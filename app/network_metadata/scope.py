"""Exact valid-from and IPv4-only scope authority; no device attribution."""
import ipaddress

from .models import NetworkMetadataValidationError
from .validation import ip, ni_timestamp


def check_valid_from(event_at, binding):
    return "pre_binding_event" if ni_timestamp(event_at) < ni_timestamp(binding.valid_from_utc) else None


def check_network_scope(event, binding):
    src = ip(event["src_ip"]) if "src_ip" in event else None
    dst = ip(event["dest_ip"]) if "dest_ip" in event else None
    endpoints = [ipaddress.ip_address(value) for value in (src, dst) if value is not None]
    if not endpoints:
        raise NetworkMetadataValidationError()
    ipv4 = [address for address in endpoints if address.version == 4]
    if not ipv4:
        return "unsupported_address_family_for_scope", src, dst
    networks = tuple(ipaddress.IPv4Network(cidr) for cidr in binding.ipv4_cidrs)
    if not any(address in network for address in ipv4 for network in networks):
        return "outside_intended_scope", src, dst
    return None, src, dst
