"""Passport profile 1.0 for PAM v1.0: validator, visibility report, front page view and `share`.

Standard library only. No network, no model. Command line (from the kit root):

    python -m base.mechanism validate FILE     # PAM v1.0 part, then the Passport profile part
    python -m base.mechanism report   FILE     # which memories are private, public, or private+consent
    python -m base.mechanism share    FILE [-o OUT]
    python -m base.mechanism seal     FILE [-o OUT]   # recompute content_hash and integrity after hand edits

A Passport is a PAM v1.0 document. PAM's rules are checked by base/pam.py against PAM's own schema (vendored in
spec/pam/). The profile's rules are in spec/passport-profile.schema.json (per-memory shape) and in
`profile_checks` below (rules across memories). See spec/SPEC.md.
"""
import argparse
import copy
import datetime
import hashlib
import json
import pathlib
import sys
import uuid

from base import pam
from base.schema_check import Checker

KIT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROFILE_SCHEMA_PATH = KIT_ROOT / "spec" / "passport-profile.schema.json"
PAM_ID = "https://schemas.portable-ai-memory.org/v1.0/memory-store.schema.json"
PROFILE_VERSION = "1.0"
_SHARE_NS = uuid.UUID("2d6f2a3e-5b8a-4f43-9d4e-6f0f8c2a7b11")

# R13: the sections a Passport accounts for. Each is present (has entries), declared empty by the human, or withheld.
SECTION_NAMES = ["corrections", "promises", "standing_rules", "human_line", "places", "routines", "running_jokes"]
_ROLE_SECTION = {"correction": "corrections", "promise": "promises", "standing_rule": "standing_rules",
                 "human_line": "human_line"}
_CUSTOM_SECTION = {"place": "places", "routine": "routines", "running_joke": "running_jokes"}
CHAINED = ("correction", "promise")             # R12, R17: travel as a full chain of versions
LATEST_ONLY = tuple(_CUSTOM_SECTION)            # R17: place, routine, running_joke travel as the latest version only


def load_profile_schema():
    return json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))


# --- reading a passport ---------------------------------------------------------------------------

def x(m):
    """The memory's metadata.x_passport block, or {}."""
    meta = m.get("metadata") if isinstance(m, dict) else None
    block = meta.get("x_passport") if isinstance(meta, dict) else None
    return block if isinstance(block, dict) else {}


def role(m):
    return x(m).get("role")


def kind(m):
    """A label for a memory: its profile role, else its custom type, else its PAM type."""
    return role(m) if role(m) not in (None, "memory") else (m.get("custom_type") or m.get("type"))


def memories(doc):
    ms = doc.get("memories") if isinstance(doc, dict) else None
    return [m for m in ms if isinstance(m, dict)] if isinstance(ms, list) else []


def verbatim_hash(text):
    """T1: SHA-256 of the exact UTF-8 text. No trimming, no case folding, no Unicode normalising: any change to the
    words changes the hash. (PAM's own content_hash is normalised and is recomputed by `seal`, so it cannot do this.)"""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def capture_record(text, note_text=None):
    """The x_passport.capture block for a correction, taken at the moment of capture."""
    out = {"verbatim_sha256": verbatim_hash(text)}
    if note_text is not None:
        out["note_sha256"] = verbatim_hash(note_text)
    return out


def section_of(m):
    """R13: the section a memory belongs to, or None (front page, facts, preferences and unknown kinds have none)."""
    r = role(m)
    if r in _ROLE_SECTION:
        return _ROLE_SECTION[r]
    return _CUSTOM_SECTION.get(m.get("custom_type")) if m.get("type") == "custom" else None


def promise_status(m):
    return x(m).get("promise_status")


def has_consent(m):
    c = x(m).get("consent_to_share")
    return isinstance(c, dict) and c.get("given_by") == "human" and bool(c.get("at"))


def _access(m):
    a = m.get("access")
    return a if isinstance(a, dict) else {}


def is_shareable(m):
    """The one rule. Private by default: a missing or unknown flag never travels.

    - access.exportable == false never leaves (PAM section 21.1), whatever else is true.
    - The profile marker always travels (it holds no personal data).
    - public travels. private or shared travels only with the human's consent recorded on THIS memory.
    - A paired_handle travels only when public: the handle is how the human is found.
    - A promise travels only while it is open; a kept or released one stays behind unless the human consented to it.
    """
    a = _access(m)
    if a.get("exportable") is False:
        return False
    if role(m) == "profile":
        return True
    vis = a.get("visibility")
    if role(m) == "promise" and promise_status(m) != "open" and not has_consent(m):
        return False   # R9: only OPEN promises travel by default; a kept or released one needs the human's say-so
    if vis == "public":
        return True
    if role(m) == "front_page.paired_handle":
        return False
    return vis in ("private", "shared") and has_consent(m)


# --- validation -----------------------------------------------------------------------------------

def _prefix(errors, label):
    return [f"{label}: {e}" for e in errors]


def validate_parts(doc):
    """Return (pam_errors, profile_errors). Both empty = a valid Passport."""
    pam_errors = pam.validate_pam(doc)
    schema = load_profile_schema()
    checker = Checker(registry={PAM_ID: pam.load_pam_schema()})
    overlay = schema["$defs"]["ProfileOverlay"]
    prof = checker.errors(doc, overlay, schema)
    memories_ok = isinstance(doc, dict) and isinstance(doc.get("memories"), list) \
        and all(isinstance(m, dict) for m in doc["memories"])
    if memories_ok:
        prof += profile_checks(doc)
    return pam_errors, prof


def validate(doc):
    pam_errors, prof = validate_parts(doc)
    return _prefix(pam_errors, "PAM") + _prefix(prof, "profile")


def profile_checks(doc):
    """Rules that span memories. Shape rules per memory are in the profile schema."""
    errs = []
    ms = doc["memories"]
    markers = [m for m in ms if role(m) == "profile"]
    if len(markers) != 1:
        errs.append(f"expected exactly one profile marker memory (role 'profile'), found {len(markers)}")
    shared = bool(markers and "shared_copy" in x(markers[0]))

    def active(r):
        return [m for m in ms if role(m) == r and m.get("status", "active") == "active"]

    names = active("front_page.name")
    if len(names) > 1 or (not names and not shared):
        errs.append(f"expected exactly one active front_page.name, found {len(names)}")
    for r in ("front_page.paired_handle", "front_page.motto"):
        if len(active(r)) > 1:
            errs.append(f"more than one active {r}")
    for i, m in enumerate(ms):
        how = (m.get("provenance") or {}).get("extraction_method")
        if role(m) == "standing_rule" and how not in ("explicit_user_input", "manual"):
            errs.append(f"memories[{i}] - a standing rule must be entered by the human "
                        "(provenance.extraction_method explicit_user_input or manual), not inferred")
        if role(m) == "correction" and x(m).get("verbatim_fidelity") == "human_words" and how == "llm_inference":
            errs.append(f"memories[{i}] - verbatim_fidelity is human_words but the text was inferred by a model")
        if role(m) == "correction":
            errs += [f"memories[{i}] - {e}" for e in capture_errors(m)]
        if role(m) == "human_line":
            if how not in ("explicit_user_input", "manual"):
                errs.append(f"memories[{i}] - a human_line must be entered by the human "
                            "(provenance.extraction_method explicit_user_input or manual), not inferred")
            if len(str(m.get("content", "")).strip().splitlines()) > 1:
                errs.append(f"memories[{i}] - a human_line is one line")
        b = x(m)
        who = (b.get("authored_by") or {}).get("role") if isinstance(b.get("authored_by"), dict) else None
        rev = b.get("human_review") if isinstance(b.get("human_review"), dict) else {}
        if who == "human" and how == "llm_inference":
            errs.append(f"memories[{i}] - authored by the human but inferred by a model "
                        "(provenance.extraction_method llm_inference): a model's inference is not the human's writing")
        if who == "human" and rev and rev.get("seen") is not True:
            errs.append(f"memories[{i}] - authored by the human, so the human has seen it: human_review.seen must be true")
    lines = [m for m in ms if role(m) == "human_line" and m.get("status", "active") == "active"]
    if len(lines) > 1:
        errs.append(f"expected at most one human_line, found {len(lines)}")
    errs += chain_errors(ms)
    errs += section_errors(ms, markers[0] if len(markers) == 1 else None)
    return errs


def chain_errors(ms):
    """R12 and R17: corrections and promises are chains. A replaced one names its replacement, the replacement names
    it back (`x_passport.replaces`), nothing is missing, nothing loops. A chain cut on purpose by `share` says so with
    `history_withheld`, and then has no `replaces` pointer."""
    errs = []
    ids = {m["id"]: m for m in ms if isinstance(m.get("id"), str)}
    for i, m in enumerate(ms):
        r = role(m)
        if r not in CHAINED:
            continue
        b = x(m)
        t = m.get("temporal") if isinstance(m.get("temporal"), dict) else {}
        sup = t.get("superseded_by")
        if m.get("status") == "superseded":
            if not sup:
                errs.append(f"memories[{i}] - a replaced {r} has no replacement named (temporal.superseded_by): "
                            f"it may only travel together with the {r} that replaced it")
            elif sup not in ids:
                errs.append(f"memories[{i}] - the replacement of this {r} is not in the file (a missing link in the chain)")
            elif role(ids[sup]) != r:
                errs.append(f"memories[{i}] - this {r} was replaced by a memory that is not a {r}")
            elif x(ids[sup]).get("replaces") != m.get("id"):
                errs.append(f"memories[{i}] - the replacement does not point back at the {r} it replaced "
                            "(x_passport.replaces), so the chain cannot be shown to be whole")
        elif sup:
            errs.append(f"memories[{i}] - {r} has temporal.superseded_by but its status is not superseded")
        rep = b.get("replaces")
        if rep is not None:
            if b.get("history_withheld"):
                errs.append(f"memories[{i}] - history_withheld and replaces together: say the earlier history is "
                            "withheld or point at it, not both")
            elif rep not in ids:
                errs.append(f"memories[{i}] - replaces {rep!r} which is not in the file (a missing link; if the "
                            "earlier history was held back on purpose, history_withheld says so)")
            elif role(ids[rep]) != r or ids[rep].get("status") != "superseded" \
                    or (ids[rep].get("temporal") or {}).get("superseded_by") != m.get("id"):
                errs.append(f"memories[{i}] - replaces a memory that does not record being replaced by it")
    for i, m in enumerate(ms):
        if role(m) not in CHAINED:
            continue
        seen, cur = set(), m
        while isinstance(cur, dict) and cur.get("status") == "superseded":
            if cur.get("id") in seen:
                errs.append(f"memories[{i}] - the chain of replacements loops back on itself")
                break
            seen.add(cur.get("id"))
            cur = ids.get((cur.get("temporal") or {}).get("superseded_by"))
    return errs


def section_errors(ms, marker):
    """R13: absent is not empty. Every section is exactly one of: present (has entries), declared empty by the human
    (`sections_empty`, who and when), or not shown (`sections_withheld`, a name and nothing else)."""
    errs = []
    if marker is None:
        return errs
    mk = x(marker)
    empty = mk.get("sections_empty") if isinstance(mk.get("sections_empty"), dict) else {}
    held = mk.get("sections_withheld") if isinstance(mk.get("sections_withheld"), list) else []
    counts = {n: 0 for n in SECTION_NAMES}
    for m in ms:
        s = section_of(m)
        if s:
            counts[s] += 1
        if role(m) != "profile" and ("sections_empty" in x(m) or "sections_withheld" in x(m)):
            errs.append("sections_empty and sections_withheld belong on the profile marker only")
    for n in SECTION_NAMES:
        e, w = n in empty, n in held
        if e and w:
            errs.append(f"section {n!r} is marked both empty by the human and withheld; it can be only one")
        if counts[n] and (e or w):
            errs.append(f"section {n!r} has entries but is marked {'empty' if e else 'withheld'}")
        if not counts[n] and not e and not w:
            errs.append(f"section {n!r} is empty and not marked: absent is not empty. Say the human has none "
                        "(sections_empty, declared by the human) or that it was not shown (sections_withheld)")
    return errs


def _squash(s):
    return " ".join(str(s).lower().split())


def capture_errors(m):
    """T1, joffrey's merge test: the verbatim text and the companion's note must still be what they were when the
    correction was captured, and the note must still be its own field.

    - verbatim text hashed at capture (exact bytes) must still match: catches a note folded into the text, and any
      softening, re-casing or trimming of the human's words;
    - a companion_note present must have been hashed at capture, and a note hashed at capture must still be there
      and unchanged: catches the notes field being deleted (with or without appending it to the verbatim field);
    - the note text must not sit inside the verbatim text: catches a merge where the app also rewrote the hash.
    Not caught: an app that rewrites the hash AND deletes the note AND its hash. Only a signature (PAM section 18,
    not built here) can rule that out. See spec/SPEC.md."""
    b = x(m)
    cap = b.get("capture")
    if not isinstance(cap, dict) or "verbatim_sha256" not in cap:
        return []   # the schema reports a missing capture record
    errs = []
    content = m.get("content", "")
    if verbatim_hash(content) != cap["verbatim_sha256"]:
        errs.append("correction: the verbatim text has changed since capture (content no longer matches "
                    "capture.verbatim_sha256), so it was edited or merged with something else")
    note = b.get("companion_note")
    has_note = isinstance(note, dict) and isinstance(note.get("text"), str)
    if "note_sha256" in cap and not has_note:
        errs.append("correction: companion_note is missing but was recorded at capture (capture.note_sha256), "
                    "so the notes field was deleted or merged into the verbatim text")
    if has_note and "note_sha256" not in cap:
        errs.append("correction: companion_note has no capture.note_sha256, so it cannot be shown to be separate")
    if has_note and "note_sha256" in cap and verbatim_hash(note["text"]) != cap["note_sha256"]:
        errs.append("correction: companion_note has changed since capture (no longer matches capture.note_sha256)")
    if has_note and len(_squash(note["text"])) >= 20 and _squash(note["text"]) in _squash(content):
        errs.append("correction: the companion's note appears inside the verbatim text; "
                    "the note must stay in its own field")
    return errs


# --- views ----------------------------------------------------------------------------------------

def front_page(doc):
    """R5: the front page, read from the memories. Former names are superseded or archived name memories."""
    out = {"name": None, "former_names": [], "paired_handle": None, "motto": None}
    for m in memories(doc):
        r, b = role(m), x(m)
        live = m.get("status", "active") == "active"
        if r == "front_page.name":
            entry = {"spelling": b.get("spelling"), "pronunciation": b.get("pronunciation")}
            if live:
                out["name"] = entry
            else:
                t = m.get("temporal", {})
                entry.update({"used_from": t.get("valid_from"), "used_until": t.get("valid_until")})
                out["former_names"].append(entry)
        elif r == "front_page.paired_handle" and live:
            out["paired_handle"] = b.get("handle")
        elif r == "front_page.motto" and live:
            out["motto"] = m.get("content")
    return out


def by_role(doc, r):
    """The memories with this profile role, in file order."""
    return [m for m in memories(doc) if role(m) == r]


def current_corrections(doc):
    """R8/R11: the corrections that are CURRENT. A superseded one is history, never read as current."""
    return [m for m in memories(doc) if role(m) == "correction" and m.get("status") == "active"]


def promises_to_carry(doc, closed_with_consent=False):
    """R9: the promises `share` carries. Open ones by default; kept or released ones only when the human consented
    to that one memory and the caller asks for them. (Visibility and exportable still apply, via is_shareable.)"""
    out = []
    for m in memories(doc):
        if role(m) != "promise" or not is_shareable(m):
            continue
        if promise_status(m) == "open" or (closed_with_consent and has_consent(m)):
            out.append(m)
    return out


def _label(i, m):
    text = " ".join(str(m.get("content", "")).split())
    return f"[{i}] {kind(m)}: {text[:26]}" + ("..." if len(text) > 26 else "")


def visibility_report(doc):
    """List of (label, flag, status): public, private, private+consent (will be shared), marker or withheld."""
    rows = []
    for i, m in enumerate(memories(doc)):
        a = _access(m)
        vis = a.get("visibility")
        flag = vis if vis in ("private", "shared", "public") else "private"
        if a.get("exportable") is False:
            status = "withheld"
        elif role(m) == "profile":
            status = "marker"
        elif role(m) == "promise" and promise_status(m) != "open" and not has_consent(m):
            status = "held"   # R9: a kept or released promise stays behind without the human's consent
        elif vis == "public":
            status = "public"
        elif is_shareable(m):
            status = flag + "+consent"
        else:
            status = flag
        rows.append((_label(i, m), flag, status))
    return rows


def format_report(doc):
    lines = [f"{'MEMORY':44}  {'FLAG':8}  STATUS"]
    for label, flag, status in visibility_report(doc):
        lines.append(f"{label:44}  {flag:8}  {status}")
    extra = unknown_metadata_keys(doc)
    if extra:
        lines.append("other metadata keys (kept with their memory): " + ", ".join(extra))
    return "\n".join(lines)


def unknown_metadata_keys(doc):
    """metadata keys that are neither PAM's (language, domain) nor ours (x_passport). They travel with the memory."""
    found = set()
    for m in memories(doc):
        meta = m.get("metadata")
        if isinstance(meta, dict):
            found |= set(meta) - {"language", "domain", "x_passport"}
    return sorted(found)


# --- share ----------------------------------------------------------------------------------------

def _old_version(m):
    """R17: a place, routine or running joke travels as its latest version only; an older one never does."""
    return m.get("type") == "custom" and m.get("custom_type") in LATEST_ONLY and m.get("status", "active") != "active"


def _close_chains(keep):
    """R12: a replaced correction or promise travels only with the one that replaced it, or not at all. Whatever
    cannot bring its replacement is dropped (and so is whatever was replaced by that, down the chain). A replacement
    may travel without what it replaced: it is the current one, and share then marks `history_withheld` on it."""
    while True:
        ids = {m.get("id") for m in keep}
        left = [m for m in keep if not (role(m) in CHAINED and m.get("status") == "superseded"
                                        and (m.get("temporal") or {}).get("superseded_by") not in ids)]
        if len(left) == len(keep):
            return keep
        keep = left


def share(doc, now=None):
    """Return a NEW passport with every memory removed that the human has not made public or consented to.

    The input is never changed. Also dropped from the copy, because they could leak or would no longer be true:
    signature (it cannot be re-made without the key), conversations_index, per-memory platform ids,
    conversation/message refs, embedding refs and access grants. The integrity block is recomputed.
    The copy records how many memories were removed in the marker's x_passport.shared_copy, never what they were.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = copy.deepcopy(doc)
    before = out.get("memories", [])
    keep = [m for m in before if isinstance(m, dict) and is_shareable(m) and not _old_version(m)]
    keep = _close_chains(keep)
    kept_ids = {m.get("id") for m in keep}
    out["memories"] = keep
    for m in keep:
        prov = m.get("provenance")
        if isinstance(prov, dict):
            for k in ("platform_user_id", "conversation_ref", "message_ref"):
                prov.pop(k, None)
        if "embedding_ref" in m:
            m["embedding_ref"] = None
        if isinstance(m.get("access"), dict) and "shared_with" in m["access"]:
            m["access"]["shared_with"] = []
        t = m.get("temporal")
        if isinstance(t, dict) and t.get("superseded_by") not in (None, *kept_ids):
            t["superseded_by"] = None
    if "relations" in out:
        out["relations"] = [r for r in out["relations"] if r.get("from") in kept_ids and r.get("to") in kept_ids]
    for key in ("conversations_index", "signature"):
        out.pop(key, None)
    for m in keep:
        if role(m) in CHAINED and x(m).get("replaces") not in (None, *kept_ids):
            m["metadata"]["x_passport"].pop("replaces")
            m["metadata"]["x_passport"]["history_withheld"] = True   # R17: say the earlier history was held back
    counts = {n: 0 for n in SECTION_NAMES}
    for m in keep:
        if section_of(m):
            counts[section_of(m)] += 1
    for m in keep:
        if role(m) == "profile":
            b = m["metadata"]["x_passport"]
            b["shared_copy"] = {"made_at": stamp, "fields_removed": len(before) - len(keep)}
            declared = b.get("sections_empty") if isinstance(b.get("sections_empty"), dict) else {}
            # R13: a section with nothing left is never left empty. The human's "none" stays; the rest is named, not shown.
            b["sections_withheld"] = [n for n in SECTION_NAMES if not counts[n] and n not in declared]
    out["export_id"] = str(uuid.uuid5(_SHARE_NS, f"{doc.get('export_id')}|{stamp}"))
    out["export_date"] = stamp
    out["export_type"] = "full"
    pam.with_integrity(out)
    return out


def seal(doc):
    """Recompute every content_hash and the integrity block (after hand edits). Returns a new document."""
    out = copy.deepcopy(doc)
    for m in out["memories"]:
        m["content_hash"] = pam.content_hash(m["content"])
    return pam.with_integrity(out)


# --- command line ---------------------------------------------------------------------------------

def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="mechanism", description="Passport profile 1.0 for PAM v1.0")
    ap.add_argument("command", choices=["validate", "report", "share", "seal"])
    ap.add_argument("file")
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    try:
        doc = _load(args.file)
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.file}: {exc}")
        return 2
    if args.command == "seal":
        ok = (isinstance(doc, dict) and isinstance(doc.get("memories"), list)
              and all(isinstance(m, dict) and isinstance(m.get("content"), str) and isinstance(m.get("id"), str)
                      for m in doc["memories"]))
        if not ok:
            print(f"cannot seal {args.file}: needs memories with id and content")
            return 1
        text = json.dumps(seal(doc), indent=2, ensure_ascii=False) + "\n"
        if args.out:
            pathlib.Path(args.out).write_text(text, encoding="utf-8")
            print(f"wrote sealed copy to {args.out}")
        else:
            print(text, end="")
        return 0
    pam_errors, prof_errors = validate_parts(doc)
    if args.command == "validate":
        print(("PAM v1.0: VALID   " if not pam_errors else "PAM v1.0: INVALID ") + args.file)
        for e in pam_errors:
            print("  " + e)
        print(("Profile:  VALID   " if not prof_errors else "Profile:  INVALID ") + args.file)
        for e in prof_errors:
            print("  " + e)
        return 1 if (pam_errors or prof_errors) else 0
    if pam_errors or prof_errors:
        print(f"INVALID {args.file} (fix before {args.command})")
        for e in _prefix(pam_errors, "PAM") + _prefix(prof_errors, "profile"):
            print("  " + e)
        return 1
    if args.command == "report":
        print(format_report(doc))
        return 0
    text = json.dumps(share(doc), indent=2, ensure_ascii=False) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote shareable copy to {args.out}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
