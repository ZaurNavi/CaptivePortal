"""Disposable knowledge input builders. All matching uses production code."""
import json
from pathlib import Path
from app.network_service_recognition.artifacts import load_bundle
from app.network_service_recognition.canonical import canonical_json, content_digest

KNOWLEDGE = Path(__file__).parents[2] / "app/network_service_recognition/knowledge"
NAMES = ("recognition-taxonomy-v1.json", "recognition-knowledge-manifest-v1.json", "recognition-ruleset-v1.json")
AT = "2026-10-12T00:00:00.000000Z"


def documents():
    return [json.loads(KNOWLEDGE.joinpath(name).read_bytes()) for name in NAMES]


def encode(documents):
    taxonomy, manifest, ruleset = documents
    for document, kind in ((taxonomy, "taxonomy"), (manifest, "knowledge_manifest")):
        document[kind + "_digest_sha256"] = content_digest(document, kind + "_digest_sha256")
        for suffix in ("_id", "_version", "_digest_sha256"):
            ruleset[kind + suffix] = document[kind + suffix]
    ruleset["ruleset_digest_sha256"] = content_digest(ruleset, "ruleset_digest_sha256")
    return tuple(canonical_json(document) for document in documents)


def bundle():
    return load_bundle(*(KNOWLEDGE.joinpath(name).read_bytes() for name in NAMES))
