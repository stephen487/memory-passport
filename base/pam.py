"""PAM v1.0 helpers: schema check against the vendored PAM schema, content hash, integrity checksum.

Standard library only. PAM (Portable AI Memory) is https://github.com/portable-ai-memory/portable-ai-memory ;
its schema is vendored UNCHANGED in spec/pam/ under Apache-2.0 (see spec/pam/SOURCE.md). The hashing and the
canonical JSON below are written fresh from the PAM spec text (sections 6 and 15); no PAM code is copied.

What is checked here, and what is not:
- CHECKED: the whole PAM v1.0 memory-store schema (through this kit's small checker), content_hash of every
  memory, id uniqueness, custom_type rule, superseded_by / relation references, integrity.total_memories and
  integrity.checksum.
- NOT CHECKED: signatures (PAM section 18; needs a crypto library), conversation files and embeddings files
  (separate PAM schemas, not part of a passport), and PAM's own reference validator's remaining checks
  (temporal ordering, platform consistency).
"""
import hashlib
import json
import pathlib
import re
import unicodedata

from base.schema_check import Checker

KIT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PAM_SCHEMA_PATH = KIT_ROOT / "spec" / "pam" / "portable-ai-memory.schema.json"


def load_pam_schema():
    return json.loads(PAM_SCHEMA_PATH.read_text(encoding="utf-8"))


def normalize_content(text):
    """PAM section 6.1: trim, lowercase, NFC, collapse runs of spaces to one."""
    t = unicodedata.normalize("NFC", text.strip().lower())
    return re.sub(" {2,}", " ", t)


def content_hash(text):
    return "sha256:" + hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


def canonical_json(obj):
    """RFC 8785 (JCS) bytes for the JSON this kit produces: strings, integers, booleans, null, objects, lists, and
    floats that print the same in Python and in ECMAScript (the common case). Raises ValueError for a float whose
    form could differ (very large or very small), rather than guess."""
    def enc(v):
        if v is None:
            return "null"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")):
                raise ValueError("NaN/Infinity are not JSON")
            if v == int(v) and abs(v) < 1e21:
                return str(int(v))
            if not (1e-6 <= abs(v) < 1e21):
                raise ValueError("float outside the range this canonicaliser handles: " + repr(v))
            return repr(v)
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, list):
            return "[" + ",".join(enc(x) for x in v) + "]"
        if isinstance(v, dict):
            order = [k for _, k in sorted((k.encode("utf-16-be"), k) for k in v)]
            return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + enc(v[k]) for k in order) + "}"
        raise ValueError("not JSON: " + type(v).__name__)
    return enc(obj).encode("utf-8")


def integrity_checksum(memories):
    """PAM section 15.2: sort memories by id, canonicalise, SHA-256."""
    ordered = [m for _, _, m in sorted((m["id"], i, m) for i, m in enumerate(memories))]
    return "sha256:" + hashlib.sha256(canonical_json(ordered)).hexdigest()


def with_integrity(doc):
    """Return doc with `integrity` recomputed for its memories."""
    doc["integrity"] = {"canonicalization": "RFC8785", "checksum": integrity_checksum(doc["memories"]),
                        "total_memories": len(doc["memories"])}
    return doc


def validate_pam(doc):
    """Errors against PAM v1.0 itself (empty list = a valid PAM document, within the limits in the docstring)."""
    schema = load_pam_schema()
    errors = Checker().errors(doc, schema)
    if errors:
        return errors   # the checks below assume a well-formed document
    ids = [m["id"] for m in doc["memories"]]
    for i, m in enumerate(doc["memories"]):
        p = f"memories[{i}]"
        if content_hash(m["content"]) != m["content_hash"]:
            errors.append(f"{p}.content_hash - does not match the content (PAM section 6)")
        if (m["type"] == "custom") != bool(m.get("custom_type")):
            errors.append(f"{p}.custom_type - must be set exactly when type is 'custom'")
        sup = m["temporal"].get("superseded_by")
        if sup and sup not in ids:
            errors.append(f"{p}.temporal.superseded_by - refers to a memory that is not in the file")
    if len(set(ids)) != len(ids):
        errors.append("memories - duplicate id")
    for i, r in enumerate(doc.get("relations", [])):
        for end in ("from", "to"):
            if r[end] not in ids:
                errors.append(f"relations[{i}].{end} - refers to a memory that is not in the file")
    integ = doc.get("integrity")
    if integ:
        if integ["total_memories"] != len(doc["memories"]):
            errors.append("integrity.total_memories - does not equal the number of memories")
        try:
            if integ["checksum"] != integrity_checksum(doc["memories"]):
                errors.append("integrity.checksum - does not match the memories (PAM section 15)")
        except ValueError as exc:
            errors.append("integrity.checksum - could not be recomputed here (" + str(exc) + ")")
    return errors
