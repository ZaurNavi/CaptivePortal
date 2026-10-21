from __future__ import annotations
import os, sys, subprocess, json
from dataclasses import replace
from pathlib import Path

REPO = Path(r"C:\CaptivPortal-UI-Preview")
EXPECTED_HEAD = "c997e53876bc70cc57e16d6082cc79a1161b5217"
EXPECTED_TREE = "a80e90f7a00e934e853a90516781a5882620d072"

os.chdir(REPO)
sys.path.insert(0, str(REPO))

from app.admin_web.historical_traffic_serialization import (
    HistoricalTrafficSerializationError,
    serialize_historical_traffic,
)
from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
from app.analytics import HistoricalTrafficApPopulation
from tests.admin_web.conftest import SITE_ID
from tests.admin_web.test_traffic_ap import _product
from tests.admin_web.test_traffic_history import EVALUATED, _result
from tests.admin_web.test_traffic_peak import _peak_result


def git(*args):
    p = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(p.stdout + p.stderr)
    return p.stdout.strip()


def supported_product(base):
    template_product = _product(base=base)
    template_item = template_product.items[0]
    items = []
    for index in range(12):
        mac = f"02:00:00:00:00:{index:02X}"
        prefix = f"AP-{index + 1:02d}-"
        name = prefix + ("X" * (256 - len(prefix)))
        items.append(replace(
            template_item,
            ap_mac=mac,
            display_name=name,
            display_name_source="current",
        ))
    return replace(
        template_product,
        population=HistoricalTrafficApPopulation(12, 12, 12, 12, 12, True),
        items=tuple(items),
    )


head = git("rev-parse", "HEAD")
tree = git("rev-parse", "HEAD^{tree}")
print(f"HEAD={head}")
print(f"TREE={tree}")
if head != EXPECTED_HEAD or tree != EXPECTED_TREE:
    raise SystemExit("FAIL: exact artifact mismatch")
if git("status", "--porcelain=v1"):
    raise SystemExit("FAIL: Preview worktree dirty")

base = _peak_result(_result("7d", evaluated=EVALUATED))
product = supported_product(base)
combined = replace(base, ap_traffic=product)
resolved = resolve_traffic_network_range("7d", EVALUATED)

print("SERIALIZER_INPUT:")
print(f"  SITE_BUCKETS={len(base.buckets)}")
print(f"  AP_ITEMS={len(product.items)}")
print(f"  NAME_LENGTHS={sorted(set(len(i.display_name) for i in product.items))}")
print(f"  POPULATION={product.population}")
print(f"  SNAPSHOT={product.current_snapshot}")
print()

try:
    result = serialize_historical_traffic(
        combined,
        SITE_ID,
        resolved_range=resolved,
        include_period_statistics=True,
        include_peak_load=True,
        include_ap_traffic=True,
    )
except HistoricalTrafficSerializationError as exc:
    print(f"SERIALIZER_RESULT=FAIL")
    print(f"EXACT_ERROR={type(exc).__name__}: {exc}")
    raise SystemExit(2)

envelope = {
    "api_version": "admin.read.v1",
    "request_id": "00000000-0000-4000-8000-000000000000",
    "site_id": SITE_ID,
    "result": result,
    "page": None,
}
body = json.dumps(
    envelope,
    allow_nan=False,
    ensure_ascii=True,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")

print("SERIALIZER_RESULT=PASS")
print(f"SERIALIZED_BYTES={len(body)}")
print(f"LIMIT_75_PERCENT=786432")
print(f"HEADROOM={786432-len(body)}")
