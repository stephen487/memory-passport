"""Community round 2 (R8 to R11 and the T1 merge test). Written BEFORE the code, to fail first.

R8 + R11  a verbatim correction carries a date, a source (app and context) and a state (current or superseded).
R9        a PROMISES kind with status (open, kept, released) and a date; share carries only OPEN promises
          unless the human consents to a closed one.
R10       one line the HUMAN wrote about the companion: marked human-authored, never generated.
R4+       Sova's line is the stated reason for private-by-default (in SPEC.md).
T1        joffrey's merge test: a record where an app folded the companion's notes into the verbatim text (or
          deleted the notes and appended them) must FAIL validation; a clean record passes.
"""
import copy
import json
import pathlib

import pytest

from base import mechanism, pam

KIT = pathlib.Path(__file__).resolve().parents[2]
EX = KIT / "examples"
GOOD = ["cooking-helper", "study-companion", "game-companion"]


def load(name):
    return json.loads((EX / f"{name}.json").read_text(encoding="utf-8"))


def by_role(doc, r):
    return [m for m in doc["memories"] if mechanism.role(m) == r]


def prof_errors(doc):
    return mechanism.validate_parts(mechanism.seal(doc))[1]


def with_note(doc):
    """The first correction in the cooking example that has a companion note."""
    return [m for m in by_role(doc, "correction") if "companion_note" in mechanism.x(m)][0]


# --- R8 + R11: date, source, state on every verbatim correction ------------------------------------------

@pytest.mark.parametrize("name", GOOD)
def test_r8_every_correction_in_the_examples_has_date_source_and_state(name):
    cs = by_role(load(name), "correction")
    assert cs
    for c in cs:
        assert c["temporal"]["created_at"]                       # the date: PAM's own field, reused
        src = mechanism.x(c)["source"]
        assert src["app"] and src["context"]                      # where it was said
        assert c["status"] in ("active", "superseded")           # the state: PAM's own status, reused


def test_r8_the_examples_show_a_superseded_correction_that_is_not_current():
    doc = load("cooking-helper")
    old = [c for c in by_role(doc, "correction") if c["status"] == "superseded"]
    assert len(old) == 1 and old[0]["temporal"]["superseded_by"]
    now = mechanism.current_corrections(doc)
    assert old[0]["id"] not in {c["id"] for c in now}
    assert all(c["status"] == "active" for c in now) and len(now) >= 2


def test_r8_a_correction_without_a_source_is_rejected():
    doc = load("cooking-helper")
    del with_note(doc)["metadata"]["x_passport"]["source"]
    assert any("source" in e for e in prof_errors(doc))


@pytest.mark.parametrize("part", ["app", "context"])
def test_r8_a_source_needs_both_the_app_and_the_context(part):
    doc = load("cooking-helper")
    del with_note(doc)["metadata"]["x_passport"]["source"][part]
    assert any(part in e for e in prof_errors(doc))


def test_r8_a_blank_source_is_rejected():
    doc = load("cooking-helper")
    with_note(doc)["metadata"]["x_passport"]["source"]["context"] = ""
    assert any("source" in e and "too short" in e for e in prof_errors(doc))


def test_r11_a_correction_that_does_not_state_its_state_is_rejected_even_though_pam_would_default_it():
    doc = load("cooking-helper")
    del with_note(doc)["status"]
    assert any("status" in e for e in prof_errors(doc))


def test_r11_only_current_or_superseded_are_states_of_a_correction():
    doc = load("cooking-helper")
    with_note(doc)["status"] = "archived"
    assert any("status" in e for e in prof_errors(doc))


def test_r8_a_correction_without_a_date_is_rejected_by_the_profile_too():
    doc = load("cooking-helper")
    del with_note(doc)["temporal"]["created_at"]
    assert any("created_at" in e for e in mechanism.validate_parts(doc)[1])


def test_r8_a_correction_with_a_garbled_date_is_rejected():
    doc = load("cooking-helper")
    with_note(doc)["temporal"]["created_at"] = "last spring"
    assert mechanism.validate(mechanism.seal(doc))


def test_r8_share_keeps_date_source_and_state_with_a_correction():
    shared = mechanism.share(load("cooking-helper"))
    assert len(by_role(shared, "correction")) == 2
    for c in by_role(shared, "correction"):
        assert mechanism.x(c)["source"]["app"] and c["temporal"]["created_at"] and c["status"]
    assert mechanism.validate(shared) == []


# --- R9: promises ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", GOOD)
def test_r9_examples_carry_promises_with_a_status_and_a_date(name):
    ps = by_role(load(name), "promise")
    assert ps
    for p in ps:
        assert p["custom_type"] == "promise"
        b = mechanism.x(p)
        assert b["promise_status"] in ("open", "kept", "released") and b["status_at"][:4].isdigit()
        assert p["temporal"]["created_at"]


def test_r9_the_examples_use_all_three_statuses():
    seen = {mechanism.x(p)["promise_status"] for n in GOOD for p in by_role(load(n), "promise")}
    assert seen == {"open", "kept", "released"}


def test_r9_a_promise_needs_a_status():
    doc = load("cooking-helper")
    del by_role(doc, "promise")[0]["metadata"]["x_passport"]["promise_status"]
    assert any("promise_status" in e for e in prof_errors(doc))


def test_r9_a_promise_status_must_be_one_of_the_three():
    doc = load("cooking-helper")
    by_role(doc, "promise")[0]["metadata"]["x_passport"]["promise_status"] = "pending"
    assert any("promise_status" in e for e in prof_errors(doc))


def test_r9_a_promise_needs_the_date_of_its_status():
    doc = load("cooking-helper")
    del by_role(doc, "promise")[0]["metadata"]["x_passport"]["status_at"]
    assert any("status_at" in e for e in prof_errors(doc))


def test_r9_share_carries_an_open_promise_and_leaves_a_kept_one_behind():
    doc = load("cooking-helper")
    kept = [p for p in by_role(doc, "promise") if mechanism.x(p)["promise_status"] == "kept"][0]
    assert kept["access"]["visibility"] == "public" and not mechanism.has_consent(kept)   # public, still stays
    shared = by_role(mechanism.share(doc), "promise")
    assert shared and {mechanism.x(p)["promise_status"] for p in shared} == {"open"}


def test_r9_a_released_public_promise_also_stays_behind_without_consent():
    doc = load("game-companion")
    rel = [p for p in by_role(doc, "promise") if mechanism.x(p)["promise_status"] == "released"][0]
    assert rel["access"]["visibility"] == "public"
    assert rel["id"] not in {m["id"] for m in mechanism.share(doc)["memories"]}


def test_r9_a_kept_promise_travels_when_the_human_consents_to_that_one():
    doc = load("study-companion")
    kept = [p for p in by_role(doc, "promise") if mechanism.x(p)["promise_status"] == "kept"][0]
    assert mechanism.has_consent(kept)
    assert kept["id"] in {m["id"] for m in mechanism.share(doc)["memories"]}


def test_r9_consent_by_a_non_human_does_not_release_a_kept_promise():
    doc = load("study-companion")
    kept = [p for p in by_role(doc, "promise") if mechanism.x(p)["promise_status"] == "kept"][0]
    kept["metadata"]["x_passport"]["consent_to_share"]["given_by"] = "companion"
    assert kept["id"] not in {m["id"] for m in mechanism.share(doc)["memories"]}


def test_r9_an_open_promise_is_still_private_by_default():
    doc = load("game-companion")
    op = [p for p in by_role(doc, "promise") if mechanism.x(p)["promise_status"] == "open"
          and p["access"]["visibility"] == "private" and not mechanism.has_consent(p)]
    assert op
    assert op[0]["id"] not in {m["id"] for m in mechanism.share(doc)["memories"]}


def test_r9_the_promises_to_carry_helper_defaults_to_open_only():
    doc = load("cooking-helper")
    carried = mechanism.promises_to_carry(doc)
    assert carried and {mechanism.x(p)["promise_status"] for p in carried} == {"open"}
    study = load("study-companion")      # a kept promise the human consented to: only with the flag
    assert {mechanism.x(p)["promise_status"] for p in mechanism.promises_to_carry(study)} == {"open"}
    assert {mechanism.x(p)["promise_status"]
            for p in mechanism.promises_to_carry(study, closed_with_consent=True)} == {"open", "kept"}


def test_r9_the_shared_copy_is_still_valid():
    for n in GOOD:
        shared = mechanism.share(load(n))
        assert mechanism.validate(shared) == [], n


# --- R10: one line the human wrote about the companion ---------------------------------------------------

@pytest.mark.parametrize("name", GOOD)
def test_r10_examples_carry_one_human_authored_line(name):
    lines = by_role(load(name), "human_line")
    assert len(lines) == 1
    b = mechanism.x(lines[0])
    assert b["authored_by"] == {"role": "human"} and b["generated"] is False
    assert lines[0]["provenance"]["extraction_method"] in ("explicit_user_input", "manual")


@pytest.mark.parametrize("who", ["companion", "app"])
def test_r10_a_line_authored_by_the_companion_or_the_app_is_rejected(who):
    doc = load("cooking-helper")
    by_role(doc, "human_line")[0]["metadata"]["x_passport"]["authored_by"] = {"role": who}
    assert any("authored_by" in e for e in prof_errors(doc))


def test_r10_a_line_marked_generated_is_rejected():
    doc = load("cooking-helper")
    by_role(doc, "human_line")[0]["metadata"]["x_passport"]["generated"] = True
    assert any("generated" in e for e in prof_errors(doc))


def test_r10_a_line_that_does_not_say_whether_it_was_generated_is_rejected():
    doc = load("cooking-helper")
    del by_role(doc, "human_line")[0]["metadata"]["x_passport"]["generated"]
    assert any("generated" in e for e in prof_errors(doc))


def test_r10_a_line_with_no_author_is_rejected():
    doc = load("cooking-helper")
    del by_role(doc, "human_line")[0]["metadata"]["x_passport"]["authored_by"]
    assert any("authored_by" in e for e in prof_errors(doc))


def test_r10_a_line_a_model_inferred_is_rejected_even_if_it_claims_a_human_author():
    doc = load("cooking-helper")
    by_role(doc, "human_line")[0]["provenance"]["extraction_method"] = "llm_inference"
    assert any("human_line" in e and "human" in e for e in prof_errors(doc))


def test_r10_it_is_one_line_and_only_one():
    doc = load("cooking-helper")
    by_role(doc, "human_line")[0]["content"] += "\nand a second line"
    assert any("one line" in e for e in prof_errors(doc))
    doc = load("cooking-helper")
    extra = copy.deepcopy(by_role(doc, "human_line")[0])
    extra["id"] = "cooking-helper-line2"
    doc["memories"].append(extra)
    assert any("human_line" in e and "one" in e for e in prof_errors(doc))


def test_r10_the_line_is_private_by_default_and_travels_only_with_consent():
    cook = load("cooking-helper")
    line = by_role(cook, "human_line")[0]
    assert line["access"]["visibility"] == "private" and not mechanism.has_consent(line)
    assert by_role(mechanism.share(cook), "human_line") == []
    study = load("study-companion")
    assert mechanism.has_consent(by_role(study, "human_line")[0])
    assert by_role(mechanism.share(study), "human_line")


# --- R4+: Sova's reason for private-by-default ----------------------------------------------------------

def test_r4plus_spec_gives_sovas_line_as_the_reason_for_private_by_default():
    text = (KIT / "spec" / "SPEC.md").read_text(encoding="utf-8")
    assert "a passport that carries everything is a leak with a stamp on it" in text
    i = text.index("a passport that carries everything is a leak with a stamp on it")
    assert "Sova" in text[max(0, i - 200): i + 300]


def test_credits_name_sova_and_joffrey_for_the_new_rules():
    text = (KIT / "README.md").read_text(encoding="utf-8")
    sova = [l for l in text.splitlines() if l.startswith("| Sova")]
    joff = [l for l in text.splitlines() if l.startswith("| joffrey")]
    assert sova and all(k in sova[0] for k in ("R8", "R9", "R10", "R4"))
    assert joff and all(k in " ".join(joff) for k in ("R11", "merge"))


# --- T1: joffrey's merge test ---------------------------------------------------------------------------

def _merged_append(doc):
    """An app folds the companion's reading into the verbatim text and re-seals the file."""
    c = with_note(doc)
    c["content"] = c["content"] + " " + c["metadata"]["x_passport"]["companion_note"]["text"]
    return doc


def _merged_delete_and_append(doc):
    """The app deletes the separate notes field and appends its content to the verbatim field."""
    c = with_note(doc)
    note = c["metadata"]["x_passport"].pop("companion_note")
    c["content"] = c["content"] + " " + note["text"]
    return doc


def _merged_and_rehashed(doc):
    """A careless fix: the app also rewrites the capture hash to match the merged text."""
    _merged_append(doc)
    c = with_note(doc)
    c["metadata"]["x_passport"]["capture"]["verbatim_sha256"] = mechanism.verbatim_hash(c["content"])
    return doc


def _note_deleted_not_merged(doc):
    """The app simply drops the notes field; the capture record says there was one."""
    del with_note(doc)["metadata"]["x_passport"]["companion_note"]
    return doc


def test_t1_a_clean_record_passes():
    doc = load("cooking-helper")
    assert mechanism.validate(doc) == []
    assert mechanism.validate(mechanism.seal(doc)) == []


@pytest.mark.parametrize("merge", [_merged_append, _merged_delete_and_append, _merged_and_rehashed,
                                   _note_deleted_not_merged])
def test_t1_a_merged_record_fails_validation(merge):
    doc = merge(load("cooking-helper"))
    sealed = mechanism.seal(doc)                      # the app re-seals: PAM's own checks are happy
    pam_errors, errors = mechanism.validate_parts(sealed)
    assert pam_errors == []
    assert errors, merge.__name__
    assert any("correction" in e for e in errors)


def test_t1_the_merge_error_says_what_went_wrong():
    errs = prof_errors(_merged_append(load("cooking-helper")))
    assert any("verbatim" in e and "changed since capture" in e for e in errs)
    errs = prof_errors(_note_deleted_not_merged(load("cooking-helper")))
    assert any("companion_note" in e and "missing" in e for e in errs)


def test_t1_a_softened_or_re_cased_correction_also_fails():
    doc = load("cooking-helper")
    c = with_note(doc)
    c["content"] = c["content"].lower()
    assert any("changed since capture" in e for e in prof_errors(doc))


def test_t1_the_capture_hash_is_exact_not_normalised():
    assert mechanism.verbatim_hash("No, NO coriander.") != mechanism.verbatim_hash("no, no coriander.")
    assert mechanism.verbatim_hash("a") == mechanism.verbatim_hash("a")
    assert mechanism.verbatim_hash("a").startswith("sha256:")


def test_t1_a_correction_with_no_capture_record_is_rejected():
    doc = load("cooking-helper")
    del with_note(doc)["metadata"]["x_passport"]["capture"]
    assert any("capture" in e for e in prof_errors(doc))


def test_t1_a_note_with_no_note_hash_is_rejected():
    doc = load("cooking-helper")
    del with_note(doc)["metadata"]["x_passport"]["capture"]["note_sha256"]
    assert any("note_sha256" in e for e in prof_errors(doc))


def test_t1_a_changed_note_fails_its_own_hash():
    doc = load("cooking-helper")
    with_note(doc)["metadata"]["x_passport"]["companion_note"]["text"] = "Read as: coriander is fine."
    assert any("companion_note" in e and "changed since capture" in e for e in prof_errors(doc))


def test_t1_a_correction_with_no_interpretation_needs_no_note():
    doc = load("cooking-helper")
    plain = [c for c in by_role(doc, "correction") if "companion_note" not in mechanism.x(c)]
    assert plain and "note_sha256" not in mechanism.x(plain[0])["capture"]
    assert mechanism.validate(doc) == []


def test_t1_sharing_does_not_disturb_the_capture_record():
    shared = mechanism.share(load("cooking-helper"))
    assert mechanism.validate(shared) == []


def test_t1_the_spec_says_what_the_rule_cannot_do():
    text = (KIT / "spec" / "SPEC.md").read_text(encoding="utf-8")
    assert "signature" in text.lower() and "merge test" in text
