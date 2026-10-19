"""Explicit root-only pilot entry. No install, enable, reset or path override."""
import sys

STAGES=frozenset({'profile_load','coordinator_initialization','serve','claim_publish',
    'post_claim_leaf_attestation','child_spawn','child_containment','running_publish','child_release'})
REASONS=frozenset({'not_admitted','unsafe_path','gate_busy','queue_unavailable','queue_unknown',
    'coordinator_unavailable','orphan_hold','invalid_request','unauthorized'})


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if args!=['run']:return 2
    stage='profile_load';subject=None
    try:
        from .live_profile import load_profile
        from .live_coordinator import LiveCoordinator
        profile=load_profile();stage='coordinator_initialization'
        subject=LiveCoordinator(profile);stage='serve'
        try:subject.serve()
        finally:subject.close()
        return 0
    except Exception as error:
        # Only closed enums; never interpolate exception text or arbitrary attrs.
        candidate=getattr(subject,'diagnostic_stage',None)
        if type(candidate) is str and candidate in STAGES:stage=candidate
        code=getattr(error,'code',None)
        reason=code if type(code) is str and code in REASONS else 'coordinator_unavailable'
        print(f'db_audit_coordinator stage={stage} reason_code={reason}',file=sys.stderr)
        return 3


if __name__=='__main__':raise SystemExit(main())
