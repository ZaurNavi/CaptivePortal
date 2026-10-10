"""Exact NI-03 publication boundary; no implicit/private field serialization."""
from app.network_protocol_intelligence.models import public_summary


def serialize_device_protocol_intelligence(value):
    return public_summary(value)
