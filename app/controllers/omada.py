"""
Omada Controller Provider.
"""

import copy
import ipaddress
import math
import os
from pathlib import Path
import re
import ssl
import stat
import threading
import time
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID
from typing import Any, Optional

from app.common.mac import format_mac_colon, format_mac_hyphen
from app.controllers.base import ControllerInterface
from app.controllers.omada_config import OmadaControllerRuntimeConfig, OmadaTlsPolicy
from app.exceptions import ConfigurationError, ControllerError
from app.logger import logger
from app.models import Result


class OmadaTransportError(requests.exceptions.SSLError):
    """Sanitized non-authoritative failure; never includes a request or credentials."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__("Omada strict transport unavailable: " + reason)


def _omada_ssl_context(policy):
    """Admit one independently approved public leaf, not a network/TOFU certificate."""
    path = Path(policy.trust_anchor_path)
    repository = Path(__file__).resolve().parents[2]
    try:
        if path.resolve().is_relative_to(repository):
            raise ConfigurationError("Omada TLS: trust_bundle_unapproved")
        if os.name != "posix":
            # A root-owned deployment file cannot be attested through POSIX mode
            # bits on Windows. Nonproduction Windows fixtures may inject admission.
            raise ConfigurationError("Omada TLS: trust_permissions_unattested")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                    or info.st_mode & 0o022 or not 0 < info.st_size <= 65536):
                raise ConfigurationError("Omada TLS: trust_bundle_unapproved")
            pem = handle.read(65537)
    except (OSError, RuntimeError):
        raise ConfigurationError("Omada TLS: trust_bundle_missing_or_unreadable") from None
    try:
        if (len(pem) > 65536 or pem.count(b"-----BEGIN CERTIFICATE-----") != 1
                or not re.fullmatch(rb"\s*-----BEGIN CERTIFICATE-----[\s\S]+-----END CERTIFICATE-----\s*", pem)):
            raise ValueError()
        cert = x509.load_pem_x509_certificate(pem)
        if cert.fingerprint(hashes.SHA256()).hex() != policy.trust_anchor_sha256:
            raise ConfigurationError("Omada TLS: trust_bundle_unapproved")
        now = datetime.now(timezone.utc)
        before = (cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc")
                  else cert.not_valid_before.replace(tzinfo=timezone.utc))
        after = (cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc")
                 else cert.not_valid_after.replace(tzinfo=timezone.utc))
        if now < before:
            raise ConfigurationError("Omada TLS: certificate_not_yet_valid")
        if now >= after:
            raise ConfigurationError("Omada TLS: certificate_expired")
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        if not any(name.lower() == "omada" for name in names.get_values_for_type(x509.DNSName)):
            raise ConfigurationError("Omada TLS: name_mismatch")
        if ExtendedKeyUsageOID.SERVER_AUTH not in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
            raise ConfigurationError("Omada TLS: certificate_purpose_invalid")
        if cert.subject != cert.issuer:
            raise ConfigurationError("Omada TLS: trust_bundle_unapproved")
        try:
            if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
                raise ConfigurationError("Omada TLS: trust_bundle_not_leaf")
        except x509.ExtensionNotFound:
            pass  # no CA capability is asserted; native TLS verification remains mandatory
        key = cert.public_key()
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
        else:
            raise ValueError()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=pem.decode("ascii"))
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            raise ConfigurationError("Omada TLS: tls_policy_invalid")
        return context
    except ConfigurationError:
        raise
    except Exception:
        raise ConfigurationError("Omada TLS: trust_bundle_invalid") from None


class _OmadaTlsAdapter(requests.adapters.HTTPAdapter):
    """Provider-local strict context, without Requests adding certifi/system roots."""

    def __init__(self, context):
        self._context = context
        super().__init__(max_retries=0)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        return super().init_poolmanager(connections, maxsize, block=block,
                                        ssl_context=self._context, **kwargs)

    def cert_verify(self, conn, url, verify, cert):
        if verify is not True or cert is not None:
            raise OmadaTransportError("tls_policy_invalid")
        conn.cert_reqs = "CERT_REQUIRED"
        conn.ca_certs = None
        conn.ca_cert_dir = None
        conn.ca_cert_data = None

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        # Requests >=2.32 otherwise substitutes its preloaded default CA context.
        if verify is not True or cert is not None:
            raise OmadaTransportError("tls_policy_invalid")
        parsed = urlsplit(request.url)
        return ({"scheme": parsed.scheme, "host": parsed.hostname, "port": parsed.port},
                {"ssl_context": self._context, "cert_reqs": "CERT_REQUIRED"})

    def proxy_manager_for(self, *args, **kwargs):
        raise OmadaTransportError("proxy_not_admitted")


class _OmadaVerifiedTransport:
    """One TLS policy for every Omada call; no shared/global Requests mutations."""

    def __init__(self, policy):
        if not isinstance(policy, OmadaTlsPolicy):
            raise ConfigurationError("Missing Omada strict TLS policy")
        self._context = _omada_ssl_context(policy)
        self._lock = threading.Lock()
        self._reason = None
        self._last_log = 0.0
        self._repeated = 0
        self._last_state = "unproven"

    def _state(self, reason):
        with self._lock:
            now = time.monotonic()
            if (self._last_state == "unproven" or reason != self._reason
                    or (reason is not None and now - self._last_log >= 60)):
                repeated = self._repeated
                if reason is None:
                    logger.info("omada.tls_state state=verified previous=%s repeated_failures=%d", self._reason, repeated)
                else:
                    logger.warning("omada.tls_state state=unavailable reason=%s previous=%s repeated_failures=%d", reason, self._reason, repeated)
                self._reason, self._last_log, self._repeated = reason, now, 0
            elif reason is not None:
                self._repeated += 1
            self._last_state = "unavailable" if reason else "verified_last_connection"

    @property
    def health(self):
        with self._lock:
            return {"verification_mode": "strict", "failure_reason": self._reason,
                    "state": self._last_state,
                    "repeated_failures": self._repeated}

    @staticmethod
    def _ssl_reason(error):
        # Only classify locally. Never return/log the raw exception, URL or request.
        text = str(error).lower()
        for markers, reason in (
            (("expired",), "certificate_expired"),
            (("not yet valid",), "certificate_not_yet_valid"),
            (("hostname", "doesn't match", "ip address mismatch"), "name_mismatch"),
            (("unsuitable certificate purpose",), "certificate_purpose_invalid"),
            (("self-signed", "unable to get local issuer", "unknown ca"), "certificate_unknown"),
        ):
            if any(marker in text for marker in markers):
                return reason
        return "tls_handshake"

    def request(self, method, url, **kwargs):
        try:
            parsed = urlsplit(url)
            decoded = unquote(parsed.path)
            if (parsed.scheme != "https" or parsed.hostname is None or parsed.hostname.lower() != "omada"
                    or parsed.port != 8043 or parsed.netloc.lower() != "omada:8043"
                    or parsed.username is not None or parsed.password is not None or parsed.fragment
                    or "\\" in url or any(ord(char) <= 32 for char in url)
                    or decoded != parsed.path or any(part in {".", ".."} for part in decoded.split("/"))
                    or not (parsed.path == "/openapi/authorize/token" or parsed.path.startswith("/openapi/v1/"))):
                raise OmadaTransportError("origin_not_admitted")
            if set(kwargs) - {"headers", "params", "json", "timeout"}:
                raise OmadaTransportError("tls_policy_override_not_admitted")
            if any(key.lower() in {"host", "proxy-authorization"} for key in kwargs.get("headers", {})):
                raise OmadaTransportError("origin_not_admitted")
            # Match existing top-level requests lifecycle: a fresh session/connection
            # per operation. No indefinite pooled certificate/expiry attestation.
            with requests.Session() as session:
                session.trust_env = False  # excludes proxy, netrc and env CA overrides
                session.mount("https://", _OmadaTlsAdapter(self._context))
                response = session.request(method, url, verify=True, allow_redirects=False, **kwargs)
                if 300 <= response.status_code < 400:
                    response.close()
                    raise OmadaTransportError("redirect_not_admitted")
            self._state(None)
            return response
        except OmadaTransportError as error:
            self._state(error.reason)
            raise
        except requests.exceptions.SSLError as error:
            reason = self._ssl_reason(error)
            self._state(reason)
            raise OmadaTransportError(reason) from None
        except requests.exceptions.ProxyError:
            self._state("proxy_not_admitted")
            raise OmadaTransportError("proxy_not_admitted") from None
        except requests.exceptions.Timeout:
            self._state("timeout")
            raise
        except requests.exceptions.ConnectionError:
            self._state("network_error")
            raise
        except (ValueError, TypeError):
            self._state("origin_not_admitted")
            raise OmadaTransportError("origin_not_admitted") from None


class OmadaProvider(ControllerInterface):
    """Omada SDN Controller Provider."""

    CLIENT_PAGE_SIZE = 100
    CLIENT_MAX_PAGES = 100
    def __init__(self, runtime_config: OmadaControllerRuntimeConfig):
        logger.debug("Initializing OmadaProvider")
        if not isinstance(runtime_config, OmadaControllerRuntimeConfig):
            raise TypeError("OmadaControllerRuntimeConfig required")
        self._omada_url = runtime_config.controller_url
        self._omada_id = runtime_config.controller_id
        self._client_id = runtime_config.client_id
        self._client_secret = runtime_config.client_secret
        self._verify_ssl = runtime_config.verify_ssl
        try:
            self._transport = _OmadaVerifiedTransport(runtime_config.tls_policy)
        except ConfigurationError:
            logger.error("omada.tls_preflight state=unavailable")
            raise
        self._token_condition = threading.Condition(
            threading.RLock()
        )
        self._cached_token = None
        self._cached_token_expires_at = 0.0
        self._token_refreshing = False

    def _request(self, method, url, **kwargs):
        transport = getattr(self, "_transport", None)
        if not isinstance(transport, _OmadaVerifiedTransport):
            raise OmadaTransportError("tls_policy_missing")
        return transport.request(method, url, **kwargs)

    @property
    def tls_health(self):
        return self._transport.health

    def _request_token_uncached(self) -> Result:
        url = f"{self._omada_url}/openapi/authorize/token?grant_type=client_credentials"
        payload = {
            "omadacId": self._omada_id,
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }

        try:
            response = self._request("POST",
                url,
                json=payload,
                timeout=(5, 10),
            )
        except OmadaTransportError as exc:
            return Result.fail(error="OMADA_TLS_UNAVAILABLE", message=str(exc), data={
                "http_status": 0, "error_code": 0, "failure_category": exc.reason, "retryable": False})
        except requests.exceptions.Timeout as exc:
            return Result.fail(
                error="HTTP_ERROR",
                message=f"HTTP Error: {str(exc)}",
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "failure_category": "timeout",
                    "retryable": True,
                },
            )
        except requests.exceptions.ConnectionError as exc:
            return Result.fail(
                error="HTTP_ERROR",
                message=f"HTTP Error: {str(exc)}",
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "failure_category": "network_error",
                    "retryable": True,
                },
            )
        except requests.exceptions.RequestException as exc:
            return Result.fail(
                error="HTTP_ERROR",
                message=f"HTTP Error: {str(exc)}",
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "failure_category": "network_error",
                    "retryable": True,
                },
            )
        except Exception as exc:
            return Result.fail(
                error="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(exc)}",
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "failure_category": "token_error",
                    "retryable": False,
                },
            )

        http_status = response.status_code
        if not 200 <= http_status <= 299:
            data = self._response_json_object(response)
            error_code = (
                data.get("errorCode")
                if data is not None
                else None
            )
            category, retryable = self._http_failure(http_status)
            return Result.fail(
                error="TOKEN_FAILED",
                message="Token endpoint returned an HTTP error",
                data={
                    "http_status": http_status,
                    "error_code": error_code,
                    "failure_category": category,
                    "retryable": retryable,
                },
            )

        data = self._response_json_object(response)
        if data is None:
            return Result.fail(
                error="TOKEN_FAILED",
                message="Token endpoint returned a malformed response",
                data={
                    "http_status": http_status,
                    "error_code": None,
                    "failure_category": "malformed_response",
                    "retryable": True,
                },
            )

        error_code = data.get("errorCode")
        if (
            isinstance(error_code, bool)
            or not isinstance(error_code, (int, str))
        ):
            return Result.fail(
                error="TOKEN_FAILED",
                message="Token endpoint response has no valid errorCode",
                data={
                    "http_status": http_status,
                    "error_code": None,
                    "failure_category": "malformed_response",
                    "retryable": True,
                },
            )
        if not self._is_success_error_code(error_code):
            return Result.fail(
                error="TOKEN_FAILED",
                message=self._response_message(
                    data,
                    "Unknown token error",
                ),
                data={
                    "http_status": http_status,
                    "error_code": error_code,
                    "failure_category": "token_error",
                    "retryable": False,
                },
            )

        result = data.get("result")
        token = (
            result.get("accessToken")
            if isinstance(result, dict)
            else None
        )
        if not isinstance(token, str) or not token:
            return Result.fail(
                error="TOKEN_FAILED",
                message="Token endpoint response has no access token",
                data={
                    "http_status": http_status,
                    "error_code": error_code,
                    "failure_category": "malformed_response",
                    "retryable": True,
                },
            )

        return Result.ok(
            message=self._response_message(data, "Success"),
            data={
                "token": token,
                "http_status": http_status,
                "error_code": 0,
            },
        )

    def _ensure_token_cache_state(self) -> None:
        # Support normal construction and tests using __new__.
        if hasattr(self, "_token_condition"):
            return
        self._token_condition = threading.Condition(
            threading.RLock()
        )
        self._cached_token = None
        self._cached_token_expires_at = 0.0
        self._token_refreshing = False

    def _get_token(self, *, force_refresh: bool = False) -> Result:
        # One atomic cache shared by AuthWorker and Cleaner threads.
        self._ensure_token_cache_state()
        while True:
            with self._token_condition:
                now = time.monotonic()
                if (
                    not force_refresh
                    and isinstance(self._cached_token, str)
                    and self._cached_token
                    and now + 30.0 < self._cached_token_expires_at
                ):
                    return Result.ok(
                        message="Success",
                        data={
                            "token": self._cached_token,
                            "http_status": 200,
                            "error_code": 0,
                        },
                    )
                if self._token_refreshing:
                    self._token_condition.wait()
                    force_refresh = False
                    continue
                self._token_refreshing = True
                break

        result = None
        try:
            result = self._request_token_uncached()
            return result
        finally:
            with self._token_condition:
                if result is not None and result.success:
                    token = result.data.get("token")
                    if isinstance(token, str) and token:
                        self._cached_token = token
                        # Token lifetime is two hours; refresh early.
                        self._cached_token_expires_at = (
                            time.monotonic() + 6600.0
                        )
                self._token_refreshing = False
                self._token_condition.notify_all()

    def _invalidate_cached_token(self, token=None) -> None:
        self._ensure_token_cache_state()
        with self._token_condition:
            if token is None or token == self._cached_token:
                self._cached_token = None
                self._cached_token_expires_at = 0.0
            self._token_condition.notify_all()

    def connect(self) -> None:
        logger.info("Omada provider configured (strict TLS; shared token cache)")

    def get_sites(self) -> list[dict[str, Any]]:
        token_result = self._get_token()
        if not token_result.success:
            raise ControllerError("Omada authority unavailable")

        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites?page=1&pageSize=100"
        headers = {"Authorization": f"AccessToken={token}"}

        try:
            response = self._request("GET",
                url,
                headers=headers,
                timeout=(5, 10),
            )
            data = response.json()
            if (not 200 <= response.status_code < 300 or not isinstance(data, dict)
                    or not self._is_success_error_code(data.get("errorCode")) or not isinstance(data.get("result"), dict)
                    or not isinstance(data["result"].get("data"), list)
                    or any(not isinstance(row, dict) for row in data["result"]["data"])):
                raise ControllerError("Omada authority unavailable")
            return data["result"]["data"]
        except Exception:
            # Public success remains a list; failed authority is never a zero-site fact.
            raise ControllerError("Omada authority unavailable") from None

    def get_clients(self, site_id: str) -> Result:
        """
        Return one normalized snapshot of all clients in a site.

        Omada transport details and response-shape handling stay in this
        provider. Callers receive only the stable ``clients`` contract.
        """
        if not isinstance(site_id, str) or not site_id.strip():
            return Result.fail(
                error="INVALID_SITE_ID",
                message="site_id is required",
                data={"http_status": 0, "error_code": 0},
            )

        token_result = self._get_token()
        if not token_result.success:
            return token_result

        token = token_result.data.get("token")
        url = (
            f"{self._omada_url}/openapi/v1/{self._omada_id}"
            f"/sites/{site_id.strip()}/clients"
        )
        headers = {"Authorization": f"AccessToken={token}"}
        clients: list[dict[str, Any]] = []
        last_http_status = 0
        total_rows: Optional[int] = None

        for page in range(1, self.CLIENT_MAX_PAGES + 1):
            try:
                response = self._request("GET",
                    url,
                    headers=headers,
                    params={
                        "page": page,
                        "pageSize": self.CLIENT_PAGE_SIZE,
                    },
                    timeout=(5, 10),
                )
                last_http_status = response.status_code
            except requests.exceptions.RequestException as exc:
                return Result.fail(
                    error="HTTP_ERROR",
                    message=f"HTTP Error: {str(exc)}",
                    data={
                        "http_status": 0,
                        "error_code": 0,
                    },
                )

            try:
                payload = response.json()
            except (TypeError, ValueError) as exc:
                return Result.fail(
                    error="MALFORMED_RESPONSE",
                    message=f"Invalid Omada JSON: {str(exc)}",
                    data={
                        "http_status": response.status_code,
                        "error_code": None,
                    },
                )

            if not isinstance(payload, dict):
                return Result.fail(
                    error="MALFORMED_RESPONSE",
                    message="Omada response must be an object",
                    data={
                        "http_status": response.status_code,
                        "error_code": None,
                    },
                )

            error_code = payload.get("errorCode")
            if error_code != 0:
                return Result.fail(
                    error="API_ERROR",
                    message=payload.get("msg", "Unknown client-list error"),
                    data={
                        "http_status": response.status_code,
                        "error_code": error_code,
                    },
                )

            if not 200 <= response.status_code < 300:
                return Result.fail(
                    error="HTTP_ERROR",
                    message="Omada client-list HTTP error",
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                    },
                )

            result = payload.get("result")
            if not isinstance(result, dict):
                return Result.fail(
                    error="MALFORMED_RESPONSE",
                    message="Omada result must be an object",
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                    },
                )

            page_data = result.get("data")
            if not isinstance(page_data, list):
                return Result.fail(
                    error="MALFORMED_RESPONSE",
                    message="Omada client data must be a list",
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                    },
                )

            if total_rows is None:
                total_rows = self._extract_total_rows(result)

            for item in page_data:
                normalized = self._normalize_client(item)
                if normalized is not None:
                    clients.append(normalized)

            if not page_data:
                break
            if total_rows is not None and len(clients) >= total_rows:
                break
            if len(page_data) < self.CLIENT_PAGE_SIZE:
                break
        else:
            return Result.fail(
                error="PAGINATION_LIMIT",
                message="Omada client pagination limit reached",
                data={
                    "http_status": last_http_status,
                    "error_code": 0,
                },
            )

        return Result.ok(
            message="Success",
            data={
                "clients": clients,
                "http_status": last_http_status,
                "error_code": 0,
            },
        )

    def get_client_by_ip(
        self,
        site_id: str,
        client_ip: str,
    ) -> Result:
        try:
            normalized_ip = str(ipaddress.ip_address(client_ip))
        except (TypeError, ValueError):
            return Result.fail(
                error="INVALID_CLIENT_IP",
                message="Invalid client IP address",
                data={"http_status": 0, "error_code": 0},
            )

        clients_result = self.get_clients(site_id)
        if not clients_result.success:
            return clients_result

        matches = [
            client
            for client in clients_result.data.get("clients", [])
            if client.get("client_ip") == normalized_ip
        ]
        selected = self._select_duplicate_safe(matches)
        if selected is None and len(matches) > 1:
            logger.warning(
                "omada.duplicate_client_ip site_id=%s client_ip=%s",
                site_id,
                normalized_ip,
            )
            return Result.fail(
                error="DUPLICATE_CLIENT_IP",
                message="Ambiguous Omada client IP",
                data={
                    "http_status": clients_result.data.get(
                        "http_status",
                        0,
                    ),
                    "error_code": 0,
                },
            )

        if selected is None:
            return Result.ok(
                message="Client not found",
                data={
                    "found": False,
                    "site_id": site_id,
                    "client_ip": normalized_ip,
                    "client_mac": None,
                    "list_auth_status": None,
                    "list_active": None,
                    "http_status": clients_result.data.get(
                        "http_status",
                        0,
                    ),
                    "error_code": 0,
                },
            )

        return Result.ok(
            message="Success",
            data={
                "found": True,
                "site_id": site_id,
                "client_ip": normalized_ip,
                "client_mac": selected["client_mac"],
                # Informational only; CAPPORT state must use get_client().
                "list_auth_status": selected["authStatus"],
                "list_active": selected["active"],
                "http_status": clients_result.data.get(
                    "http_status",
                    0,
                ),
                "error_code": 0,
            },
        )

    @staticmethod
    def _extract_total_rows(result: dict[str, Any]) -> Optional[int]:
        for key in ("totalRows", "total", "totalNum"):
            value = result.get(key)
            if value is None:
                continue
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed >= 0:
                return parsed
        return None

    @classmethod
    def _normalize_client(
        cls,
        item: Any,
    ) -> Optional[dict[str, Any]]:
        if not isinstance(item, dict):
            return None

        raw_ip = cls._first_value(
            item,
            "ip",
            "clientIp",
            "client_ip",
        )
        raw_mac = cls._first_value(
            item,
            "mac",
            "clientMac",
            "client_mac",
        )
        try:
            client_ip = str(ipaddress.ip_address(raw_ip))
            client_mac = cls._normalize_mac(raw_mac)
        except (TypeError, ValueError):
            return None

        return {
            "client_ip": client_ip,
            "client_mac": client_mac,
            "ssid": cls._optional_ssid(item.get("ssid")),
            "authStatus": cls._optional_int(
                item.get("authStatus")
            ),
            "active": cls._optional_bool(item.get("active")),
        }

    @staticmethod
    def _first_value(
        item: dict[str, Any],
        *keys: str,
    ) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _normalize_mac(value: Any) -> str:
        return format_mac_colon(value)

    @staticmethod
    def _optional_ssid(value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return None
        if "\x00" in value:
            return None
        return value

    @staticmethod
    def _optional_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return None

    @staticmethod
    def _select_duplicate_safe(
        matches: list[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return None
        active = [
            client
            for client in matches
            if client.get("active") is True
        ]
        if len(active) == 1:
            return active[0]
        return None

    def authorize(self, site_id: str, client_mac: str) -> Result:
        token_result = self._get_token()
        if not token_result.success:
            return token_result

        token = token_result.data.get("token")
        url = (
            f"{self._omada_url}/openapi/v1/{self._omada_id}"
            f"/sites/{site_id}/hotspot/clients/{client_mac}/auth"
        )
        headers = {"Authorization": f"AccessToken={token}"}

        try:
            response = self._request("POST",
                url,
                headers=headers,
                timeout=(5, 10),
            )
            data = response.json()

            if data.get("errorCode") == 0:
                return Result.ok(
                    message=data.get("msg", "Success"),
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                    },
                )

            return Result.fail(
                error="AUTH_FAILED",
                message=data.get(
                    "msg",
                    "Unknown authorization error",
                ),
                data={
                    "http_status": response.status_code,
                    "error_code": data.get("errorCode"),
                },
            )
        except requests.exceptions.RequestException as exc:
            return Result.fail(
                error="HTTP_ERROR",
                message=f"HTTP Error: {str(exc)}",
                data={"http_status": 0, "error_code": 0},
            )
        except Exception as exc:
            return Result.fail(
                error="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(exc)}",
                data={"http_status": 0, "error_code": 0},
            )

    def unauthorize(self, site_id: str, client_mac: str) -> Result:
        """Используем POST /unauth согласно API Omada."""
        token_result = self._get_token()
        if not token_result.success:
            return token_result

        token = token_result.data.get("token")
        url = (
            f"{self._omada_url}/openapi/v1/{self._omada_id}"
            f"/sites/{site_id}/hotspot/clients/{client_mac}/unauth"
        )
        headers = {"Authorization": f"AccessToken={token}"}

        try:
            response = self._request("POST",
                url,
                headers=headers,
                timeout=(5, 10),
            )
            data = response.json()

            if data.get("errorCode") == 0:
                return Result.ok(
                    message=data.get("msg", "Success"),
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                    },
                )

            return Result.fail(
                error="UNAUTH_FAILED",
                message=data.get(
                    "msg",
                    "Unknown unauthorization error",
                ),
                data={
                    "http_status": response.status_code,
                    "error_code": data.get("errorCode"),
                },
            )
        except requests.exceptions.RequestException as exc:
            return Result.fail(
                error="HTTP_ERROR",
                message=f"HTTP Error: {str(exc)}",
                data={"http_status": 0, "error_code": 0},
            )
        except Exception as exc:
            return Result.fail(
                error="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(exc)}",
                data={"http_status": 0, "error_code": 0},
            )

    def get_client(self, site_id: str, client_mac: str) -> Result:
        """
        Получает состояние клиента.

        Worker использует одновременно:
        - authStatus == 2: клиент уже авторизован;
        - active == true: клиент готов принять команду /auth.
        """
        token_result = self._get_token()
        if not token_result.success:
            return token_result

        token = token_result.data.get("token")
        url = (
            f"{self._omada_url}/openapi/v1/{self._omada_id}"
            f"/sites/{site_id}/clients/{client_mac}"
        )
        headers = {"Authorization": f"AccessToken={token}"}

        try:
            response = self._request("GET",
                url,
                headers=headers,
                timeout=(5, 10),
            )
            data = response.json()

            if data.get("errorCode") == 0:
                client_data = data.get("result") or {}
                auth_status = client_data.get("authStatus")
                active = client_data.get("active")

                return Result.ok(
                    message=data.get("msg", "Success"),
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                        "authStatus": auth_status,
                        "active": active,
                    },
                )

            return Result.fail(
                error="API_ERROR",
                message=data.get("msg", "Unknown error"),
                data={
                    "http_status": response.status_code,
                    "error_code": data.get("errorCode"),
                    "authStatus": None,
                    "active": None,
                },
            )
        except requests.exceptions.RequestException as exc:
            return Result.fail(
                error="HTTP_ERROR",
                message=f"HTTP Error: {str(exc)}",
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "authStatus": None,
                    "active": None,
                },
            )
        except Exception as exc:
            return Result.fail(
                error="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(exc)}",
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "authStatus": None,
                    "active": None,
                },
            )

    def get_client_snapshot(
        self,
        site_id: str,
        client_mac: str,
        timeout_seconds: float,
    ) -> Result:
        """Return the complete Omada client result for Visitor Snapshot."""
        if not isinstance(site_id, str) or not site_id.strip():
            return self._snapshot_failure(
                category="invalid_request",
                retryable=False,
                message="site_id is required",
            )
        try:
            endpoint_mac = format_mac_hyphen(client_mac)
        except ValueError:
            return self._snapshot_failure(
                category="invalid_request",
                retryable=False,
                message="client_mac is invalid",
            )
        if isinstance(timeout_seconds, bool):
            return self._snapshot_failure(
                category="invalid_request",
                retryable=False,
                message="timeout_seconds must be positive",
            )
        try:
            request_timeout = float(timeout_seconds)
        except (TypeError, ValueError):
            return self._snapshot_failure(
                category="invalid_request",
                retryable=False,
                message="timeout_seconds must be positive",
            )
        if request_timeout <= 0 or not math.isfinite(
            request_timeout
        ):
            return self._snapshot_failure(
                category="invalid_request",
                retryable=False,
                message="timeout_seconds must be positive",
            )

        token_result = self._get_token()
        if not token_result.success:
            token_data = (
                token_result.data
                if isinstance(token_result.data, dict)
                else {}
            )
            failure_category = str(
                token_data.get(
                    "failure_category",
                    "token_error",
                )
            )
            transport_failure = failure_category in {
                "timeout",
                "network_error",
            }
            return self._snapshot_failure(
                category=failure_category,
                retryable=bool(
                    token_data.get("retryable", False)
                ),
                message=token_result.message or "Token request failed",
                http_status=(
                    None
                    if transport_failure
                    else self._optional_http_status(
                        token_data.get("http_status")
                    )
                ),
                error_code=(
                    None
                    if transport_failure
                    else self._optional_error_code(
                        token_data.get("error_code")
                    )
                ),
            )

        token = token_result.data.get("token")
        url = (
            f"{self._omada_url}/openapi/v1/{self._omada_id}"
            f"/sites/{site_id.strip()}/clients/{endpoint_mac}"
        )
        headers = {
            "Authorization": f"AccessToken={token}",
            "Accept": "application/json",
        }
        try:
            response = self._request("GET",
                url,
                headers=headers,
                timeout=(request_timeout, request_timeout),
            )
        except requests.exceptions.Timeout as exc:
            return self._snapshot_failure(
                category="timeout",
                retryable=True,
                message=f"Client snapshot request timed out: {exc}",
            )
        except requests.exceptions.ConnectionError as exc:
            return self._snapshot_failure(
                category="network_error",
                retryable=True,
                message=f"Client snapshot network error: {exc}",
            )
        except requests.exceptions.RequestException as exc:
            return self._snapshot_failure(
                category="network_error",
                retryable=True,
                message=f"Client snapshot request failed: {exc}",
            )

        http_status = response.status_code
        if not 200 <= http_status <= 299:
            data = self._response_json_object(response)
            error_code = (
                data.get("errorCode")
                if data is not None
                else None
            )
            category, retryable = self._http_failure(http_status)
            return self._snapshot_failure(
                category=category,
                retryable=retryable,
                message="Client endpoint returned an HTTP error",
                http_status=http_status,
                error_code=self._optional_error_code(error_code),
            )

        data = self._response_json_object(response)
        if data is None:
            return self._snapshot_failure(
                category="malformed_response",
                retryable=True,
                message="Client endpoint returned malformed JSON",
                http_status=http_status,
            )

        error_code = data.get("errorCode")
        if (
            isinstance(error_code, bool)
            or not isinstance(error_code, (int, str))
        ):
            return self._snapshot_failure(
                category="malformed_response",
                retryable=True,
                message=(
                    "Client endpoint response has no valid errorCode"
                ),
                http_status=http_status,
            )
        if error_code in {-41011, "-41011"}:
            return self._snapshot_failure(
                category="client_not_available",
                retryable=True,
                message=self._response_message(
                    data,
                    "Client snapshot is not available",
                ),
                http_status=http_status,
                error_code=error_code,
            )
        if not self._is_success_error_code(error_code):
            return self._snapshot_failure(
                category="controller_error",
                retryable=False,
                message=self._response_message(
                    data,
                    "Controller rejected client snapshot request",
                ),
                http_status=http_status,
                error_code=self._optional_error_code(error_code),
            )

        raw_result = data.get("result")
        if raw_result is None:
            return self._snapshot_failure(
                category="client_not_available",
                retryable=True,
                message="Client snapshot result is not available",
                http_status=http_status,
                error_code=0,
            )
        if not isinstance(raw_result, dict):
            return self._snapshot_failure(
                category="malformed_response",
                retryable=True,
                message="Client snapshot result must be an object",
                http_status=http_status,
                error_code=0,
            )
        try:
            format_mac_colon(raw_result.get("mac"))
        except ValueError:
            return self._snapshot_failure(
                category="client_not_available",
                retryable=True,
                message="Client snapshot result has no valid MAC",
                http_status=http_status,
                error_code=0,
            )
        try:
            raw_copy = copy.deepcopy(raw_result)
        except Exception:
            return self._snapshot_failure(
                category="malformed_response",
                retryable=True,
                message="Client snapshot result could not be copied",
                http_status=http_status,
                error_code=0,
            )
        return Result.ok(
            message=self._response_message(data, "Success."),
            data={
                "http_status": http_status,
                "error_code": 0,
                "raw_result": raw_copy,
            },
        )

    @staticmethod
    def _response_json_object(response: Any) -> Optional[dict[str, Any]]:
        try:
            data = response.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _response_message(
        data: dict[str, Any],
        default: str,
    ) -> str:
        message = data.get("msg")
        return message if isinstance(message, str) else default

    @staticmethod
    def _http_failure(status: int) -> tuple[str, bool]:
        if status == 408:
            return "timeout", True
        if status == 429 or 500 <= status <= 599:
            return "http_error", True
        return "http_error", False

    @staticmethod
    def _is_success_error_code(value: Any) -> bool:
        return value in {0, "0"} and not isinstance(value, bool)

    @staticmethod
    def _optional_http_status(value: Any) -> Optional[int]:
        return value if type(value) is int and value > 0 else None

    @staticmethod
    def _optional_error_code(value: Any) -> Any:
        if isinstance(value, bool):
            return None
        return value if isinstance(value, (int, str)) else None

    @classmethod
    def _snapshot_failure(
        cls,
        *,
        category: str,
        retryable: bool,
        message: str,
        http_status: Optional[int] = None,
        error_code: Any = None,
        raw_result: Optional[dict[str, Any]] = None,
    ) -> Result:
        return Result.fail(
            error="SNAPSHOT_REQUEST_FAILED",
            message=message,
            data={
                "http_status": http_status,
                "error_code": error_code,
                "failure_category": category,
                "retryable": bool(retryable),
                "raw_result": raw_result,
            },
        )
