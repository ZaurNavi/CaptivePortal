"""Shared checked direct-SNI evaluation. Sensitive inputs remain batch-local."""
from dataclasses import dataclass
from datetime import timedelta
from app.device_fingerprint.validation import validate_site_id
from app.network_attribution.validation import canonical_mac
from app.network_metadata.validation import canonical_uuid,integer,ni_timestamp,ni_format_utc
from app.network_metadata.recognition_read_service import RecognitionSourceEvidenceV1
from app.network_metadata_projection.recognition_read_service import RecognitionProjectionEdgeFactV1
from app.network_metadata_projection.service_delivery_read_service import RecognitionIdentityV1
from .artifacts import RecognitionBundle,AdmittedArtifact
from .canonical import canonical_hostname
from .matcher import match_direct_sni_v1,matching_rules,rule_eligible
from .models import ServiceUnavailable,service_observation


@dataclass(frozen=True,slots=True,repr=False)
class EvaluatedCandidateV1:
    identity: RecognitionIdentityV1
    observation: object
    matched_rule_id: str | None
    limited: bool
    observed_at: str
    coverage_valid_from_utc: str


class ServiceRecognitionEvaluatorV1:
    def __init__(self,bundle, *, matcher=match_direct_sni_v1):
        if type(bundle) is not RecognitionBundle or not all(type(a) is AdmittedArtifact for a in (bundle.taxonomy,bundle.manifest,bundle.ruleset)):
            raise ServiceUnavailable("recognition_unavailable")
        self.bundle,self._matcher=bundle,matcher

    @staticmethod
    def validate(fact,value,identity,evaluated_at_utc, *, window_from_utc=None):
        at=ni_timestamp(evaluated_at_utc,canonical=True)
        first=ni_timestamp(window_from_utc,canonical=True) if window_from_utc is not None else at-timedelta(days=1)
        if not at-timedelta(days=14)<=first<at:raise ServiceUnavailable()
        if type(identity) is not RecognitionIdentityV1 or identity.binding_state!="authoritative":
            raise ServiceUnavailable()
        validate_site_id(identity.site_id)
        canonical_uuid(identity.device_id)
        if canonical_mac(identity.client_mac)!=identity.client_mac:
            raise ServiceUnavailable()
        if identity.registry_binding_change_seq is not None:
            integer(identity.registry_binding_change_seq,1)
        if (type(fact) is not RecognitionProjectionEdgeFactV1 or fact.direction!="outbound" or fact.peer_scope!="external"
                or fact.device_endpoint_role!="src" or fact.source_event_family not in {"dns","tls","quic"}
                or not first<=ni_timestamp(fact.event_at,canonical=True)<at):
            raise ServiceUnavailable()
        if (type(value) is not RecognitionSourceEvidenceV1 or type(value.schema_version) is not int or value.schema_version!=1
                or value.site_id!=identity.site_id or value.observation_id!=fact.source_observation_ref
                or any(getattr(value,k)!=getattr(fact,k) for k in ("event_at","source_event_family","source_generation_id","capture_source_id","network_scope_id","capture_scope_binding_digest"))):
            raise ServiceUnavailable()
        if sum(p is not None for p in (value.dns,value.tls,value.quic))!=1 or getattr(value,value.source_event_family) is None:
            raise ServiceUnavailable()
        if value.sensitive_endpoint_presence_state=="observed_retained":
            if (value.src_ip,value.src_port,value.dst_ip,value.dst_port,value.transport_protocol)!=(fact.device_ip,fact.device_port,fact.peer_ip,fact.peer_port,fact.transport_protocol):
                raise ServiceUnavailable()
        elif value.sensitive_endpoint_presence_state!="expired":
            raise ServiceUnavailable()

    def evaluate_batch(self,candidates,evidence,evaluated_at_utc, *, deadline,maximum=256,window_from_utc=None):
        """Validate the whole set BEFORE the first matcher invocation."""
        if type(candidates) is not tuple or not 0<=len(candidates)<=maximum or maximum not in {128,256,5000}:
            raise ServiceUnavailable()
        for fact,identity in candidates:
            deadline.require_remaining()
            if fact.source_observation_ref not in evidence:
                raise ServiceUnavailable()
            self.validate(fact,evidence[fact.source_observation_ref],identity,evaluated_at_utc,window_from_utc=window_from_utc)
        output=[]
        at=ni_timestamp(evaluated_at_utc,canonical=True)
        b=self.bundle
        global_limited=not any(rule_eligible(r,b.manifest,at) for r in b.ruleset["rules"] if r["target_type"]=="service" and "_sni_" in r["rule_kind"])
        for fact,identity in candidates:
            deadline.require_remaining()
            value=evidence[fact.source_observation_ref]
            limited=global_limited or value.sensitive_endpoint_presence_state=="expired"
            observation=rule_id=None
            if value.dns is not None:
                dns=value.dns
                limited|=(dns.queries_truncated or dns.answers_truncated or dns.query_names_presence_state=="expired"
                    or dns.answer_values_presence_state=="expired" or any(canonical_hostname(q.query_name) is None or matching_rules(q.query_name,b.ruleset) for q in dns.queries))
            else:
                payload=value.tls if value.tls is not None else value.quic
                host=canonical_hostname(payload.sni)
                if payload.sni_presence_state!="observed_retained" or host is None:
                    limited=True
                else:
                    matching=matching_rules(host,b.ruleset)
                    limited|=any(r["lifecycle_state"]=="active" and not rule_eligible(r,b.manifest,at) for r in matching)
                    matched=self._matcher(hostname=host,signal_family=fact.source_event_family+"_sni",evaluated_at_utc=evaluated_at_utc,taxonomy=b.taxonomy,manifest=b.manifest,ruleset=b.ruleset)
                    limited|=matched.resolution_state=="ambiguous"
                    observation=service_observation(identity.site_id,identity.device_id,fact,matched)
                    if matched.resolution_state=="service_resolved":
                        if len(matched.matched_rule_ids)!=1:
                            raise ServiceUnavailable("recognition_unavailable")
                        rule_id=matched.matched_rule_ids[0]
            output.append(EvaluatedCandidateV1(identity,observation,rule_id,bool(limited),fact.event_at,window_from_utc or ni_format_utc(at-timedelta(days=1))))
        deadline.require_remaining()
        return tuple(output),global_limited
