"""Community round 3 (R12 to R17), MuseFM Lobby draft thread, 23 Nov 2026.

R12 joffrey  a replaced correction travels only with the correction that replaced it, or not at all.
R13 joffrey  absent is not empty: sections the human did not pack are absent and marked, never present-but-empty.
R14 joffrey  the human-written line carries a date.
R15 Sova     every entry records its author and whether the human has seen and approved it; share cannot strip it.
R16 Sova     unknown fields are carried sealed, byte for byte.
R17 Sova     corrections and promises travel as a full history chain; places, routines and jokes as the latest only.
"""
import copy
import itertools
import json
import pathlib
import subprocess
import sys

import pytest

from base import mechanism, pam

KIT = pathlib.Path(__file__).resolve().parents[2]
EX = KIT / "examples"
GOOD = ["cooking-helper", "study-companion", "game-companion"]
SECTIONS = ["corrections", "promises", "standing_rules", "human_line", "places", "routines", "running_jokes"]


def load(name):
    return json.loads((EX / f"{name}.json").read_text(encoding="utf-8"))


def by_role(doc, r):
    return [m for m in doc["memories"] if mechanism.role(m) == r]


def by_id(doc, suffix):
    return [m for m in doc["memories"] if m["id"].endswith("-" + suffix)][0]


def prof_errors(doc):
    return mechanism.validate_parts(mechanism.seal(doc))[1]


def shared(doc):
    return mechanism.share(mechanism.seal(doc))


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def present(doc, text):
    return any(text in s for s in strings(doc))


def set_vis(m, vis, consent=None):
    m["access"]["visibility"] = vis
    b = m["metadata"]["x_passport"]
    b.pop("consent_to_share", None)
    if consent:
        b["consent_to_share"] = {"given_by": "human", "at": consent}


def chain_of_three(doc):
    """Cooking: c0 -> c1 -> c9, a three-link correction chain, all public. Returns (c0, c1, c9)."""
    c0, c1 = by_id(doc, "c0"), by_id(doc, "c1")
    c9 = copy.deepcopy(c1)
    c9["id"] = "cooking-helper-c9"
    c9["content"] = "Coriander is fine again, but only fresh, only at the end, and only if I ask."
    c9["content_hash"] = pam.content_hash(c9["content"])
    b = c9["metadata"]["x_passport"]
    b.pop("companion_note", None)
    b["replaces"] = c1["id"]
    b["capture"] = mechanism.capture_record(c9["content"])
    c9["status"] = "active"
    c9["temporal"] = {"created_at": "2026-09-01T10:00:00Z"}
    c1["status"] = "superseded"
    c1["temporal"]["superseded_by"] = c9["id"]
    doc["memories"].append(c9)
    for m in (c0, c1, c9):
        set_vis(m, "public")
    return c0, c1, c9


# --- R12: a replaced correction travels with its replacement, or not at all --------------------------------

def test_r12_a_replaced_correction_with_no_replacement_is_rejected():
    doc = load("cooking-helper")
    by_id(doc, "c0")["temporal"].pop("superseded_by")
    assert any("replacement" in e and "correction" in e for e in prof_errors(doc))


def test_r12_a_replaced_correction_whose_replacement_is_not_in_the_file_is_rejected():
    doc = load("cooking-helper")
    doc["memories"] = [m for m in doc["memories"] if not m["id"].endswith("-c1")]
    assert any("replacement" in e for e in prof_errors(doc))


def test_r12_a_correction_replaced_by_something_that_is_not_a_correction_is_rejected():
    doc = load("cooking-helper")
    by_id(doc, "c0")["temporal"]["superseded_by"] = by_id(doc, "p1")["id"]
    assert any("not a correction" in e for e in prof_errors(doc))


def test_r12_the_replacement_must_point_back_at_what_it_replaced():
    doc = load("cooking-helper")
    del by_id(doc, "c1")["metadata"]["x_passport"]["replaces"]
    assert any("point" in e and "replaced" in e for e in prof_errors(doc))


def test_r12_an_active_correction_must_not_claim_to_be_replaced():
    doc = load("cooking-helper")
    by_id(doc, "c2")["temporal"]["superseded_by"] = by_id(doc, "c3")["id"]
    assert any("superseded_by" in e and "not superseded" in e for e in prof_errors(doc))


def test_r12_share_drops_the_pair_when_the_replacement_is_not_consented():
    doc = load("cooking-helper")
    set_vis(by_id(doc, "c0"), "public")            # the old one would travel on its own
    set_vis(by_id(doc, "c1"), "private")           # its replacement may not
    out = shared(doc)
    assert not present(out, "a pinch of coriander") and not present(out, "tastes like soap")
    assert mechanism.validate(out) == []


def test_r12_share_drops_an_orphaned_replaced_correction_but_keeps_the_current_one():
    doc = load("cooking-helper")
    set_vis(by_id(doc, "c0"), "private")           # the old one stays home
    set_vis(by_id(doc, "c1"), "public")
    out = shared(doc)
    assert not present(out, "a pinch of coriander")
    kept = by_id(out, "c1")
    assert kept["status"] == "active"
    assert "replaces" not in kept["metadata"]["x_passport"]
    assert kept["metadata"]["x_passport"]["history_withheld"] is True
    assert mechanism.validate(out) == []


@pytest.mark.parametrize("old_vis,new_vis", list(itertools.product(["public", "private"], repeat=2)))
@pytest.mark.parametrize("old_consent,new_consent", list(itertools.product([None, "2026-08-01"], repeat=2)))
def test_r12_a_shared_copy_never_holds_a_replaced_correction_without_its_replacement(old_vis, new_vis,
                                                                                     old_consent, new_consent):
    doc = load("cooking-helper")
    set_vis(by_id(doc, "c0"), old_vis, old_consent)
    set_vis(by_id(doc, "c1"), new_vis, new_consent)
    out = shared(doc)
    ids = {m["id"] for m in out["memories"]}
    for m in by_role(out, "correction"):
        if m["status"] == "superseded":
            assert m["temporal"]["superseded_by"] in ids
    assert mechanism.validate(out) == []


def test_r12_a_chain_is_cut_from_the_new_end_down_not_the_old_end_up():
    doc = load("cooking-helper")
    c0, c1, c9 = chain_of_three(doc)
    set_vis(c9, "private")                         # the newest may not travel
    out = shared(mechanism.seal(doc))
    assert not [m for m in by_role(out, "correction") if m["id"] in (c0["id"], c1["id"], c9["id"])]  # the older two would read as current alone: all stay home


# --- R17: full chain for corrections and promises, latest only for the rest --------------------------------

def test_r17_the_examples_show_a_correction_chain_and_a_promise_chain():
    cook, study = load("cooking-helper"), load("study-companion")
    assert [m["status"] for m in by_role(cook, "correction")][:2] == ["superseded", "active"]
    assert any(m["status"] == "superseded" for m in by_role(study, "promise"))


def test_r17_a_complete_chain_travels_whole():
    doc = load("cooking-helper")
    chain_of_three(doc)
    assert prof_errors(doc) == []
    out = shared(mechanism.seal(doc))
    assert {by_id(out, k)["id"] for k in ("c0", "c1", "c9")}
    assert mechanism.x(by_id(out, "c9"))["replaces"].endswith("-c1")
    assert "history_withheld" not in mechanism.x(by_id(out, "c0"))
    assert mechanism.validate(out) == []


def test_r17_a_missing_middle_link_is_rejected():
    doc = load("cooking-helper")
    chain_of_three(doc)
    doc["memories"] = [m for m in doc["memories"] if not m["id"].endswith("-c1")]
    errs = prof_errors(doc)
    assert any("replacement" in e for e in errs) and any("replaces" in e and "not in the file" in e for e in errs)


def test_r17_a_missing_oldest_link_is_rejected_unless_history_was_withheld_on_purpose():
    doc = load("cooking-helper")
    doc["memories"] = [m for m in doc["memories"] if not m["id"].endswith("-c0")]
    assert any("replaces" in e and "not in the file" in e for e in prof_errors(doc))
    b = by_id(doc, "c1")["metadata"]["x_passport"]
    b.pop("replaces")
    b["history_withheld"] = True
    assert prof_errors(doc) == []


def test_r17_history_withheld_and_replaces_together_contradict():
    doc = load("cooking-helper")
    by_id(doc, "c1")["metadata"]["x_passport"]["history_withheld"] = True
    assert any("history_withheld" in e for e in prof_errors(doc))


def test_r17_a_chain_that_loops_is_rejected():
    doc = load("cooking-helper")
    c0, c1 = by_id(doc, "c0"), by_id(doc, "c1")
    c1["status"] = "superseded"
    c1["temporal"]["superseded_by"] = c0["id"]
    c0["metadata"]["x_passport"]["replaces"] = c1["id"]
    assert any("loop" in e for e in prof_errors(doc))


def test_r17_promise_history_travels_as_a_chain_too():
    doc = load("study-companion")
    old = [m for m in by_role(doc, "promise") if m["status"] == "superseded"][0]
    new = by_id(doc, "p1")
    assert old["temporal"]["superseded_by"] == new["id"]
    out = shared(doc)
    assert old["id"] in {m["id"] for m in out["memories"]} and new["id"] in {m["id"] for m in out["memories"]}
    set_vis(new, "private")                        # drop the consent that lets the kept promise travel
    out2 = shared(doc)
    assert by_role(out2, "promise") == [m for m in by_role(out2, "promise") if m["id"].endswith("-p2")]
    assert old["id"] not in {m["id"] for m in out2["memories"]}


def test_r17_a_promise_chain_with_a_missing_link_is_rejected():
    doc = load("study-companion")
    doc["memories"] = [m for m in doc["memories"] if not m["id"].endswith("-p1")]
    assert any("promise" in e and "replacement" in e for e in prof_errors(doc))


def test_r17_places_routines_and_jokes_travel_as_the_latest_version_only():
    doc = load("cooking-helper")
    place = by_id(doc, "place")
    old = copy.deepcopy(place)
    old["id"] = "cooking-helper-place-old"
    old["content"] = "Favourite spot: the cheese stall by the old fountain."
    old["content_hash"] = pam.content_hash(old["content"])
    old["status"] = "superseded"
    old["temporal"] = {"created_at": "2026-04-01T10:00:00Z", "superseded_by": place["id"]}
    doc["memories"].append(old)
    assert prof_errors(doc) == []                  # the original may keep its history
    out = shared(doc)
    assert present(out, "third from the fountain") and not present(out, "old fountain")
    assert mechanism.validate(out) == []


# --- R13: absent is not empty ------------------------------------------------------------------------------

def test_r13_every_example_accounts_for_every_section():
    for name in GOOD:
        doc = load(name)
        marker = mechanism.x(by_role(doc, "profile")[0])
        for s in SECTIONS:
            n = sum(1 for m in doc["memories"] if mechanism.section_of(m) == s)
            assert (n > 0) + (s in marker.get("sections_empty", {})) + (s in marker.get("sections_withheld", [])) == 1


def test_r13_an_example_says_the_human_has_none():
    doc = load("game-companion")
    marker = mechanism.x(by_role(doc, "profile")[0])
    assert marker["sections_empty"]["places"]["declared_by"] == "human"
    assert not any(mechanism.section_of(m) == "places" for m in doc["memories"])


def test_r13_an_empty_section_that_nobody_marked_is_rejected():
    doc = load("cooking-helper")
    doc["memories"] = [m for m in doc["memories"] if mechanism.section_of(m) != "routines"]
    assert any("routines" in e and "not marked" in e for e in prof_errors(doc))


def test_r13_the_human_can_say_there_really_are_none():
    doc = load("cooking-helper")
    doc["memories"] = [m for m in doc["memories"] if mechanism.section_of(m) != "routines"]
    mechanism.x(by_role(doc, "profile")[0])["sections_empty"] = {"routines": {"declared_by": "human", "at": "2026-11-01"}}
    assert prof_errors(doc) == []


@pytest.mark.parametrize("bad", [
    {"declared_by": "companion", "at": "2026-11-01"},
    {"declared_by": "app", "at": "2026-11-01"},
    {"declared_by": "human"},
    {"at": "2026-11-01"},
])
def test_r13_only_the_human_can_declare_a_section_empty_and_with_a_date(bad):
    doc = load("cooking-helper")
    doc["memories"] = [m for m in doc["memories"] if mechanism.section_of(m) != "routines"]
    mechanism.x(by_role(doc, "profile")[0])["sections_empty"] = {"routines": bad}
    assert prof_errors(doc) != []


def test_r13_a_section_with_entries_cannot_be_marked_empty_or_withheld():
    doc = load("cooking-helper")
    marker = mechanism.x(by_role(doc, "profile")[0])
    marker["sections_empty"] = {"places": {"declared_by": "human", "at": "2026-11-01"}}
    assert any("places" in e and "entries" in e for e in prof_errors(doc))
    marker.pop("sections_empty")
    marker["sections_withheld"] = ["places"]
    assert any("places" in e and "entries" in e for e in prof_errors(doc))


def test_r13_a_section_cannot_be_both_empty_and_withheld_and_names_must_be_known():
    doc = load("game-companion")
    marker = mechanism.x(by_role(doc, "profile")[0])
    marker["sections_withheld"] = ["places"]
    assert any("places" in e and "both" in e for e in prof_errors(doc))
    marker["sections_withheld"] = ["not_a_section"]
    assert prof_errors(doc) != []


def test_r13_the_withheld_list_holds_names_only_never_content():
    doc = load("game-companion")
    out = shared(doc)
    marker = mechanism.x(by_role(out, "profile")[0])
    assert "promises" in marker["sections_withheld"] and "human_line" in marker["sections_withheld"]
    assert all(s in SECTIONS for s in marker["sections_withheld"])
    for secret in ("remind me to stop at midnight", "bad rounds"):
        assert not present(out, secret)


def test_r13_share_never_leaves_an_empty_section_unmarked_whatever_the_human_hid():
    for name in GOOD:
        doc = load(name)
        for m in doc["memories"]:
            if mechanism.section_of(m):
                set_vis(m, "private")
        out = shared(doc)
        marker = mechanism.x(by_role(out, "profile")[0])
        for s in SECTIONS:
            n = sum(1 for m in out["memories"] if mechanism.section_of(m) == s)
            marked = (s in marker.get("sections_empty", {})) + (s in marker.get("sections_withheld", []))
            assert (n > 0) + marked == 1, (name, s)
        assert mechanism.validate(out) == []


def test_r13_share_keeps_what_the_human_declared_empty_and_does_not_call_it_withheld():
    out = shared(load("game-companion"))
    marker = mechanism.x(by_role(out, "profile")[0])
    assert "places" in marker["sections_empty"] and "places" not in marker["sections_withheld"]


def test_r13_the_report_does_not_invent_empty_sections():
    doc = load("cooking-helper")
    assert "sections_withheld" not in mechanism.format_report(doc)


# --- R14: the human-written line carries a date ------------------------------------------------------------

@pytest.mark.parametrize("name", GOOD)
def test_r14_the_examples_date_the_human_line(name):
    line = by_role(load(name), "human_line")[0]
    assert mechanism.x(line)["written_at"][:4] == "2026"


def test_r14_an_undated_line_is_rejected():
    doc = load("cooking-helper")
    del mechanism.x(by_role(doc, "human_line")[0])["written_at"]
    assert any("written_at" in e for e in prof_errors(doc))


@pytest.mark.parametrize("bad", ["yesterday", "", "2026", "2026-13", True])
def test_r14_a_garbled_date_is_rejected(bad):
    doc = load("cooking-helper")
    mechanism.x(by_role(doc, "human_line")[0])["written_at"] = bad
    assert any("written_at" in e for e in prof_errors(doc))


def test_r14_share_keeps_the_date_with_a_line_that_travels():
    doc = load("study-companion")
    out = shared(doc)
    assert mechanism.x(by_role(out, "human_line")[0])["written_at"] == mechanism.x(by_role(doc, "human_line")[0])["written_at"]


# --- R15: who wrote it, and has the human seen it ----------------------------------------------------------

@pytest.mark.parametrize("name", GOOD)
def test_r15_every_entry_in_the_examples_records_author_and_review(name):
    for m in load(name)["memories"]:
        b = mechanism.x(m)
        assert b["authored_by"]["role"] in ("human", "companion", "app")
        assert isinstance(b["human_review"]["seen"], bool) and isinstance(b["human_review"]["approved"], bool)


def test_r15_the_examples_show_all_three_authors_and_both_review_states():
    roles, states = set(), set()
    for name in GOOD:
        for m in load(name)["memories"]:
            b = mechanism.x(m)
            roles.add(b["authored_by"]["role"])
            states.add((b["human_review"]["seen"], b["human_review"]["approved"]))
    assert roles == {"human", "companion", "app"} and {(True, True), (False, False)} <= states


def test_r15_an_entry_with_no_author_is_rejected_even_a_plain_one():
    doc = load("cooking-helper")
    del by_id(doc, "pref")["metadata"]["x_passport"]["authored_by"]
    assert any("authored_by" in e for e in prof_errors(doc))
    doc = load("cooking-helper")
    del by_id(doc, "pref")["metadata"]
    assert any("metadata" in e for e in prof_errors(doc))


def test_r15_an_unknown_author_is_rejected():
    doc = load("cooking-helper")
    by_id(doc, "pref")["metadata"]["x_passport"]["authored_by"] = {"role": "stranger"}
    assert any("authored_by" in e for e in prof_errors(doc))


def test_r15_an_entry_that_does_not_say_whether_the_human_saw_it_is_rejected():
    doc = load("cooking-helper")
    del by_id(doc, "pref")["metadata"]["x_passport"]["human_review"]
    assert any("human_review" in e for e in prof_errors(doc))


def test_r15_approved_without_seen_is_rejected_and_seen_needs_a_date():
    doc = load("cooking-helper")
    by_id(doc, "pref")["metadata"]["x_passport"]["human_review"] = {"seen": False, "approved": True}
    assert any("seen" in e for e in prof_errors(doc))
    by_id(doc, "pref")["metadata"]["x_passport"]["human_review"] = {"seen": True, "approved": True}
    assert any("'at'" in e for e in prof_errors(doc))


def test_r15_a_model_inferred_entry_cannot_be_authored_by_the_human():
    doc = load("cooking-helper")
    p = by_id(doc, "pref")
    p["metadata"]["x_passport"]["authored_by"] = {"role": "human"}
    p["metadata"]["x_passport"]["human_review"] = {"seen": True, "approved": True, "at": "2026-05-01"}
    assert any("authored by the human" in e for e in prof_errors(doc))


def test_r15_a_human_authored_entry_counts_as_seen_by_the_human():
    doc = load("cooking-helper")
    by_id(doc, "c2")["metadata"]["x_passport"]["human_review"] = {"seen": False, "approved": False}
    assert any("human" in e and "seen" in e for e in prof_errors(doc))


def test_r15_a_companion_entry_the_human_never_reviewed_stays_distinct_after_share():
    doc = load("cooking-helper")
    out = shared(doc)
    reviewed = [m for m in out["memories"] if mechanism.x(m)["human_review"]["seen"]
                and mechanism.x(m)["authored_by"]["role"] == "companion"]
    unreviewed = [m for m in out["memories"] if not mechanism.x(m)["human_review"]["seen"]
                  and mechanism.x(m)["authored_by"]["role"] == "companion"]
    assert reviewed and unreviewed


@pytest.mark.parametrize("name", GOOD)
def test_r15_share_keeps_authorship_on_every_carried_entry(name):
    doc = load(name)
    before = {m["id"]: m for m in doc["memories"]}
    out = shared(doc)
    assert out["memories"]
    for m in out["memories"]:
        b, b0 = mechanism.x(m), mechanism.x(before[m["id"]])
        assert b["authored_by"] == b0["authored_by"]
        assert b["human_review"] == b0["human_review"]


def test_r15_a_shared_copy_that_lost_authorship_would_not_validate():
    out = shared(load("cooking-helper"))
    del mechanism.x(out["memories"][1])["authored_by"]
    assert any("authored_by" in e for e in prof_errors(out))


# --- R16: unknown fields are carried sealed ----------------------------------------------------------------

UNKNOWN = {"mood": {"arc": ["warm", "dry", 1.0, 2, None, True], "z": "ünï code", "a": {"deep": {"er": 0.25}}},
           "x_other_app": "seal"}


def with_unknowns(doc):
    """Unknown keys inside x_passport on a marker, a public memory, a consented private one, and an unknown kind."""
    for suffix in ("marker", "pref", "c2", "c1"):
        mechanism.x(by_id(doc, suffix)).update(copy.deepcopy(UNKNOWN))
    odd = copy.deepcopy(by_id(doc, "pref"))
    odd["id"] = "cooking-helper-odd"
    odd["type"], odd["custom_type"] = "custom", "muse_mood_ring"
    odd["content"] = "Mood ring says: amber."
    odd["content_hash"] = pam.content_hash(odd["content"])
    odd["metadata"]["x_passport"].update(copy.deepcopy(UNKNOWN))
    doc["memories"].append(odd)
    future = copy.deepcopy(odd)
    future["id"] = "cooking-helper-future"
    future["custom_type"] = "future_kind"
    future["content"] = "A role this version does not know."
    future["content_hash"] = pam.content_hash(future["content"])
    future["metadata"]["x_passport"]["role"] = "x_future_role"
    doc["memories"].append(future)
    return mechanism.seal(doc)


def canon(obj):
    return pam.canonical_json(obj)


def test_r16_unknown_keys_and_unknown_kinds_validate():
    doc = with_unknowns(load("cooking-helper"))
    assert mechanism.validate(doc) == []


def test_r16_the_validator_never_changes_what_it_reads():
    doc = with_unknowns(load("cooking-helper"))
    before = json.dumps(doc, ensure_ascii=False)
    mechanism.validate(doc)
    mechanism.format_report(doc)
    mechanism.share(doc)
    assert json.dumps(doc, ensure_ascii=False) == before


def test_r16_share_carries_unknown_keys_byte_for_byte():
    doc = with_unknowns(load("cooking-helper"))
    out = mechanism.share(doc)
    assert mechanism.validate(out) == []
    carried = 0
    for suffix in ("marker", "pref", "c2", "c1", "odd", "future"):
        orig = [m for m in doc["memories"] if m["id"].endswith("-" + suffix)][0]
        kept = [m for m in out["memories"] if m["id"] == orig["id"]]
        if not kept:
            continue
        carried += 1
        for key in UNKNOWN:
            assert canon(mechanism.x(kept[0])[key]) == canon(mechanism.x(orig)[key]), (suffix, key)
            assert list(mechanism.x(kept[0])[key]) == list(mechanism.x(orig)[key]) if isinstance(UNKNOWN[key], dict) else True
    assert carried >= 5


def test_r16_a_round_trip_through_the_command_line_keeps_the_unknown_text_exactly():
    # Files go in a folder inside the kit's own harness folder and are removed after: the release gate lets a harness
    # write only inside its copy.
    scratch = pathlib.Path(__file__).resolve().parents[1] / "_roundtrip_scratch"
    scratch.mkdir(exist_ok=True)
    try:
        _round_trip(scratch)
    finally:
        for f in scratch.glob("*"):
            f.unlink()
        scratch.rmdir()


def _round_trip(tmp_path):
    doc = with_unknowns(load("cooking-helper"))
    src = tmp_path / "in.json"
    out = tmp_path / "out.json"
    src.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run = lambda *a: subprocess.run([sys.executable, "-m", "base.mechanism", *a], capture_output=True, text=True,
                                    encoding="utf-8", cwd=str(KIT))
    assert run("validate", str(src)).returncode == 0
    assert run("share", str(src), "-o", str(out)).returncode == 0
    text = out.read_text(encoding="utf-8")
    for key in UNKNOWN:
        sub = json.dumps(UNKNOWN[key], indent=2, ensure_ascii=False)
        sub = sub.replace("\n", "\n" + " " * 10)   # depth of x_passport values in the written file
        assert sub in text, key
    assert run("validate", str(out)).returncode == 0


def test_r16_an_unknown_key_goes_when_its_memory_goes():
    doc = with_unknowns(load("cooking-helper"))
    mechanism.x(by_id(doc, "c3"))["x_secret_marker"] = "ONLY-WITH-C3"
    mechanism.x(by_id(doc, "pref"))["x_public_marker"] = "WITH-PREF"
    out = mechanism.share(mechanism.seal(doc))
    assert not present(out, "ONLY-WITH-C3") and present(out, "WITH-PREF")


def test_r16_an_unknown_metadata_key_outside_x_passport_is_kept_too():
    doc = load("cooking-helper")
    by_id(doc, "pref")["metadata"]["x_muse"] = {"keep": ["me", 1]}
    out = shared(doc)
    assert by_id(out, "pref")["metadata"]["x_muse"] == {"keep": ["me", 1]}


def test_r16_an_unknown_role_without_the_extension_prefix_is_still_rejected():
    doc = load("cooking-helper")
    mechanism.x(by_id(doc, "pref"))["role"] = "gossip"
    assert prof_errors(doc) != []


# --- the documents say so, and credit them ----------------------------------------------------------------

def test_spec_answers_the_three_former_open_questions_and_credits_sova():
    text = (KIT / "spec" / "SPEC.md").read_text(encoding="utf-8")
    for h in ("R12", "R13", "R14", "R15", "R16", "R17"):
        assert h in text
    assert "Sova" in text and "joffrey" in text
    for q in ("Versioning and changelog", "Who may write", "Unknown fields"):
        i = text.index("### " + q)
        assert "ANSWERED" in text[i: i + 600]


def test_readme_credits_state_that_joffrey_and_sova_are_muses_and_musefm_gave_r6_r7():
    text = (KIT / "README.md").read_text(encoding="utf-8")
    assert "muses (AI companions)" in text
    assert "Who designed this" in text and "no human demand has been measured" in text
    rows = [l for l in text.splitlines() if l.startswith("| joffrey") or l.startswith("| Sova")]
    assert any("R12" in r and "R13" in r and "R14" in r for r in rows)
    assert any("R15" in r and "R16" in r and "R17" in r for r in rows)
    assert "GitHub issue" in text
