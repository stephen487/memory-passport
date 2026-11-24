"""Passport demo. Run from the kit root:  python demo/run_demo.py

1. Validates the three fictional example passports and the deliberately invalid one: first as PAM v1.0, then as
   the Passport profile.
2. Shows the front page and which memories are private (cooking-helper).
3. Runs `share` on cooking-helper and prints what a shared copy keeps and drops.
Prints steps 1 to 3.
Stdlib only. No network call, no model call. The output is the same every run.
"""
import datetime
import json
import pathlib
import runpy
import sys

KIT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT))

from base import mechanism  # noqa: E402

EX = KIT_ROOT / "examples"
FIXED_NOW = datetime.datetime(2026, 11, 23, 12, 0, 0, tzinfo=datetime.timezone.utc)


def labels(doc):
    out = []
    for i, m in enumerate(doc["memories"]):
        text = " ".join(m["content"].split())
        out.append(f"{mechanism.kind(m)} = " + json.dumps(text if len(text) <= 70 else text[:67] + "...",
                                                          ensure_ascii=False))
    return out


def authorship_summary(doc):
    who = {}
    for m in doc["memories"]:
        who[mechanism.x(m)["authored_by"]["role"]] = who.get(mechanism.x(m)["authored_by"]["role"], 0) + 1
    seen = sum(1 for m in doc["memories"] if mechanism.x(m)["human_review"]["seen"])
    return ", ".join(f"{k} {who[k]}" for k in sorted(who)) + f"; seen by the human {seen} of {len(doc['memories'])}"


def sections_line(doc):
    mk = mechanism.x(next(m for m in doc["memories"] if mechanism.role(m) == "profile"))
    return (f"sections not shown (names only): {mk.get('sections_withheld', [])}; "
            f"empty, the human says there are none: {sorted(mk.get('sections_empty', {}))}")


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    print("== 1. Validate the examples (PAM v1.0 first, then the Passport profile) ==")
    for name in ("cooking-helper", "study-companion", "game-companion", "INVALID-no-human-approval"):
        doc = json.loads((EX / f"{name}.json").read_text(encoding="utf-8"))
        pam_errors, prof_errors = mechanism.validate_parts(doc)
        print(f"{name}.json   PAM: {'valid' if not pam_errors else 'INVALID'}   profile: "
              f"{'valid' if not prof_errors else 'INVALID'}")
        for e in pam_errors:
            print("    PAM: " + e)
        for e in prof_errors:
            print("    profile: " + e)

    doc = json.loads((EX / "cooking-helper.json").read_text(encoding="utf-8"))
    print("\n== 2. Front page and privacy (cooking-helper) ==")
    fp = mechanism.front_page(doc)
    n = fp["name"]
    former = ", ".join("%s (%s)" % (f["spelling"], f["pronunciation"]) for f in fp["former_names"])
    print(f"name: {n['spelling']} (said {n['pronunciation']}); before that: {former}")
    print(f"paired handle: {fp['paired_handle']}; motto: {fp['motto']}")
    print("corrections (date, where it was said, state):")
    for m in mechanism.by_role(doc, "correction"):
        src = mechanism.x(m)["source"]
        state = "current" if m["status"] == "active" else "superseded"
        print(f"  {m['temporal']['created_at'][:10]}  {src['app']} / {src['context']}  [{state}]  "
              + json.dumps(m["content"][:40], ensure_ascii=False))
    print("promises: " + ", ".join(f"{mechanism.x(m)['promise_status']} since {mechanism.x(m)['status_at']}"
                                    for m in mechanism.by_role(doc, "promise")))
    line = mechanism.by_role(doc, "human_line")[0]
    print(f"human's own line (human-authored, written {mechanism.x(line)['written_at']}, private unless consented): "
          + json.dumps(line["content"], ensure_ascii=False))
    print("who wrote it, and has the human seen it: " + authorship_summary(doc))
    print(mechanism.format_report(doc))

    print("\n== 3. Share: before and after ==")
    shared = mechanism.share(doc, now=FIXED_NOW)
    before, after = labels(doc), labels(shared)
    print(f"BEFORE ({len(before)} memories):")
    for line in before:
        print(("  " if line in after else "  [PRIVATE] ") + line)
    print(f"AFTER, the shareable copy ({len(after)} memories):")
    for line in after:
        print("  " + line)
    marker = next(m for m in shared["memories"] if mechanism.role(m) == "profile")
    print(f"memories removed: {mechanism.x(marker)['shared_copy']['fields_removed']}")
    held = [m for m in shared["memories"] if mechanism.x(m).get("history_withheld")]
    print("the replaced coriander correction stayed home; the current one says its earlier history was withheld: "
          + str(bool(held)))
    print("authorship kept on every carried entry: " + authorship_summary(shared))
    pam_errors, prof_errors = mechanism.validate_parts(shared)
    print(f"shared copy valid as PAM: {not pam_errors}; as Passport profile: {not prof_errors}")

    print("\n== 3b. Absent is not empty (game-companion) ==")
    game = json.loads((EX / "game-companion.json").read_text(encoding="utf-8"))
    print("original:    " + sections_line(game))
    shared_game = mechanism.share(game, now=FIXED_NOW)
    print("shared copy: " + sections_line(shared_game))
    present = sorted({mechanism.section_of(m) for m in shared_game["memories"]} - {None})
    print(f"sections present with entries: {present}")
    pam_errors, prof_errors = mechanism.validate_parts(shared_game)
    print(f"shared copy valid as PAM: {not pam_errors}; as Passport profile: {not prof_errors}")



if __name__ == "__main__":
    main(sys.argv[1:])
