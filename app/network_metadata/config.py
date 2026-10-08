"""Direct process environment; disabled means no unrelated parsing or I/O."""
import ipaddress
import os
import re
from dataclasses import asdict, replace

from app.device_fingerprint.validation import validate_machine_id, validate_site_id
from .canonical import semantic_digest
from .models import (CaptureScopeBindingV1, NetworkMetadataConfig, NetworkMetadataConfigError,
    NetworkMetadataValidationError, DEFAULT_MAX_DB_BYTES, MAX_DB_BYTES, MIN_DB_BYTES, MAX_RECORD_BYTES,
    MIN_RECORD_BYTES, MAX_BATCH_RECORDS, MAX_BATCH_BYTES, LOGICAL_SOURCE_ID,
    NORMALIZER_VERSION, SOURCE_CONTRACT_VERSION)
from .validation import absolute_path, integer, ni_timestamp, ni_format_utc, strict_json, text


def make_capture_scope_binding(value):
    fields = {"schema_version", "capture_source_id", "site_id", "network_scope_id", "ipv4_cidrs", "valid_from_utc"}
    if not isinstance(value, dict) or set(value) != fields:
        raise NetworkMetadataValidationError()
    integer(value["schema_version"], 1, 1)
    try:
        capture = validate_machine_id(value["capture_source_id"])
        site = validate_site_id(value["site_id"])
    except Exception:
        raise NetworkMetadataValidationError() from None
    scope = text(value["network_scope_id"], 64, pattern=r"[A-Za-z0-9][A-Za-z0-9._:-]*", ascii_only=True)
    cidrs = value["ipv4_cidrs"]
    if type(cidrs) is not list or not 1 <= len(cidrs) <= 16:
        raise NetworkMetadataValidationError()
    networks = []
    for cidr in cidrs:
        try:
            if not isinstance(cidr, str):
                raise ValueError
            network = ipaddress.IPv4Network(cidr, strict=True)
            if str(network) != cidr or any(network.overlaps(other) for other in networks):
                raise ValueError
            networks.append(network)
        except ValueError:
            raise NetworkMetadataValidationError() from None
    ordered = tuple(str(net) for net in sorted(networks, key=lambda net: (int(net.network_address), net.prefixlen)))
    normalized = {"schema_version": 1, "capture_source_id": capture, "site_id": site,
                  "network_scope_id": scope, "ipv4_cidrs": list(ordered),
                  "valid_from_utc": ni_format_utc(ni_timestamp(value["valid_from_utc"]))}
    return CaptureScopeBindingV1(**{**normalized, "ipv4_cidrs": ordered}, binding_digest=semantic_digest(normalized))


def network_metadata_config_from_env(environ=None):
    env = os.environ if environ is None else environ
    flag = env.get("NETWORK_METADATA_ENABLED", "false")
    if type(flag) is not str or flag not in {"true", "false"}:
        raise NetworkMetadataConfigError()
    if flag == "false":
        return NetworkMetadataConfig()

    def number(key, default, low, high=None):
        value = env.get(key, str(default))
        if not isinstance(value, str) or re.fullmatch(r"[0-9]+", value, flags=re.ASCII) is None:
            raise NetworkMetadataConfigError()
        try:
            parsed = int(value)
        except ValueError:
            raise NetworkMetadataConfigError() from None
        if parsed < low or (high is not None and parsed > high):
            raise NetworkMetadataConfigError()
        return parsed

    try:
        source = absolute_path(env.get("NETWORK_METADATA_SOURCE_PATH", "/run/fingerprint-suricata/dti-ni-v1.eve.json"))
        db = absolute_path(env.get("NETWORK_METADATA_DB_PATH", "/opt/CaptivePortal/data/network_metadata.sqlite3"))
        if source in {db, db + ".writer.lock"}:
            raise NetworkMetadataValidationError()
        binding = make_capture_scope_binding(strict_json(env.get("NETWORK_METADATA_CAPTURE_SCOPE_BINDING_JSON")))
        record_limit = number("NETWORK_METADATA_MAX_RECORD_BYTES", MAX_RECORD_BYTES, MIN_RECORD_BYTES, MAX_RECORD_BYTES)
        config = NetworkMetadataConfig(True, source, db, binding,
            number("NETWORK_METADATA_MAX_DB_BYTES", DEFAULT_MAX_DB_BYTES, MIN_DB_BYTES, MAX_DB_BYTES),
            record_limit, number("NETWORK_METADATA_BATCH_MAX_RECORDS", MAX_BATCH_RECORDS, 1, MAX_BATCH_RECORDS),
            number("NETWORK_METADATA_BATCH_MAX_BYTES", MAX_BATCH_BYTES, record_limit, MAX_BATCH_BYTES),
            number("NETWORK_METADATA_POLL_INTERVAL_SECONDS", 1, 1))
        binding_value = asdict(binding)
        binding_value["ipv4_cidrs"] = list(binding.ipv4_cidrs)
        configuration = {"capture_scope_binding": binding_value, "db_path": db,
            "logical_source_id": LOGICAL_SOURCE_ID, "max_db_bytes": config.max_db_bytes,
            "max_record_bytes": config.max_record_bytes, "batch_max_records": config.batch_max_records,
            "batch_max_bytes": config.batch_max_bytes, "normalizer_version": NORMALIZER_VERSION,
            "poll_interval_seconds": config.poll_interval_seconds,
            "source_contract_version": SOURCE_CONTRACT_VERSION, "source_path": source}
        return replace(config, configuration_digest=semantic_digest(configuration))
    except NetworkMetadataValidationError:
        raise NetworkMetadataConfigError() from None
