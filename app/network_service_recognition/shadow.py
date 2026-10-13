"""Protected Lab comparison at one supplied evaluation time, never fallback."""
from dataclasses import dataclass
from .models import ServiceDeadline,ServiceUnavailable


@dataclass(frozen=True,slots=True)
class ShadowComparisonV1:
    schema_version: int
    status: str
    legacy_positive_count: int
    materialized_positive_count: int
    missing_positive_count: int
    extra_positive_count: int


def compare_shadow(legacy,materialized,site_id,device_id,client_mac, *, evaluated_at_utc,deadline):
    try:
        old=legacy.get_device_service_summary(site_id,device_id,client_mac,evaluated_at_utc=evaluated_at_utc,deadline=deadline)
    except ServiceDeadline:
        return ShadowComparisonV1(1,'LEGACY_DEADLINE_RECORDED',0,0,0,0)
    new=materialized.get_device_service_summary(site_id,device_id,client_mac,evaluated_at_utc=evaluated_at_utc,deadline=deadline)
    for value,version in ((old,2),(new,3)):
        if value.schema_version!=version or (value.site_id,value.device_id,value.evaluated_at_utc)!=(site_id,device_id,evaluated_at_utc):
            raise ServiceUnavailable('recognition_unavailable')
    def positives(value):
        rows=list(value.recent_services)
        if value.last_service_observation is not None:rows.append(value.last_service_observation)
        return {(r.service_id,r.organization_id,r.service_category_id,r.support_state) for r in rows}
    expected,actual=positives(old),positives(new)
    missing,extra=expected-actual,actual-expected
    # Required lineage is validated by the materialized reader before return;
    # no sensitive identifiers are reflected in comparison reporting.
    return ShadowComparisonV1(1,'PASS' if not missing and not extra else 'FAIL',len(expected),len(actual),len(missing),len(extra))
