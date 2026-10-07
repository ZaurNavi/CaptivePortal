"""Local stopped-service recovery; no key access or service-control authority."""
import argparse
import getpass
import os
import uuid
from types import SimpleNamespace

from .controller_secret import ControllerSecretRepository, SecretFilesystem, SETTINGS_DB_PATH, binding, gc_secret_versions
from .models import SettingsError, utc_now
from .repository import SettingsRepository


def clear_managed_secret(repository, expected_generation, *, filesystem=None, operator=getpass.getuser, deployment_source=None):
    secrets = ControllerSecretRepository(repository, filesystem)
    secrets.check_db()  # Deliberately does not load a master key or decrypt.
    with repository.transaction(write=True) as db:
        parent = repository.head(db)
        if parent != expected_generation:
            raise SettingsError("stale_generation", 412)
        previous = binding(db, parent)
        if previous is None:
            return parent, False
        principal = SimpleNamespace(principal_type="local_operator", username=operator())
        request_id = str(uuid.uuid4())
        generation = repository.create_generation(db, parent=parent, principal=principal, request_id=request_id,
            created_at=utc_now(), overrides=repository.overrides(db, parent), carry_secret=False)
        secrets.audit(db, generation=generation, parent=parent, principal=principal, source_ip="local",
            request_id=request_id, key=None, operation="clear_secret_override_recovery", previous=previous,
            new=None, deployment_source=deployment_source or ("environment" if "OMADA_CLIENT_SECRET" in os.environ else "repository_default"))
        gc_secret_versions(db)
        return generation, True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clear managed Controller secret; service must already be stopped.")
    parser.add_argument("operation", choices=["clear-omada-client-secret"])
    parser.add_argument("--expected-generation", required=True, type=int)
    args = parser.parse_args(argv)
    if args.expected_generation < 0:
        parser.error("expected generation must be nonnegative")
    try:
        filesystem = SecretFilesystem()
        filesystem.validate_db(SETTINGS_DB_PATH)
        generation, changed = clear_managed_secret(SettingsRepository.open_existing_v3(SETTINGS_DB_PATH), args.expected_generation, filesystem=filesystem)
        print(f"configured_generation={generation} changed={str(changed).lower()}")
        return 0
    except SettingsError as error:
        print(error.code)
        return 1
    except Exception:
        print("controller_secret_store_unavailable")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
