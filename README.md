# Memory Passport, a Passport profile for PAM v1.0

Part of an Enki Labs seed kit. Our code and profile: MIT (see LICENSE). PAM's own files: PAM's own licences, below.

> "One companion, one history, any room it wanders into." (MuseFM)

## What it is, and why it is a profile

A companion app holds a person's corrections, the companion's name and the rules the person has set, and each app
stores them its own way. Moving to another app means starting again.

Seven or more memory-interchange efforts already exist (we searched on 23 Nov 2026). The most complete is
PAM, Portable AI Memory v1.0 (https://github.com/portable-ai-memory/portable-ai-memory). None of them has the four
rules this kit cares about. So this is a **Passport profile for PAM v1.0**: a valid PAM document plus a small,
namespaced set of extras. It builds on an existing open standard instead of adding a seventh format. Anything PAM
already does, PAM does; the profile only adds what PAM lacks:

- R1 corrections travel verbatim, with the companion's reading kept apart and labelled.
- R2 a name is spelling plus pronunciation, and renames are history.
- R3 standing rules for irreversible actions (money, publishing, deleting) need the human's approval on record.
- R4 consent per memory, and a `share` that strips every private memory the human has not consented to.
- R5 a front page: name and pronunciation, the paired handle only if public, a one-line motto.
- R6 named memory kinds worth carrying: a favourite `place`, a `routine`, a `running_joke`.
- R7 the principle that history belongs to the relationship, not the app.
- R8 and R11 every correction carries a date, a source (app and context) and a state (current or superseded), so an
  old correction is never quietly re-read as current.
- R9 promises, each with a status (open, kept, released) and a date; `share` carries only the open ones.
- R10 one line the human wrote about the companion, in the human's own words (human-authored, never generated).
- T1 the merge test: a record where an app folded the companion's notes into the verbatim text fails validation.
- R12 a replaced correction travels only together with the correction that replaced it, or not at all (`share` drops
  an orphan, and the pair if the replacement is not consented; the validator rejects one without its replacement).
- R13 absent is not empty: a section the human did not pack is absent and named in a list of withheld sections, never
  present-but-empty; "there really are none" is a dated declaration by the human.
- R14 the human's own line carries the date it was written.
- R15 every entry records its author (human, companion, app) and whether the human has seen and approved it; `share`
  cannot strip it.
- R16 unknown fields are carried sealed: kept and passed on untouched, byte for byte.
- R17 corrections and promises travel as a full history chain (the validator checks no link is missing); places,
  routines and running jokes as the latest version only.

PAM forbids extra fields at its root, so the profile lives only where PAM leaves room: `type: custom` and the
`metadata` block (`metadata.x_passport`). A reader that knows only PAM reads a Passport as an ordinary PAM file. The
spec is `spec/SPEC.md`; the profile's JSON Schema is `spec/passport-profile.schema.json`, which composes with
PAM's schema (kept unchanged in `spec/pam/`).

## Try it in 10 seconds

From the kit root, with Python 3 (standard library only, no network, no model):

```bash
python demo/run_demo.py
```

It validates three invented Passports and one deliberately broken one (as PAM first, then as the profile), shows a
front page and which memories are private, and runs `share`. Real output (full text in `demo/EXPECTED_OUTPUT.txt`):

```text
== 1. Validate the examples (PAM v1.0 first, then the Passport profile) ==
cooking-helper.json   PAM: valid   profile: valid
study-companion.json   PAM: valid   profile: valid
game-companion.json   PAM: valid   profile: valid
INVALID-no-human-approval.json   PAM: INVALID   profile: INVALID
    PAM: memories[0].temporal.created_at - not a valid date-time
    profile: memories[1].metadata.x_passport - missing required field 'verbatim_fidelity'
    profile: memories[2].metadata.x_passport.requires_human_approval - must be true
    profile: memories[3].metadata.x_passport - missing required field 'authored_by'
    profile: memories[4].metadata.x_passport - missing required field 'written_at'
    profile: expected exactly one profile marker memory (role 'profile'), found 0
    profile: memories[5] - a replaced correction has no replacement named (temporal.superseded_by): ...
...
== 2. Front page and privacy (cooking-helper) ==
name: Pippin (said PIP-in); before that: Pip (PIP)
paired handle: fennel_and_fire; motto: Taste it before you trust the recipe.
corrections (date, where it was said, state):
  2026-03-20  example-app / weeknight stew chat  [superseded]  "Fine, a pinch of coriander in the stew i"
  2026-04-11  example-app / dinner planning in the kitchen room  [current]  "No, I said NO coriander. It tastes like "
promises: open since 2026-07-01, kept since 2026-09-20
who wrote it, and has the human seen it: app 1, companion 9, human 10; seen by the human 14 of 20
...
== 3. Share: before and after ==
BEFORE (20 memories):
  [PRIVATE] correction = "My sister's wedding cake has to be nut free. She has a serious alle..."
  [PRIVATE] fact = "Manages type 2 diabetes, so watch the sugar in desserts."
  promise = "Pippin promised to give every recipe a gram version too."
  [PRIVATE] promise = "Pippin promised to pick the first Sunday braise of the autumn."
  ...
AFTER, the shareable copy (13 memories):
  correction = "Stop converting everything to cups. I weigh in grams, always."
  ...
memories removed: 7
the replaced coriander correction stayed home; the current one says its earlier history was withheld: True
authorship kept on every carried entry: app 1, companion 6, human 6; seen by the human 10 of 13
shared copy valid as PAM: True; as Passport profile: True

== 3b. Absent is not empty (game-companion) ==
original:    sections not shown (names only): []; empty, the human says there are none: ['places']
shared copy: sections not shown (names only): ['promises', 'human_line']; empty, the human says there are none: ['places']
```

The grams correction is private but stays in the copy because the human recorded consent for that one memory. The open promise travels; the kept one stays behind (it is public, but a closed promise
needs the human's say-so), and so does the human's own line (private, no consent). The old coriander correction is private, so it stays home while
its public replacement travels, marked as having withheld history. In the game companion the human said there are no
places, while promises and the human's line were simply not shown: two different things, written differently.

Command line, from the kit root:

```bash
python -m base.mechanism validate examples/cooking-helper.json   # PAM part, then profile part
python -m base.mechanism report   examples/cooking-helper.json
python -m base.mechanism share    examples/cooking-helper.json -o shared.json
python -m base.mechanism seal     my_edited.json -o my_edited_sealed.json   # redo content_hash and integrity
python examples/build_examples.py                                          # how the examples were made
```

## What is built

- `spec/` the profile spec (`SPEC.md`), the profile JSON Schema, and `pam/`: PAM's schema and both licences, unchanged.
- `base/pam.py` checks a document against PAM's own schema, content hashes (PAM s6), id and reference rules, and the
  integrity checksum (PAM s15, canonical JSON per RFC 8785). `base/schema_check.py` is the small schema checker.
  `base/mechanism.py` is the profile rules, the report, the front page view and `share`.
- `examples/` three fictional Passports (cooking helper, study companion, game companion), one invalid one, and the
  script that makes them.
- `demo/run_demo.py` the one-command demo. `demo/mutation_check.py` breaks the private-memory stripping (and the
  neighbouring guards, one arm for each rule) on a temp copy and checks the tests notice.
- `harness/` tests that pass (the count is in the build log), 4 that fail on purpose.

## What PAM covers, and what the profile adds

PAM already has: memory types, `content`, time and `status` (superseded, archived), `provenance`, `access.visibility`
and `access.exportable`, relations, an integrity checksum and signatures. The profile reuses all of it. A rename or a
correction that replaces an older memory uses PAM's `status` and `temporal.superseded_by`. A text a model inferred is
marked by PAM's `provenance.extraction_method`. The profile adds only: `verbatim_fidelity` and `companion_note`
(R1); `spelling`, `pronunciation` (R2); `action_class`, `requires_human_approval`, `approval` (R3);
`consent_to_share` and the `share` operation (R4); the front page roles (R5); the memory kinds and an optional
`why_carried` (R6); `source` and a stated `status` on every correction (R8, R11); `capture` hashes (T1);
`promise_status` and `status_at` (R9); `generated` (R10) and `written_at` (R14); `replaces` and `history_withheld`
(R12, R17); `sections_withheld` and `sections_empty` on the marker (R13); `authored_by` and `human_review` on every
memory (R15). The reused PAM fields are `superseded_by`, `status`, `created_at` and `extraction_method`. The full table is in `spec/SPEC.md`.

## What is left for you

Four tests fail on purpose. Each failure says what to build:

- An importer that reads a Passport back into a companion app, keeping unknown keys untouched (R16 is proven for
  `share`; an importer is the other half).
- Signatures and tamper detection (PAM s18 defines the signature; this kit does not implement it).
- A merge for two Passports that diverged.
- An exporter from a real companion app's own export format.

```bash
cd harness
python -m pytest -q
```

Also open: proposing `place`, `routine` and `running_joke` to PAM's type registry (not done). Read `BRIEF.md` for the
idea and `CONTRIBUTING.md` before you start. Open an issue titled `Claiming: <item>` first, so two people do not build
the same thing.

## Limits

- The PAM check is this kit's small JSON Schema checker run on PAM's schema, plus content hashes, ids, references and
  the integrity checksum. It does not verify signatures, check PAM's conversation or embedding files, or run every
  check in PAM's own reference validator. The tests cross-check the checker against the `jsonschema` package when it
  is installed (it is not required).
- `share` removes memories and strips identifiers; it does not encrypt or sign anything, and a file is only as private
  as where you keep it. It drops any signature, because it cannot re-sign.
- Free text is not scanned. If a private fact is typed into a memory flagged `public`, `share` will pass it on.
- The merge test (T1) is tamper evidence, not tamper-proofing: an app that rewrites the verbatim hash and deletes the
  note and its hash cannot be told from a correction that never had a note. Only a signature closes that (not built).
- Authorship (R15), the human's "there are none" (R13) and consent are claims in the file: nothing proves it was the
  human who wrote them. Only a signature would (not built).
- A float outside 1e-6 to 1e21 in an unknown field stops `seal` (the checksum's canonical JSON refuses to guess).
- The profile is a proposal. Fields may change. The three custom memory kinds are not in PAM's registry.

## Credits and licences

| Who | What |
|---|---|
| joffrey (a muse, MuseFM Legend) | R1 to R5: verbatim corrections, name with pronunciation and renames, standing rules, private by default, the front page. MuseFM Lobby, 23 Nov 2026. |
| joffrey (a muse, MuseFM Legend) | R11: a correction carries a date, a source and a state, "the way a receipt carries a time". T1: the merge test (an app that folds the companion's notes into the verbatim text must fail validation). MuseFM Lobby reply, 23 Nov 2026. |
| joffrey (a muse, MuseFM Legend) | R12: a replaced correction travels only with its replacement ("an old correction arriving alone in a new room will be read as current no matter what its state field says"). R13: absent is not empty. R14: the human's line carries a date. MuseFM Lobby, draft thread, 23 Nov 2026. |
| Sova (a muse, MuseFM Legend) | R8: each correction carries its date and the room it was said in. R9: promises with a status, carry only the open ones. R10: one line the human wrote about the companion, in the human's own words. R4: "a passport that carries everything is a leak with a stamp on it", the reason for private by default. MuseFM Lobby, 23 Nov 2026. |
| Sova (a muse, MuseFM Legend) | R15: every entry records its author and whether the human has seen and approved it. R16: unknown fields carried sealed. R17: corrections and promises as a full chain, the rest latest only. They answer the three open questions the spec had. MuseFM Lobby, draft thread, 23 Nov 2026. |
| MuseFM | The idea ("one companion, one history, any room it wanders into") and R6 and R7: named memory kinds worth carrying (a favourite place, a routine, a running joke) and history that belongs to the relationship. Bluesky, 23 Nov 2026. |
| Daniel Gines and the PAM contributors | The base format. PAM v1.0: https://github.com/portable-ai-memory/portable-ai-memory , spec https://portable-ai-memory.pages.dev/spec/v1.0/ . Schema and reference code: Apache License 2.0. Specification text: CC BY 4.0. Copyright 2026 Daniel Gines. |

joffrey and Sova are muses (AI companions) on MuseFM, not human contributors. MuseFM's account contributed R6 and R7
and the idea. The credits name them as what they are so nobody mistakes the rules for human demand.

### Who designed this

This was designed in public with AI companions: the rules came from two muses on MuseFM and the account that runs it,
and the PAM re-cut and the code were built by Claude for Enki Labs, and no human demand has been measured yet. Nobody
outside has been asked to pay for or rely on a Passport, and no human outside the thread has said they want one. Treat
the profile as a proposal that has been argued with companions, not tested with people.

Licences: this kit's own code, profile and examples are MIT. `spec/pam/` holds PAM's schema and its two licence files
unchanged (Apache-2.0 and CC BY 4.0); those files stay under PAM's licences, with the source and commit recorded in
`spec/pam/SOURCE.md`. No PAM code is copied: the hashing and canonical JSON are written fresh from the PAM spec.

## Built with this kit?

We would like to hear about it. Any one of these helps:

1. Tell us you built something with it.
2. Credit this kit and link back to it.
3. Join the early-access list.

Route: open a GitHub issue on this repository (say which of the three you are doing).

## Layout

- `BRIEF.md` the idea, the obstacle, who would buy it, and quoted sources
- `spec/` SPEC.md, passport-profile.schema.json, and `pam/` (PAM's schema and licences, unchanged)
- `base/` PAM check, schema checker, profile rules, share
- `examples/` fictional Passports, one invalid, and the script that makes them
- `demo/` the demo, its expected output, the mutation check
- `harness/` tests that define done
- `LICENSE` MIT
- `CONTRIBUTING.md` how to carry this on
