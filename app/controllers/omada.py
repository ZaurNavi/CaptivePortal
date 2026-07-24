"""
Omada Controller Provider.
"""

import requests
from typing import List, Dict, Any

from app.controllers.base import ControllerInterface
from app.logger import logger
from app.models import Result
from app import get_settings


class OmadaProvider(ControllerInterface):
    """Omada SDN Controller Provider."""

    def __init__(self):
        logger.debug("Initializing OmadaProvider")
        settings = get_settings()
        self._omada_url = settings["omada_url"].rstrip("/")
        self._omada_id = settings["omada_id"]
        self._client_id = settings["client_id"]
        self._client_secret = settings["client_secret"]
        self._verify_ssl = settings["verify_ssl"]

    def _get_token(self) -> Result:
        url = f"{self._omada_url}/openapi/authorize/token?grant_type=client_credentials"
        payload = {
            "omadacId": self._omada_id,
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }
        
        try:
            response = requests.post(url, json=payload, verify=self._verify_ssl, timeout=(5, 10))
            data = response.json()
            if data.get("errorCode") == 0:
                return Result.ok(
                    message=data.get("msg", "Success"), 
                    data={"token": data["result"]["accessToken"], "http_status": response.status_code, "error_code": 0}
                )
            else:
                return Result.fail(
                    error="TOKEN_FAILED", 
                    message=data.get("msg", "Unknown token error"),
                    data={"http_status": response.status_code, "error_code": data.get("errorCode")}
                )
        except requests.exceptions.RequestException as e:
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}", data={"http_status": 0, "error_code": 0})
        except Exception as e:
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}", data={"http_status": 0, "error_code": 0})

    def connect(self) -> None:
        logger.info("Omada provider ready (dynamic token per request)")

    def get_sites(self) -> List[Dict[str, Any]]:
        token_result = self._get_token()
        if not token_result.success:
            return []
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites?page=1&pageSize=100"
        headers = {"Authorization": f"AccessToken={token}"}
        
        try:
            response = requests.get(url, headers=headers, verify=self._verify_ssl, timeout=(5, 10))
            data = response.json()
            if data.get("errorCode") == 0:
                return data.get("result", {}).get("data", [])
            return []
        except Exception:
            return []

    def get_clients(self, site_id: str) -> List[Dict[str, Any]]:
        return []

    def authorize(self, site_id: str, client_mac: str) -> Result:
        token_result = self._get_token()
        if not token_result.success:
            return token_result
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites/{site_id}/hotspot/clients/{client_mac}/auth"
        headers = {"Authorization": f"AccessToken={token}"}
        
        try:
            # В вашем коде не было body, оставляем как есть (Omada принимает пустой POST для этого эндпоинта)
            response = requests.post(url, headers=headers, verify=self._verify_ssl, timeout=(5, 10))
            data = response.json()
            
            if data.get("errorCode") == 0:
                return Result.ok(
                    message=data.get("msg", "Success"),
                    data={"http_status": response.status_code, "error_code": 0}
                )
            else:
                return Result.fail(
                    error="AUTH_FAILED", 
                    message=data.get("msg", "Unknown authorization error"),
                    data={"http_status": response.status_code, "error_code": data.get("errorCode")}
                )
        except requests.exceptions.RequestException as e:
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}", data={"http_status": 0, "error_code": 0})
        except Exception as e:
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}", data={"http_status": 0, "error_code": 0})

    def unauthorize(self, site_id: str, client_mac: str) -> Result:
        """Исправлено: используем POST /unauth согласно ТЗ, а не DELETE /auth"""
        token_result = self._get_token()
        if not token_result.success:
            return token_result
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites/{site_id}/hotspot/clients/{client_mac}/unauth"
        headers = {"Authorization": f"AccessToken={token}"}
        
        try:
            response = requests.post(url, headers=headers, verify=self._verify_ssl, timeout=(5, 10))
            data = response.json()
            
            if data.get("errorCode") == 0:
                return Result.ok(
                    message=data.get("msg", "Success"),
                    data={"http_status": response.status_code, "error_code": 0}
                )
            else:
                return Result.fail(
                    error="UNAUTH_FAILED", 
                    message=data.get("msg", "Unknown unauthorization error"),
                    data={"http_status": response.status_code, "error_code": data.get("errorCode")}
                )
        except requests.exceptions.RequestException as e:
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}", data={"http_status": 0, "error_code": 0})
        except Exception as e:
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}", data={"http_status": 0, "error_code": 0})

    def get_client(self, site_id: str, client_mac: str) -> Result:
        """Новый метод для проверки статуса клиента (ТЗ v1.6)"""
        token_result = self._get_token()
        if not token_result.success:
            return token_result
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites/{site_id}/clients/{client_mac}"
        headers = {"Authorization": f"AccessToken={token}"}
        
        try:
            response = requests.get(url, headers=headers, verify=self._verify_ssl, timeout=(5, 10))
            data = response.json()
            
            if data.get("errorCode") == 0:
                auth_status = data.get("result", {}).get("authStatus", 0)
                return Result.ok(
                    message=data.get("msg", "Success"),
                    data={
                        "http_status": response.status_code,
                        "error_code": 0,
                        "authStatus": auth_status
                    }
                )
            else:
                return Result.fail(
                    error="API_ERROR", 
                    message=data.get("msg", "Unknown error"),
                    data={"http_status": response.status_code, "error_code": data.get("errorCode"), "authStatus": 0}
                )
        except requests.exceptions.RequestException as e:
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}", data={"http_status": 0, "error_code": 0, "authStatus": 0})
        except Exception as e:
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}", data={"http_status": 0, "error_code": 0, "authStatus": 0})
