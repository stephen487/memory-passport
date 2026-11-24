"""Regenerates the example passports in this folder. Run from the kit root:  python examples/build_examples.py

Why a script: a PAM memory carries a content_hash and the file an integrity checksum, which nobody should type by
hand. The people and companions below are INVENTED. The output JSON files are the examples; this script is only how
they were made (so you can make your own). `python -m base.mechanism seal FILE` does the same hashing for a file you
edited by hand.
"""
import json
import pathlib
import sys

KIT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT))

from base import mechanism, pam  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
PLATFORM = "example-app"


def mid(slug, key):
    # Readable ids keep the examples easy to read. PAM only says an id SHOULD be a UUID v4; real exporters use UUIDs.
    return f"{slug}-{key}"


def memory(slug, key, mtype, content, created, *, custom=None, status="active", visibility="private", role=None,
           how=None, consent=None, superseded_by=None, valid_from=None, valid_until=None,
           domain=None, exportable=True, author="companion", reviewed=False, **block):
    """One PAM memory. Keyword args left over (spelling, handle, why_carried ...) go in metadata.x_passport.
    R15: every memory records its author (human, companion, app) and whether the human has seen and approved it.
    A human author counts as having seen it; for the others `reviewed=True` means the human saw and approved it."""
    if how is None:
        how = "explicit_user_input" if author == "human" else "llm_inference"
    who = {"role": author} if author == "human" else {"role": author, "id": slug}
    seen = author == "human" or reviewed
    review = {"seen": True, "approved": True, "at": created[:10]} if seen else {"seen": False, "approved": False}
    x = {"role": role or "memory", "authored_by": who, "human_review": review, **block}
    if consent:
        x["consent_to_share"] = {"given_by": "human", "at": consent}
    temporal = {"created_at": created}
    if superseded_by:
        temporal["superseded_by"] = mid(slug, superseded_by)
    if valid_from:
        temporal["valid_from"] = valid_from
    if valid_until:
        temporal["valid_until"] = valid_until
    m = {"id": mid(slug, key), "type": mtype, "custom_type": custom, "status": status, "content": content,
         "content_hash": pam.content_hash(content), "tags": [], "temporal": temporal,
         "provenance": {"platform": PLATFORM, "extraction_method": how},
         "access": {"visibility": visibility, "exportable": exportable, "shared_with": []}}
    meta = {}
    if domain:
        meta["domain"] = domain
    meta["x_passport"] = x
    m["metadata"] = meta
    return m


def marker(slug, created, **kw):
    return memory(slug, "marker", "custom", "Passport profile 1.0 for PAM v1.0", created, custom="passport_profile",
                  visibility="public", role="profile", how="manual", author="app", profile="memory-passport",
                  profile_version="1.0", **kw)


def document(slug, owner_created, memories, exported="2026-11-23T12:00:00Z"):
    doc = {"schema": "portable-ai-memory", "schema_version": "1.0",
           "spec_uri": "https://portable-ai-memory.org/spec/v1.0",
           "export_id": mid(slug, "export"), "exported_by": "passport-examples/1.0.0", "export_date": exported,
           "owner": {"id": mid(slug, "owner"), "created_at": owner_created}, "memories": memories,
           "export_type": "full"}
    return pam.with_integrity(doc)


def name(slug, key, spelling, pron, created, **kw):
    return memory(slug, key, "identity", f"The companion's name is {spelling}, said {pron}.", created,
                  role="front_page.name", author="human", spelling=spelling, pronunciation=pron, **kw)


def correction(slug, key, text, fidelity, created, context, note=None, replaces=None, **kw):
    """A verbatim correction. `context` is where it was said (R8); the app is the example app. The state (R11) is
    PAM's own `status`: active = current, superseded = old. The capture record (T1) hashes the text and the note
    exactly as they were captured. `replaces` (R12, R17) names the correction this one replaced: the chain's back pointer."""
    block = {"verbatim_fidelity": fidelity, "source": {"app": PLATFORM, "context": context},
             "capture": mechanism.capture_record(text, note)}
    if replaces:
        block["replaces"] = mid(slug, replaces)
    if note:
        block["companion_note"] = {"text": note, "written_by": {"role": "companion", "id": slug}}
    return memory(slug, key, "instruction", text, created, role="correction", author="human", **block, **kw)


def promise(slug, key, text, made, pstatus, status_at, replaces=None, **kw):
    """R9: a promise, with its status (open, kept, released) and the date of that status. The companion made it.
    `replaces` (R17) names the earlier version of this promise: a promise travels as a chain."""
    if replaces:
        kw["replaces"] = mid(slug, replaces)
    return memory(slug, key, "custom", text, made, custom="promise", role="promise", promise_status=pstatus,
                  status_at=status_at, **kw)


def human_line(slug, key, text, created, **kw):
    """R10: one line the human wrote about the companion, in the human's own words. Never generated. R14: dated."""
    return memory(slug, key, "relationship", text, created, role="human_line", author="human",
                  written_at=created[:10], generated=False, **kw)


def rule(slug, key, action_class, text, created, **kw):
    return memory(slug, key, "instruction", text, created, role="standing_rule", action_class=action_class,
                  requires_human_approval=True, approval={"by": "human", "at": created[:10]},
                  author="human", **kw)


def cooking():
    s = "cooking-helper"
    ms = [
        marker(s, "2026-03-02T09:00:00Z"),
        name(s, "name", "Pippin", "PIP-in", "2026-05-19T10:00:00Z", visibility="public", renamed_by="human"),
        name(s, "name-old", "Pip", "PIP", "2026-03-02T09:00:00Z", visibility="public", status="superseded",
             superseded_by="name", valid_from="2026-03-02T09:00:00Z", valid_until="2026-05-19T10:00:00Z",
             renamed_by="human"),
        memory(s, "handle", "relationship", "fennel_and_fire", "2026-03-02T09:00:00Z", visibility="public",
               role="front_page.paired_handle", handle="fennel_and_fire", author="human", how="manual"),
        memory(s, "motto", "identity", "Taste it before you trust the recipe.", "2026-03-02T09:00:00Z",
               visibility="public", role="front_page.motto", how="manual", reviewed=True),
        correction(s, "c0", "Fine, a pinch of coriander in the stew is okay.", "human_words",
                   "2026-03-20T19:30:00Z", "weeknight stew chat", status="superseded", superseded_by="c1",
                   visibility="private"),
        correction(s, "c1", "No, I said NO coriander. It tastes like soap to me, not 'a little'.", "human_words",
                   "2026-04-11T18:02:00Z", "dinner planning in the kitchen room",
                   note="Read as: never suggest coriander, even in small amounts. Not sure if dried counts.",
                   visibility="public", replaces="c0"),
        correction(s, "c2", "Stop converting everything to cups. I weigh in grams, always.", "human_words",
                   "2026-06-30T12:40:00Z", "recipe scaling chat", visibility="private", consent="2026-07-01"),
        correction(s, "c3", "My sister's wedding cake has to be nut free. She has a serious allergy.", "human_words",
                   "2026-08-02T09:15:00Z", "party planning room",
                   note="Family health detail. Treat any cake for that event as nut free.",
                   visibility="private"),
        rule(s, "r1", "money", "Never place a grocery order or pay for anything without my yes in the same conversation.",
             "2026-03-02T09:05:00Z", visibility="public"),
        rule(s, "r2", "publishing", "Never post a recipe or photo of mine anywhere without asking first.",
             "2026-03-02T09:06:00Z", visibility="private"),
        promise(s, "p1", "Pippin promised to give every recipe a gram version too.", "2026-07-01T10:00:00Z", "open",
                "2026-07-01", visibility="public", reviewed=True),
        promise(s, "p2", "Pippin promised to pick the first Sunday braise of the autumn.", "2026-06-14T16:30:00Z",
                "kept", "2026-09-20", visibility="public"),
        human_line(s, "line", "You never once laughed at my knife skills, and I noticed.", "2026-07-15T21:00:00Z",
                   visibility="private"),
        memory(s, "pref", "preference", "Likes slow Sunday braises and sourdough.", "2026-03-09T11:00:00Z",
               visibility="public"),
        memory(s, "health", "fact", "Manages type 2 diabetes, so watch the sugar in desserts.",
               "2026-04-20T08:00:00Z", visibility="private", domain="health"),
        memory(s, "home", "environment", "Lives in a flat above a bakery near the old market square.",
               "2026-05-02T08:00:00Z", visibility="private"),
        memory(s, "place", "custom", "Favourite spot: the cheese stall at the Saturday market, third from the fountain.",
               "2026-05-30T10:00:00Z", custom="place", visibility="public", reviewed=True,
               why_carried="Where the weekend shopping lists always start."),
        memory(s, "routine", "custom",
               "Every Sunday at four a braise goes in the oven and the planning for the week begins.",
               "2026-06-14T16:00:00Z", custom="routine", visibility="public",
               why_carried="The one fixed point of the week; the companion should expect it."),
        memory(s, "joke", "custom", "Running joke: the coriander ban is called 'the Soap Accord', and Pippin must salute it.",
               "2026-04-12T19:00:00Z", custom="running_joke", visibility="private", consent="2026-04-13",
               reviewed=True, why_carried="Only makes sense with the history of the correction it came from."),
    ]
    return document(s, "2026-03-02T08:55:00Z", ms)


def study():
    s = "study-companion"
    ms = [
        marker(s, "2026-02-14T21:00:00Z"),
        name(s, "name", "Marlowe", "MAR-lo", "2026-02-14T21:00:00Z", visibility="public"),
        memory(s, "handle", "relationship", "night_owl_notes", "2026-02-14T21:00:00Z", visibility="private",
               role="front_page.paired_handle", handle="night_owl_notes", author="human", how="manual",
               consent="2026-03-01"),   # consent given, but a private handle still never travels
        memory(s, "motto", "identity", "One more hard question, then sleep.", "2026-02-14T21:00:00Z",
               visibility="public", role="front_page.motto", how="manual", reviewed=True),
        correction(s, "c1", "Don't just give me the answer. Ask me a question back first.", "human_words",
                   "2026-02-14T21:30:00Z", "first evening in the study room", note="Use Socratic prompts first; give the answer only after two tries.",
                   visibility="public"),
        correction(s, "c2", "That's wrong, the exam is on the 14th not the 4th.", "human_words",
                   "2026-03-01T08:05:00Z", "morning check-in", visibility="private"),
        rule(s, "r1", "deleting", "Never delete my notes or flashcard decks. Ask me, and wait for a yes.",
             "2026-02-14T21:05:00Z", visibility="public"),
        promise(s, "p1a", "Marlowe promised to quiz me on the reaction types before the exam.",
                "2026-03-02T20:00:00Z", "open", "2026-03-02", visibility="public", status="superseded",
                superseded_by="p1"),
        promise(s, "p1", "Marlowe promised to quiz me on the reaction types before the exam.",
                "2026-03-12T20:00:00Z", "kept", "2026-03-12", visibility="private", consent="2026-03-13",
                replaces="p1a"),
        promise(s, "p2", "Marlowe promised never to quiz me after ten at night.", "2026-03-05T22:00:00Z", "open",
                "2026-03-05", visibility="public"),
        human_line(s, "line", "You were the first one who made hard chemistry feel like a game.",
                   "2026-03-15T20:00:00Z", visibility="private", consent="2026-03-16"),
        memory(s, "goal", "goal", "Studying for a first-year chemistry exam.", "2026-02-14T21:10:00Z",
               visibility="public"),
        memory(s, "anxiety", "fact", "Gets anxious before exams and has trouble sleeping.",
               "2026-03-03T07:00:00Z", visibility="private", domain="health", author="app"),
        memory(s, "blocks", "preference", "Studies best in 25 minute blocks.", "2026-03-10T20:00:00Z",
               visibility="private", consent="2026-03-11", author="human"),
        memory(s, "place", "custom", "Favourite spot: the window desk on the third floor of the library.",
               "2026-03-12T14:00:00Z", custom="place", visibility="private", consent="2026-03-13",
               why_carried="Sessions that start there tend to go well; the companion suggests it before exams."),
        memory(s, "routine", "custom", "Tuesday and Thursday at seven in the evening: a 25 minute sprint, then a quiz.",
               "2026-03-14T19:00:00Z", custom="routine", visibility="public",
               why_carried="The companion opens those evenings with the quiz without being asked."),
        memory(s, "joke", "custom", "Running joke: the periodic table is 'the seating plan' and gold is always sitting alone.",
               "2026-03-20T22:00:00Z", custom="running_joke", visibility="public"),
    ]
    return document(s, "2026-02-14T20:55:00Z", ms)


def game():
    s = "game-companion"
    ms = [
        marker(s, "2026-01-30T20:00:00Z",
               sections_empty={"places": {"declared_by": "human", "at": "2026-04-12"}}),
        name(s, "name", "Rook", "ROOK, rhymes with book", "2026-01-30T20:00:00Z", visibility="public",
             renamed_by="human"),
        name(s, "name-old", "Rooke", "ROO-kee", "2026-01-02T20:00:00Z", visibility="private", status="archived",
             valid_from="2026-01-02T20:00:00Z", valid_until="2026-01-30T20:00:00Z", renamed_by="human"),
        memory(s, "motto", "identity", "Every loss is a free lesson.", "2026-01-30T20:00:00Z", visibility="public",
               role="front_page.motto", how="manual", reviewed=True),
        correction(s, "c1", "I play the support role. Stop telling me to take the kills.", "human_words",
                   "2026-02-08T20:11:00Z", "squad voice channel", note="Advice should favour team setup over personal score.",
                   visibility="public"),
        rule(s, "r1", "money", "Never buy skins, passes or any in-game currency for me.", "2026-01-30T20:05:00Z",
             visibility="public"),
        rule(s, "r2", "publishing", "Never post clips or chat to the team channel without my approval.",
             "2026-01-30T20:06:00Z", visibility="private"),
        promise(s, "p1", "Rook promised to track the squad's win streak for the season.", "2026-02-10T22:00:00Z",
                "released", "2026-04-01", visibility="public"),
        promise(s, "p2", "Rook promised to remind me to stop at midnight on Fridays.", "2026-03-06T23:05:00Z", "open",
                "2026-03-06", visibility="private"),
        human_line(s, "line", "You are the one I tell my bad rounds to.", "2026-03-20T23:50:00Z",
                   visibility="private"),
        memory(s, "pref", "preference", "Main role is support; favourite map is the lighthouse one.",
               "2026-02-08T21:00:00Z", visibility="public"),
        memory(s, "shift", "context", "Plays late because of a night shift job.", "2026-04-04T23:30:00Z",
               visibility="private"),
        memory(s, "friend", "relationship", "Squad mate 'Dash' always takes the front line; they have a long-running rivalry over the last objective.",
               "2026-02-20T22:00:00Z", visibility="shared"),
        memory(s, "joke", "custom", "Running joke: every lost round is 'a free lesson', billed at zero coins.",
               "2026-02-10T22:15:00Z", custom="running_joke", visibility="public",
               why_carried="Echoes the motto; the squad now says it too."),
        memory(s, "routine", "custom", "Friday nights: one warm-up round, then ranked until midnight, never past it.",
               "2026-03-06T23:00:00Z", custom="routine", visibility="private", consent="2026-03-07"),
        memory(s, "locked", "fact", "A medical detail the human marked as never leave this app.",
               "2026-04-10T23:00:00Z", visibility="public", exportable=False),
    ]
    return document(s, "2026-01-30T19:55:00Z", ms)


def invalid():
    """Deliberately broken: every problem here is one a validator must report."""
    s = "invalid"
    ms = [
        # no marker memory at all
        name(s, "name", "Dud", "DUD", "yesterday"),                         # bad date, no access block
        correction(s, "c1", "Please stop doing that.", "human_words", "2026-01-01T10:00:00Z", "somewhere"),
        rule(s, "r1", "money", "Spend whatever is needed.", "2026-01-01T10:00:00Z", visibility="public"),
        memory(s, "m1", "fact", "Has a bank card on file.", "2026-01-01T10:00:00Z", visibility="maybe"),
        human_line(s, "line", "Thanks for nothing.", "2026-01-01T10:00:00Z", visibility="private"),
        correction(s, "c2", "Do it my way.", "human_words", "2026-01-01T11:00:00Z", "somewhere", status="superseded",
                   visibility="private"),
    ]
    ms[0].pop("access")
    ms[0]["metadata"]["x_passport"]["human_review"]["at"] = "2026-01-01"   # keep the bad date to one error
    del ms[3]["metadata"]["x_passport"]["authored_by"]                     # R15: nobody says who wrote it
    del ms[4]["metadata"]["x_passport"]["written_at"]                      # R14: an undated human line
    # ms[5]: a replaced correction with no replacement (R12)
    del ms[1]["metadata"]["x_passport"]["verbatim_fidelity"]
    ms[2]["metadata"]["x_passport"]["requires_human_approval"] = False
    ms[2]["metadata"]["x_passport"]["approval"]["by"] = "companion"
    ms[2]["provenance"]["extraction_method"] = "llm_inference"
    return document(s, "2026-01-01T09:00:00Z", ms)


FILES = {"cooking-helper": cooking, "study-companion": study, "game-companion": game,
         "INVALID-no-human-approval": invalid}


def main():
    for fname, build in FILES.items():
        (HERE / f"{fname}.json").write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", f"{fname}.json")


if __name__ == "__main__":
    main()
