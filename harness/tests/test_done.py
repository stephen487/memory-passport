"""Harness for the Passport profile for PAM v1.0. These tests define "done" for the base.

Passing tests prove what is built:
- PAM: the vendored PAM schema is unchanged; every example is a valid PAM v1.0 document (schema, content hashes,
  integrity checksum); a broken one fails for the right reasons.
- Profile: every example is valid for the profile; R1 to R7 (see ideas notes): verbatim corrections with the
  companion's reading apart; name + pronunciation + rename history; standing rules need the human's approval;
  private by default with per-field consent; front page; named memory kinds; history belongs to the relationship.
- Share: every private memory without the human's consent is gone, the input is never changed, the copy is still
  valid PAM and valid profile.
- Demo: its output matches the saved EXPECTED_OUTPUT.txt.

Tests that fail on purpose say NOT BUILT. Each is one item in BRIEF.md "What's left for you".
"""
import copy
import datetime
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys

import pytest

from base import mechanism, pam
from base.schema_check import Checker

KIT = pathlib.Path(__file__).resolve().parents[2]
EX = KIT / "examples"
GOOD = ["cooking-helper", "study-companion", "game-companion"]
NOW = datetime.datetime(2026, 11, 23, tzinfo=datetime.timezone.utc)


def load(name):
    return json.loads((EX / f"{name}.json").read_text(encoding="utf-8"))


def not_built(what):
    pytest.fail("NOT BUILT: " + what)


def all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from all_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_strings(v)


def find(doc, **want):
    """The memories whose role (and/or custom_type, id suffix) matches."""
    out = []
    for m in doc["memories"]:
        if "role" in want and mechanism.role(m) != want["role"]:
            continue
        if "custom_type" in want and m.get("custom_type") != want["custom_type"]:
            continue
        out.append(m)
    return out


def reseal(doc):
    return mechanism.seal(doc)


# --- PAM: the base --------------------------------------------------------------------------------------

def test_vendored_pam_schema_is_unchanged_and_licensed():
    pam_dir = KIT / "spec" / "pam"
    source = (pam_dir / "SOURCE.md").read_text(encoding="utf-8")
    raw = (pam_dir / "portable-ai-memory.schema.json").read_bytes().replace(b"\r\n", b"\n")   # git may add CRLF
    digest = hashlib.sha256(raw).hexdigest()
    assert digest in source, "vendored PAM schema differs from the recorded copy: it must stay unchanged"
    assert "Apache License" in (pam_dir / "LICENSE-CODE").read_text(encoding="utf-8")
    assert "Attribution 4.0" in (pam_dir / "LICENSE-SPEC").read_text(encoding="utf-8")


def test_pam_schema_loads_and_is_v1_0():
    schema = pam.load_pam_schema()
    assert schema["$id"].endswith("/v1.0/memory-store.schema.json")


@pytest.mark.parametrize("name", GOOD)
def test_example_is_valid_pam(name):
    assert pam.validate_pam(load(name)) == []


@pytest.mark.parametrize("name", GOOD)
def test_example_is_valid_profile(name):
    assert mechanism.validate_parts(load(name))[1] == []
    assert mechanism.validate(load(name)) == []


def test_content_hash_follows_pam_section_6():
    assert pam.content_hash("  Hello   WORLD ") == pam.content_hash("hello world")
    assert pam.content_hash("x").startswith("sha256:") and len(pam.content_hash("x")) == 71


def test_a_changed_content_fails_the_hash_check():
    doc = load("cooking-helper")
    doc["memories"][5]["content"] = "No, a LITTLE coriander is fine."
    assert any("content_hash" in e for e in pam.validate_pam(doc))


def test_a_wrong_integrity_checksum_is_caught():
    doc = load("cooking-helper")
    doc["integrity"]["checksum"] = "sha256:" + "0" * 64
    assert any("integrity.checksum" in e for e in pam.validate_pam(doc))


def test_a_removed_memory_breaks_the_integrity_count():
    doc = load("cooking-helper")
    del doc["memories"][-1]
    assert any("integrity" in e for e in pam.validate_pam(doc))


def test_custom_type_rule_from_pam_is_enforced():
    doc = load("cooking-helper")
    place = find(doc, custom_type="place")[0]
    place["custom_type"] = None
    assert pam.validate_pam(doc)


def test_superseded_by_must_point_at_a_memory_in_the_file():
    doc = load("cooking-helper")
    doc["memories"][2]["temporal"]["superseded_by"] = "00000000-0000-4000-8000-00000000dead"
    assert any("superseded_by" in e for e in pam.validate_pam(doc))


def test_seal_repairs_hashes_and_integrity_after_a_hand_edit():
    doc = load("cooking-helper")
    doc["memories"][5]["content"] = "No coriander at all, ever."
    assert pam.validate_pam(doc)
    assert pam.validate_pam(mechanism.seal(doc)) == []


def test_canonical_json_sorts_keys_and_drops_whitespace():
    assert pam.canonical_json({"b": 1, "a": [True, None, "é"]}) == '{"a":[true,null,"é"],"b":1}'.encode("utf-8")


# --- the deliberately invalid example -------------------------------------------------------------------

def test_invalid_example_fails_for_the_right_reasons():
    pam_errors, prof_errors = mechanism.validate_parts(load("INVALID-no-human-approval"))
    pam_text, prof_text = "\n".join(pam_errors), "\n".join(prof_errors)
    assert "created_at" in pam_text and "not a valid date-time" in pam_text      # PAM's own rule
    assert "access.visibility - must be one of" in pam_text                        # a bad flag is an error
    assert "missing required field 'access'" in prof_text                         # R4: flag spoken out loud
    assert "verbatim_fidelity" in prof_text                                       # R1
    assert "requires_human_approval - must be true" in prof_text                   # R3
    assert "approval.by" in prof_text                                             # R3: companion cannot approve
    assert "profile marker" in prof_text                                          # no marker memory
    assert "must be entered by the human" in prof_text                            # R3: inferred rule


def test_checker_refuses_a_schema_keyword_it_does_not_support():
    errors = Checker().errors({}, {"type": "object", "oneOf": []})
    assert any("not supported" in e for e in errors)


def test_examples_use_no_real_handle():
    for name in GOOD:
        text = json.dumps(load(name)).lower()
        assert "joffrey" not in text and "musefm" not in text


# --- R1: corrections verbatim, interpretation apart -----------------------------------------------------

def test_r1_companion_note_is_a_separate_labelled_field_and_content_stays_the_humans_words():
    c = [c for c in find(load("cooking-helper"), role="correction") if "coriander" in c["content"]
         and "companion_note" in c["metadata"]["x_passport"]][0]
    note = c["metadata"]["x_passport"]["companion_note"]
    assert c["content"] != note["text"]
    assert note["written_by"]["role"] == "companion"
    assert "coriander" in c["content"] and "Read as" not in c["content"]


def test_r1_fidelity_flag_is_required_on_a_correction():
    doc = load("cooking-helper")
    del find(doc, role="correction")[0]["metadata"]["x_passport"]["verbatim_fidelity"]
    assert any("verbatim_fidelity" in e for e in mechanism.validate(doc))


def test_r1_a_model_inferred_text_cannot_claim_to_be_human_words():
    doc = load("cooking-helper")
    find(doc, role="correction")[0]["provenance"]["extraction_method"] = "llm_inference"
    assert any("human_words" in e for e in mechanism.validate_parts(doc)[1])


def test_r1_share_never_alters_a_correction():
    doc = load("cooking-helper")
    shared = mechanism.share(doc)
    original = {c["id"]: c["content"] for c in find(doc, role="correction")}
    got = find(shared, role="correction")
    assert got
    for c in got:
        assert c["content"] == original[c["id"]]


def test_r1_a_correction_can_supersede_an_older_memory_using_pams_own_fields():
    doc = load("cooking-helper")
    old = [m for m in doc["memories"] if m["status"] == "superseded"][0]
    assert old["temporal"]["superseded_by"]          # PAM lifecycle, no new field of ours


# --- R2: name = spelling + pronunciation, renames are history -------------------------------------------

def test_r2_pronunciation_is_required():
    doc = load("game-companion")
    del find(doc, role="front_page.name")[0]["metadata"]["x_passport"]["pronunciation"]
    assert any("pronunciation" in e for e in mechanism.validate(doc))


def test_r2_rename_history_is_kept_with_pams_dates_and_status():
    fp = mechanism.front_page(load("cooking-helper"))
    assert fp["name"]["spelling"] == "Pippin"
    assert fp["former_names"] == [{"spelling": "Pip", "pronunciation": "PIP",
                                   "used_from": "2026-03-02T09:00:00Z", "used_until": "2026-05-19T10:00:00Z"}]


def test_r2_exactly_one_current_name():
    doc = load("cooking-helper")
    old = [m for m in doc["memories"] if m["status"] == "superseded"][0]
    old["status"] = "active"
    assert any("front_page.name" in e for e in mechanism.validate_parts(reseal(doc))[1])


# --- R3: standing rules need the human ------------------------------------------------------------------

def test_r3_rule_needs_human_approval_record():
    doc = load("study-companion")
    find(doc, role="standing_rule")[0]["metadata"]["x_passport"]["approval"]["by"] = "companion"
    assert any("approval.by" in e for e in mechanism.validate(doc))


def test_r3_rule_must_say_approval_is_required():
    doc = load("study-companion")
    find(doc, role="standing_rule")[0]["metadata"]["x_passport"]["requires_human_approval"] = False
    assert any("requires_human_approval" in e for e in mechanism.validate(doc))


def test_r3_action_class_is_limited_to_irreversible_kinds():
    doc = load("study-companion")
    find(doc, role="standing_rule")[0]["metadata"]["x_passport"]["action_class"] = "tone_of_voice"
    assert any("action_class" in e for e in mechanism.validate(doc))


def test_r3_a_rule_the_model_inferred_is_refused():
    doc = load("study-companion")
    find(doc, role="standing_rule")[0]["provenance"]["extraction_method"] = "llm_inference"
    assert any("entered by the human" in e for e in mechanism.validate_parts(doc)[1])


# --- R4: private by default -----------------------------------------------------------------------------

def test_r4_every_memory_must_state_its_visibility_even_though_pam_would_default_it():
    doc = load("game-companion")
    del doc["memories"][1]["access"]["visibility"]
    assert any("visibility" in e for e in mechanism.validate(reseal(doc)))


def test_r4_share_removes_private_without_consent():
    doc = load("cooking-helper")
    shared = mechanism.share(doc)
    texts = {m["content"] for m in shared["memories"]}
    assert not any("nut free" in t for t in texts)                     # private, no consent
    assert any("grams" in t for t in texts)                            # private WITH the human's consent
    assert {m["metadata"]["x_passport"]["action_class"] for m in find(shared, role="standing_rule")} == {"money"}


def test_r4_no_private_text_survives_anywhere_in_the_shared_copy():
    for name in GOOD:
        doc = load(name)
        shared_text = json.dumps(mechanism.share(doc), ensure_ascii=False)
        for m in doc["memories"]:
            if not mechanism.is_shareable(m):
                x = mechanism.x(m)
                for s in [m["content"], x.get("why_carried", ""), x.get("companion_note", {}).get("text", ""),
                          x.get("handle", "")]:
                    if len(s) > 12:
                        assert s not in shared_text, f"{name} leaked: {s[:30]}"


def test_r4_consent_must_be_given_by_the_human():
    doc = load("cooking-helper")
    c3 = [m for m in doc["memories"] if "nut free" in m["content"]][0]
    c3["metadata"]["x_passport"]["consent_to_share"] = {"given_by": "companion", "at": "2026-08-03"}
    assert not any("nut free" in m["content"] for m in mechanism.share(doc)["memories"])


def test_r4_a_consent_record_with_a_non_human_giver_is_invalid():
    doc = load("cooking-helper")
    c2 = [m for m in doc["memories"] if "grams" in m["content"]][0]
    c2["metadata"]["x_passport"]["consent_to_share"]["given_by"] = "companion"
    assert any("given_by" in e for e in mechanism.validate_parts(doc)[1])


def test_r4_missing_or_bad_flag_counts_as_private():
    doc = load("cooking-helper")
    pref = [m for m in doc["memories"] if m["type"] == "preference"][0]
    del pref["access"]["visibility"]
    pref["access"]["visibility"] = "maybe"
    assert not mechanism.is_shareable(pref)
    del pref["access"]
    assert not mechanism.is_shareable(pref)
    assert not any(m["type"] == "preference" for m in mechanism.share(doc)["memories"])


def test_r4_consent_is_per_memory_not_blanket():
    shared = mechanism.share(load("cooking-helper"))
    assert len(find(shared, role="correction")) == 2      # one public + one consented; the old and the third stay out


def test_r4_pam_exportable_false_never_leaves_even_when_public():
    doc = load("game-companion")
    locked = [m for m in doc["memories"] if m["access"]["exportable"] is False][0]
    assert locked["access"]["visibility"] == "public"
    assert not any(m["id"] == locked["id"] for m in mechanism.share(doc)["memories"])
    locked["metadata"] = {"x_passport": {"role": "memory", "consent_to_share": {"given_by": "human", "at": "2026-05-01"}}}
    assert not mechanism.is_shareable(locked)


def test_r4_shared_visibility_is_not_public():
    doc = load("game-companion")
    friend = [m for m in doc["memories"] if m["access"]["visibility"] == "shared"][0]
    assert not mechanism.is_shareable(friend)


def test_r4_share_does_not_change_its_input():
    doc = load("cooking-helper")
    before = copy.deepcopy(doc)
    mechanism.share(doc)
    assert doc == before


def test_r4_shared_copy_is_still_valid_pam_and_valid_profile_and_counts_removals():
    for name in GOOD:
        shared = mechanism.share(load(name), now=NOW)
        assert pam.validate_pam(shared) == [], name
        assert mechanism.validate_parts(shared)[1] == [], name
    shared = mechanism.share(load("cooking-helper"), now=NOW)
    assert mechanism.x(find(shared, role="profile")[0])["shared_copy"] == {"made_at": "2026-11-23T00:00:00Z",
                                                                             "fields_removed": 7}


def test_r4_share_strips_platform_ids_signature_and_conversation_index():
    doc = load("cooking-helper")
    doc["memories"][1]["provenance"]["platform_user_id"] = "user-12345-secret"
    doc["memories"][1]["provenance"]["conversation_ref"] = "conv-secret-77"
    doc["conversations_index"] = []
    doc["signature"] = {"export_id": "x", "export_date": "2026-01-01T00:00:00Z"}
    text = json.dumps(mechanism.share(doc))
    assert "user-12345-secret" not in text and "conv-secret-77" not in text
    assert "conversations_index" not in text and '"signature"' not in text


def test_r4_share_drops_relations_that_touch_a_removed_memory():
    doc = load("cooking-helper")
    ids = {m["id"]: m for m in doc["memories"]}
    private = [m for m in doc["memories"] if not mechanism.is_shareable(m)][0]
    public = [m for m in doc["memories"] if mechanism.is_shareable(m)][1]
    doc["relations"] = [{"id": "r-1", "from": private["id"], "to": public["id"], "type": "related_to",
                         "created_at": "2026-05-01T00:00:00Z"}]
    shared = mechanism.share(doc)
    assert shared["relations"] == [] and pam.validate_pam(shared) == [] and private["id"] in ids


def test_r4_report_lists_which_memories_are_private():
    rows = {label.split(":")[0]: status for label, _, status in mechanism.visibility_report(load("cooking-helper"))}
    statuses = [s for _, _, s in mechanism.visibility_report(load("cooking-helper"))]
    assert "private" in statuses and "private+consent" in statuses and "public" in statuses and "marker" in statuses
    assert rows["[0] profile"] == "marker"


def test_r4_command_line_share_prints_a_stripped_copy(capsys):
    rc = mechanism.main(["share", str(EX / "cooking-helper.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Pippin" in out and "diabetes" not in out and "nut free" not in out


def test_r4_command_line_refuses_to_share_an_invalid_file(capsys):
    assert mechanism.main(["share", str(EX / "INVALID-no-human-approval.json")]) == 1
    assert "INVALID" in capsys.readouterr().out


def test_command_line_validate_reports_pam_and_profile_separately(capsys):
    assert mechanism.main(["validate", str(EX / "cooking-helper.json")]) == 0
    out = capsys.readouterr().out
    assert "PAM v1.0: VALID" in out and "Profile:  VALID" in out
    assert mechanism.main(["validate", str(EX / "INVALID-no-human-approval.json")]) == 1
    assert "PAM v1.0: INVALID" in capsys.readouterr().out


# --- R5: front page ---------------------------------------------------------------------------------------

def test_r5_front_page_has_name_motto_and_optional_handle():
    fp = mechanism.front_page(load("cooking-helper"))
    assert fp["name"]["pronunciation"] == "PIP-in" and fp["motto"] and fp["paired_handle"] == "fennel_and_fire"
    assert mechanism.front_page(load("game-companion"))["paired_handle"] is None


def test_r5_private_paired_handle_never_travels_even_with_consent():
    doc = load("study-companion")
    handle = find(doc, role="front_page.paired_handle")[0]
    assert handle["access"]["visibility"] == "private" and mechanism.has_consent(handle)
    assert find(mechanism.share(doc), role="front_page.paired_handle") == []


def test_r5_public_paired_handle_travels():
    assert find(mechanism.share(load("cooking-helper")), role="front_page.paired_handle")


# --- R6: named memory kinds -------------------------------------------------------------------------------

def test_r6_examples_carry_a_place_a_routine_and_a_running_joke():
    seen = set()
    for name in GOOD:
        doc = load(name)
        kinds = {m.get("custom_type") for m in doc["memories"]}
        said_none = {"place": "places", "routine": "routines", "running_joke": "running_jokes"}
        marker = mechanism.x(find(doc, role="profile")[0])
        for kind, section in said_none.items():
            # R13: a kind is either carried or the human said there are none; never silently missing
            assert kind in kinds or section in marker.get("sections_empty", {}), (name, kind)
        seen |= kinds
    assert {"place", "routine", "running_joke"} <= seen


def test_r6_spec_names_the_kinds_and_says_what_counts_as_worth_carrying():
    text = (KIT / "spec" / "SPEC.md").read_text(encoding="utf-8")
    for word in ("place", "routine", "running_joke", "worth carrying"):
        assert word in text


def test_r6_a_carried_memory_can_say_why_it_is_carried():
    doc = load("cooking-helper")
    why = [mechanism.x(m).get("why_carried") for m in find(doc, custom_type="place")]
    assert why and why[0]


# --- R7: history belongs to the relationship --------------------------------------------------------------

def test_r7_spec_states_the_principle_and_adds_no_field_for_it():
    text = (KIT / "spec" / "SPEC.md").read_text(encoding="utf-8")
    assert "belongs to the relationship" in text
    props = mechanism.load_profile_schema()["$defs"]["PassportBlock"]["properties"]
    assert not any("relationship" in k or "companion_id" in k for k in props)


def test_r7_one_file_holds_the_person_the_companion_and_their_shared_history():
    doc = load("cooking-helper")
    assert doc["owner"]["id"] and mechanism.front_page(doc)["name"] and find(doc, role="correction")


# --- profile mechanics ------------------------------------------------------------------------------------

def test_profile_adds_no_root_field_because_pam_forbids_them():
    doc = load("cooking-helper")
    doc["front_page"] = {"name": "Pippin"}
    assert any("unknown field 'front_page'" in e for e in pam.validate_pam(doc))


def test_exactly_one_profile_marker_is_required():
    doc = load("cooking-helper")
    doc["memories"] = [m for m in doc["memories"] if mechanism.role(m) != "profile"]
    assert any("profile marker" in e for e in mechanism.validate_parts(reseal(doc))[1])


def test_unknown_metadata_keys_are_kept_and_travel_with_their_memory():
    doc = load("cooking-helper")
    pref = [m for m in doc["memories"] if m["type"] == "preference"][0]
    pref["metadata"]["x_other_app"] = {"tag": "braise"}
    assert mechanism.validate(reseal(doc)) == []
    assert mechanism.unknown_metadata_keys(doc) == ["x_other_app"]
    shared = mechanism.share(reseal(doc))
    assert [m for m in shared["memories"] if m["type"] == "preference"][0]["metadata"]["x_other_app"] == {"tag": "braise"}


def test_spec_document_answers_the_open_questions():
    text = (KIT / "spec" / "SPEC.md").read_text(encoding="utf-8")
    for heading in ("Versioning", "Who may write", "Unknown fields", "OPEN FOR THE COMMUNITY"):
        assert heading in text


def test_examples_are_regenerated_exactly_by_the_build_script():
    sys.path.insert(0, str(EX))
    build = importlib.import_module("build_examples")
    for fname, make in build.FILES.items():
        assert json.loads((EX / f"{fname}.json").read_text(encoding="utf-8")) == make(), fname


# --- demo -------------------------------------------------------------------------------------------------

def test_demo_core_output_matches_the_saved_expected_output():
    out = subprocess.run([sys.executable, str(KIT / "demo" / "run_demo.py"), "--core"], capture_output=True, text=True,
                         encoding="utf-8", cwd=str(KIT))
    assert out.returncode == 0
    expected = (KIT / "demo" / "EXPECTED_OUTPUT.txt").read_text(encoding="utf-8")
    assert out.stdout.replace("\r\n", "\n").strip() == expected.replace("\r\n", "\n").strip()


# --- fail by design: what is left for you (BRIEF.md) ------------------------------------------------------

def _module(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def test_whats_left_1_importer_back_into_an_app():
    mod = _module("base.importer")
    if mod is None or not callable(getattr(mod, "import_passport", None)):
        not_built("base/importer.py import_passport(doc, app): write a Passport into a companion app. "
                  "It must keep unknown metadata keys untouched, must not turn a private memory public, and must "
                  "keep the companion's name and history with the person rather than starting again.")
    not_built("importer exists: add a round-trip test (export -> passport -> import -> export loses nothing).")


def test_whats_left_2_signatures_and_tamper_detection():
    mod = _module("base.signing")
    if mod is None or not callable(getattr(mod, "verify", None)):
        not_built("base/signing.py sign(doc, key) and verify(doc, key): PAM section 18 defines the signature over "
                  "the integrity checksum, which covers whole memory objects, so it covers access.visibility and "
                  "metadata.x_passport. Build sign/verify (needs a crypto library) and prove a flipped flag fails.")
    not_built("signing exists: add a test that flipping one visibility flag or one consent record fails verify.")


def test_whats_left_3_changelog_merge():
    mod = _module("base.merge")
    if mod is None or not callable(getattr(mod, "merge", None)):
        not_built("base/merge.py merge(a, b): join two Passports that diverged (PAM section 16.3 has merge rules for "
                  "incremental exports; the profile needs the rest). A correction from either side must survive, a "
                  "private flag must never loosen, and two different names for the companion must not both be current.")
    not_built("merge exists: add tests for two apps correcting the same fact differently.")


def test_whats_left_4_a_second_apps_exporter():
    mod = _module("base.second_exporter")
    if mod is None or not callable(getattr(mod, "convert", None)):
        not_built("base/second_exporter.py convert(...): an exporter from another companion app's own export "
                  "format into a Passport. The kit ships no app exporter.")
    not_built("second exporter exists: add its mapping table to the README.")
