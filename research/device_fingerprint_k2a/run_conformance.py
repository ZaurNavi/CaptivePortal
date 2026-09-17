"""Replay retained evidence and compare K2A matcher with pinned p0f 3.09b.

Explicit local command only. The oracle, archive, and p0f.fp stay outside the
repository. All packets are synthetic and no root, network, or capture is used.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import ipaddress
import json
import re
import struct
import subprocess
import sys
import types
from pathlib import Path

EXPECTED = {
    "p0f_3.09b.orig.tar.gz": "543b68638e739be5c3e818c3958c3b124ac0ccb8be62ba274b4241dbdec00e7f",
    "p0f-3.09b/p0f.fp": "45f27bcc65de0f64bc69356dc0662e3366e05e67a0e98fd2251808e253b6be40",
    "p0f-3.09b/p0f": "81ac7a7851980afd1f825b15e7ab4655a221f23b8f99d3c337c49752242811d3",
}
SCOPE = (
    "IPv4 outbound/request-side initial TCP SYN semantics derived exclusively "
    "from validated tcp_syn/2 evidence for pinned p0f 3.09b request matcher conformance"
)
SELECTED = (
    "base", "eol_early", "eol_final", "eol_zero", "mss_1200_bad", "mss_1460_bad",
    "mss_tail_nops", "ws_14", "ws_15", "ws_bad_255", "ts_bad_3", "ts_bad_8",
    "ns_absent", "ns_present", "ece", "cwr", "ip_ecn", "df_id_zero",
    "df_id_nonzero", "no_df_id_zero", "ip_reserved", "seq_zero", "ack_first_even",
    "ack_first_odd_one_bit", "urg_pointer", "urg_flag", "push_flag", "ttl_63",
    "ttl_65", "win_zero", "win_1460", "ip_options_zero", "payload_one",
    "mss_len4_phys2", "sok_len2_phys0", "ts_len10_phys8", "unknown_len2_phys3",
)
GUEST = (ipaddress.ip_network("192.0.2.0/24"),)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def load_repo(repo: Path):
    # WSL oracle hosts need not carry Flask/production web dependencies.
    package = types.ModuleType("app.device_fingerprint")
    package.__path__ = [str(repo / "app/device_fingerprint")]
    sys.modules[package.__name__] = package

    def load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Module unavailable: {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    load("app.device_fingerprint.models", repo / "app/device_fingerprint/models.py")
    network = load("app.device_fingerprint.network_schemas", repo / "app/device_fingerprint/network_schemas.py")
    semantics = load("app.device_fingerprint.p0f_semantics", repo / "app/device_fingerprint/p0f_semantics.py")
    sensor = load("k2a_sensor_parser", repo / "app/device_fingerprint_sensor/tcp_syn.py")
    return network.validate_tcp_syn_v2, semantics, sensor.parse_tcp_syn_frame


def oracle(binary: Path, pcap: Path, fp: Path) -> tuple[str | None, str]:
    result = subprocess.run([str(binary), "-r", str(pcap), "-f", str(fp)],
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode:
        raise RuntimeError(f"p0f oracle failed: {pcap.name}: {result.stderr}")
    output = result.stdout + result.stderr
    raw = re.search(r"\| raw_sig\s*=\s*([^\r\n]+)", output)
    return (raw.group(1).strip() if raw else None), output


def p0f_signature_file(path: Path, signatures: list[tuple[str, str, bool]]) -> None:
    # A tiny generated conformance instrument, NOT an upstream fingerprint corpus.
    lines = ["classes = other", "", "[tcp:request]"]
    for identity, text, generic in signatures:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", identity):
            raise ValueError("Invalid fixture signature ID")
        lines += [f"label = {'g' if generic else 's'}:other:{identity}:", f"sig = {text}", ""]
    path.write_text("\n".join(lines), encoding="ascii")


def oracle_match(output: str, identities: list[str]) -> dict[str, object]:
    os_match = re.search(r"\| os\s*=\s*([^\r\n]+)", output)
    dist_match = re.search(r"\| dist\s*=\s*(?:<=\s*)?([0-9]+)", output)
    params_match = re.search(r"\| params\s*=\s*([^\r\n]+)", output)
    if os_match is None or dist_match is None or params_match is None:
        raise RuntimeError("Unparseable p0f oracle match output")
    name = os_match.group(1).strip()
    if name == "???":
        return {"status": "NO_MATCH", "signature_id": None, "match_quality": None,
                "signature_kind": None, "distance": None}
    matched = [identity for identity in identities if identity in name]
    if len(matched) != 1:
        raise RuntimeError(f"Unparseable p0f signature identity: {name}")
    params = params_match.group(1).split()
    return {
        "status": "MATCH", "signature_id": matched[0],
        "match_quality": "fuzzy" if "fuzzy" in params else "exact",
        "signature_kind": "generic" if "generic" in params else "specific",
        "distance": int(dist_match.group(1)),
    }


def changed_window(source: Path, target: Path, window: int) -> None:
    packet = bytearray(source.read_bytes())
    # pcap global(24) + record(16) + Ethernet(14) + IPv4 header(IHL) + TCP(14)
    tcp = 40 + 14 + (packet[40 + 14] & 15) * 4
    struct.pack_into("!H", packet, tcp + 14, window)
    target.write_bytes(packet)


def assert_adapter_equals_oracle_raw(runtime: dict, raw: str, identity: str) -> None:
    """Cross-check all reconstructible raw_sig fields over retained vectors."""
    parts = raw.split(":")
    if len(parts) != 8 or parts[0] != "4":
        raise RuntimeError(f"Unparseable retained raw signature: {identity}")
    tokens = []
    for kind in runtime["option_kinds"]:
        if kind == 0:
            tokens.append(f"eol+{runtime['eol_padding_length']}")
        else:
            tokens.append({1: "nop", 2: "mss", 3: "ws", 4: "sok", 5: "sack", 8: "ts"}.get(kind, f"?{kind}"))
    expected = (
        int(parts[2]) == runtime["ip_option_length"]
        and int(parts[3]) == runtime["mss"]
        and (
            not re.fullmatch(r"[0-9]+,[0-9]+", parts[4])
            or tuple(map(int, parts[4].split(","))) == (runtime["window"], runtime["scale"])
        )
        and parts[5] == ",".join(tokens)
        and (set(parts[6].split(",")) if parts[6] else set()) == set(runtime["quirks"])
        and (0 if parts[7] == "0" else 1 if parts[7] == "+" else -1) == runtime["payload_class"]
    )
    if not expected:
        raise RuntimeError(f"K2A adapter / retained p0f raw_sig mismatch: {identity}")


def run(root: Path, repo: Path, evidence: Path) -> dict[str, object]:
    for relative, expected in EXPECTED.items():
        source = root / relative
        if not source.is_file() or sha(source.read_bytes()) != expected:
            raise RuntimeError(f"Pinned oracle artifact drift: {relative}")
    validate, semantics, parse = load_repo(repo)
    corpus = root / "full_gap_audit"
    manifest_path = corpus / "fixture_manifest.jsonl"
    entries = [json.loads(line) for line in manifest_path.read_text().splitlines()]
    if len(entries) != 544 or len({entry["fixture_id"] for entry in entries}) != 544:
        raise RuntimeError("Missing or duplicate retained evidence fixture")
    binary, upstream_fp = root / "p0f-3.09b/p0f", root / "p0f-3.09b/p0f.fp"
    canonical: dict[str, str] = {}
    validated: dict[str, dict] = {}
    oracle_raw: dict[str, str | None] = {}
    collisions = 0
    for entry in entries:
        identity = entry["fixture_id"]
        packet_path = corpus / f"{identity}.pcap"
        packet = packet_path.read_bytes()
        if sha(packet) != entry["packet_sha256"]:
            raise RuntimeError(f"Retained PCAP digest mismatch: {identity}")
        raw, _ = oracle(binary, packet_path, upstream_fp)
        if raw != entry["oracle_raw_sig"]:
            raise RuntimeError(f"Retained oracle output changed: {identity}")
        parsed = parse(packet[40:], GUEST)
        value = validate(parsed[2]) if parsed is not None else None
        if value != entry["tcp_syn_v2"]:
            raise RuntimeError(f"Retained canonical payload changed: {identity}")
        oracle_raw[identity] = raw
        if value is None:
            continue
        validated[identity] = value
        if raw is not None:
            assert_adapter_equals_oracle_raw(semantics.adapt_tcp_syn_v2(value), raw, identity)
        key = sha(encoded(value))
        previous = canonical.setdefault(key, raw or "")
        if previous != (raw or ""):
            collisions += 1
    if collisions:
        raise RuntimeError(f"Evidence collisions: {collisions}")
    evidence.mkdir(parents=True, exist_ok=True)
    work_fp = root / "k2a_conformance_work.fp"
    cases: list[dict[str, object]] = []
    vectors = [(identity, corpus / f"{identity}.pcap", oracle_raw[identity])
               for identity in SELECTED]
    # Additional synthetic PCAPs exercise MSS/MTU/modulo on actual p0f.
    for label, source_name, window in (
        ("mss_multi", "mss_len4_phys2", 2400),
        ("mss_multi_bad", "mss_1200_bad", 2400),
        ("mtu_multi", "mss_len4_phys2", 2480),
        ("modulo", "mss_len4_phys2", 2500),
    ):
        target = evidence / f"{label}.pcap"
        changed_window(corpus / f"{source_name}.pcap", target, window)
        vectors.append((label, target, None))
    for identity, pcap, reference_raw in vectors:
        packet = pcap.read_bytes()
        parsed = parse(packet[40:], GUEST)
        if parsed is None:
            raise RuntimeError(f"Required synthetic fixture not parsed: {identity}")
        value = validate(parsed[2])
        runtime = semantics.adapt_tcp_syn_v2(value)
        if reference_raw is None:
            reference_raw, _ = oracle(binary, pcap, upstream_fp)
        if reference_raw is None:
            raise RuntimeError(f"Missing reference raw signature: {identity}")
        # raw_sig uses +? when the unknown-host distance cannot be guessed;
        # +? is display syntax, not accepted p0f.fp signature grammar.
        sig_text = reference_raw.replace("+?", "")
        if identity in {"mss_multi", "mss_multi_bad"}:
            sig_text = sig_text.replace("2400,0", "mss*2,0")
        elif identity == "mtu_multi":
            sig_text = sig_text.replace("2480,0", "mtu*2,0")
        elif identity == "modulo":
            sig_text = sig_text.replace("2500,0", "%500,0")
        identity_tag = f"k2a_{identity}"
        variants = [("exact", [(identity_tag, sig_text, False)])]
        if identity == "base":
            parts = sig_text.split(":")
            generic = parts.copy()
            generic[4] = "*,0"
            ttl_distance = parts.copy()
            ttl_distance[1] = "64+1"
            ttl_fuzzy = parts.copy()
            ttl_fuzzy[1] = "128"
            ttl_bad = parts.copy()
            ttl_bad[1] = "64-"
            scale_wildcard = parts.copy()
            scale_wildcard[4] = scale_wildcard[4].split(",")[0] + ",*"
            mss_wildcard = parts.copy()
            mss_wildcard[3] = "*"
            payload_wildcard = parts.copy()
            payload_wildcard[7] = "*"
            variants += [
                ("specific_generic", [("k2a_generic", ":".join(generic), True),
                                      ("k2a_specific", sig_text, False)]),
                ("generic_only", [("k2a_generic", ":".join(generic), True)]),
                ("ttl_distance", [("k2a_ttldistance", ":".join(ttl_distance), False)]),
                ("ttl_fuzzy", [("k2a_ttlfuzzy", ":".join(ttl_fuzzy), False)]),
                ("ttl_badttl", [("k2a_badttl", ":".join(ttl_bad), False)]),
                ("scale_wildcard", [("k2a_scalewild", ":".join(scale_wildcard), False)]),
                ("mss_wildcard", [("k2a_msswild", ":".join(mss_wildcard), False)]),
                ("payload_wildcard", [("k2a_payloadwild", ":".join(payload_wildcard), False)]),
                ("no_match", [("k2a_wrong", sig_text.replace(":12345,", ":12346,"), False)]),
                ("fuzzy", [("k2a_fuzzy", sig_text.replace("::0", ":df:0"), False)]),
            ]
        if identity == "mss_tail_nops":
            variants.append(("option_order_mismatch", [
                ("k2a_wrongorder", sig_text.replace("mss,nop", "nop,mss"), False),
            ]))
        for variant, definitions in variants:
            p0f_signature_file(work_fp, definitions)
            raw, output = oracle(binary, pcap, work_fp)
            if raw is None:
                raise RuntimeError(f"Oracle did not observe fixture: {identity}/{variant}")
            reference = oracle_match(output, [item[0] for item in definitions])
            signatures = [semantics.parse_request_signature(text, signature_id=name, generic=generic)
                          for name, text, generic in definitions]
            actual = dataclasses.asdict(semantics.match_request(runtime, signatures))
            status = "PASS" if actual == reference else "FAIL"
            case = {
                "fixture_id": f"{identity}/{variant}",
                "fixture_digest": sha(packet),
                "tcp_syn_v2": value, "tcp_syn_v2_digest": sha(encoded(value)),
                "adapter_output": {**runtime, "option_kinds": list(runtime["option_kinds"]),
                                   "quirks": sorted(runtime["quirks"])},
                "signature_set": definitions, "signature_set_digest": sha(encoded(definitions)),
                "oracle_invocation_identity": {
                    "binary_sha256": EXPECTED["p0f-3.09b/p0f"],
                    "pcap_sha256": sha(packet), "signature_set_sha256": sha(encoded(definitions)),
                },
                "oracle_output": output, "oracle_output_digest": sha(output.encode()),
                "oracle_match": reference, "matcher_output": actual,
                "comparison_status": status,
                "difference_explanation": None if status == "PASS" else f"expected={reference}, actual={actual}",
            }
            case["adapter_digest"] = sha(encoded(case["adapter_output"]))
            cases.append(case)
    report = {
        "retained_evidence": {"total": len(entries), "validation_failures": 0,
                              "collision_groups": collisions},
        "matcher": {"total": len(cases), "pass": sum(c["comparison_status"] == "PASS" for c in cases),
                    "fail": sum(c["comparison_status"] == "FAIL" for c in cases),
                    "skip": 0, "unexplained_mismatches": sum(c["comparison_status"] == "FAIL" for c in cases)},
    }
    (evidence / "conformance_manifest.jsonl").write_bytes(b"\n".join(encoded(c) for c in cases) + b"\n")
    (evidence / "comparison_report.json").write_bytes(encoded(report) + b"\n")
    fixture_digest = sha((evidence / "conformance_manifest.jsonl").read_bytes())
    package = {
        "p0f_implementation_identity": "p0f 3.09b pinned x86_64 binary",
        "p0f_implementation_digest": EXPECTED["p0f-3.09b/p0f"],
        "p0f_reference_corpus_identity": "p0f 3.09b upstream p0f.fp (external, not admitted)",
        "p0f_reference_corpus_digest": EXPECTED["p0f-3.09b/p0f.fp"],
        "supported_request_scope": SCOPE,
        "p0f_runtime_serializer_contract_version": semantics.RUNTIME_CONTRACT,
        "matcher_implementation_contract_version": semantics.MATCHER_CONTRACT,
        "conformance_fixture_refs": [{"fixture_set_id": "k2a_synthetic_ipv4_request_v1",
                                      "fixture_set_digest": fixture_digest}],
        "conformance_status": "PASS" if report["matcher"]["fail"] == report["matcher"]["skip"] == 0 else "FAIL",
    }
    (evidence / "K2AConformancePackage.candidate.json").write_bytes(encoded(package) + b"\n")
    if package["conformance_status"] != "PASS":
        raise RuntimeError(f"K2A oracle mismatch: {report}")
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--oracle-root", type=Path, required=True)
    cli.add_argument("--repo", type=Path, required=True)
    cli.add_argument("--evidence", type=Path, required=True)
    args = cli.parse_args()
    print(json.dumps(run(args.oracle_root, args.repo, args.evidence), sort_keys=True))
