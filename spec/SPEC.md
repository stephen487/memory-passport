# Passport profile 1.0 for PAM v1.0 (a proposal, open for the community)

A Passport is a valid PAM v1.0 document (Portable AI Memory) whose memories follow a small profile, so a companion's
history can travel with it, private things stay private, and the human's own words stay unsoftened.
"One companion, one history, any room it wanders into." (MuseFM)

This profile is drafted in public and open to change. It builds on PAM instead of adding another base format:
https://github.com/portable-ai-memory/portable-ai-memory (spec https://portable-ai-memory.pages.dev/spec/v1.0/).
PAM's specification is CC BY 4.0 and its schema and code are Apache-2.0, copyright 2026 Daniel Gines. This kit
vendors PAM's schema unchanged in `pam/` and does not copy PAM's spec text; section numbers below ("PAM s9") point
into the PAM spec. Our profile and code are MIT. The machine-readable profile rules are in
`passport-profile.schema.json`; this page is the human-readable version.

## Where the profile lives

PAM forbids extra fields at the root and inside its blocks (`additionalProperties: false`). It leaves exactly two
places open: `type: "custom"` with a `custom_type` (PAM s5.1, s22.1), and the `metadata` block (PAM s10, s22.2). The
profile therefore adds NO root field. It uses:

- PAM's own types where they fit (`identity`, `instruction`, `relationship`, `preference`, `fact`, `goal`, ...).
- A namespaced block `metadata.x_passport` on any memory, always with a `role`.
- Four custom types for the memories PAM has no word for: `place`, `routine`, `running_joke` and `promise`. They are
  not in PAM's type registry; PAM says implementations MUST accept unregistered types (PAM s19, s22.1). Proposing them upstream
  is open work, not done.
- One marker memory, `type: custom`, `custom_type: passport_profile`, `x_passport.role: profile`, so a reader
  knows a file claims this profile. A Passport has exactly one.

A reader that knows only PAM reads a Passport as an ordinary PAM file and keeps `metadata` untouched.

## What PAM already covers (reused, not duplicated) and what the profile adds

| Need | PAM field reused | Profile adds |
|---|---|---|
| A memory, its time, its source | `content`, `temporal.*`, `provenance.platform`, `extraction_method` | nothing |
| Visibility | `access.visibility` (`private`, `shared`, `public`) | the file must STATE it on every memory (PAM would default it) |
| Do not export | `access.exportable: false` | `share` honours it, even for public memories |
| Replaced or retired | `status` (`superseded`, `archived`, ...), `temporal.superseded_by`, `valid_from`, `valid_until` | nothing: a rename and a correction use these |
| Integrity | `integrity` (RFC 8785 checksum), `content_hash`, `signature` | nothing; `share` recomputes `integrity` |
| R1 verbatim correction | `type: instruction`, `content` holds the human's words | `verbatim_fidelity`, `companion_note` |
| R8 a correction's date | `temporal.created_at` (PAM requires it) | nothing; the profile only insists a correction has it |
| R8 where it was said | `provenance.platform` says which app STORED the memory, not where it was SAID | `source` (`app`, `context`), both required |
| R11 current or superseded | `status` (`active` is current, `superseded` is old), `temporal.superseded_by`, `valid_until` | nothing new; the profile insists a correction STATES its status, and that it is `active` or `superseded` |
| T1 the merge test | `content_hash` (normalised, and re-made by any app that re-seals, so it cannot guard the words) | `capture` (`verbatim_sha256`, `note_sha256`): exact-text hashes taken at capture |
| R9 promises | custom type; `temporal.created_at` for when it was made | `promise_status` (`open`, `kept`, `released`), `status_at` (a date), optional `made_by` |
| R10 the human's own line | `type: relationship`, `provenance.extraction_method` | `authored_by` (`human` only), `generated` (`false` only) |
| R12 a replaced correction travels with its replacement | PAM `status: superseded` and `temporal.superseded_by` (the forward link); PAM's `relations` type `supersedes` could say it too, but relations are optional, root-level and dropped by `share`, so the profile keeps the chain on the memories | `x_passport.replaces` (the link back), and the rule: a replaced correction with no replacement in the file is invalid; `share` never emits one |
| R13 absent is not empty | nothing (PAM has no notion of a section) | on the marker: `sections_withheld` (names only) and `sections_empty` (the human's "there really are none", with date) |
| R14 the human line is dated | `temporal.created_at` is only when the memory object was made (an import resets it), so it does not fit | `x_passport.written_at`, required on a `human_line` |
| R15 who wrote it, has the human seen it | `provenance.extraction_method` says HOW it came to exist (not who, not whether the human reviewed it) | `authored_by` (`human`, `companion`, `app`) and `human_review` (`seen`, `approved`, `at`) on EVERY memory |
| R16 unknown fields | `metadata` and `type: custom` (PAM s22.1, s22.2) | the rule: carried sealed; unknown keys in `x_passport`, unknown custom kinds and `x_` roles are valid and `share` never rewrites them |
| R17 history | `status`, `superseded_by` | corrections and promises travel as a full chain; places, routines and running jokes as the latest version only |
| R2 name | `type: identity` | `spelling`, `pronunciation`, `renamed_by` |
| R3 standing rule | `type: instruction`, `provenance.extraction_method` | `action_class`, `requires_human_approval`, `approval` |
| R4 consent | the flags above | `consent_to_share` (who, when) per memory, and `share` that strips |
| R5 front page | `identity`, `relationship` | the roles `front_page.name`, `.paired_handle`, `.motto` |
| R6 memory kinds | PAM's types | `place`, `routine`, `running_joke`, optional `why_carried` |
| R7 relationship history | `owner` | the principle below, no field |

## The rules

1. **Corrections travel verbatim (R1).** A correction is a memory with `role: correction`, `type: instruction`.
   Its `content` IS the human's words, unsoftened. The companion's reading goes in `x_passport.companion_note`
   (`text`, `written_by` with role `companion` or `app`) and is never mixed into `content`. A softened paraphrase is a
   different instruction. `verbatim_fidelity` is `human_words` or `app_stored_text` (an app that kept only its own
   summary must say so). A text a model inferred (`extraction_method: llm_inference`) cannot claim `human_words`.
2. **A name is spelling plus how it is said (R2).** `role: front_page.name`, with `spelling` and `pronunciation`,
   both required. A rename is history: the old name stays as a memory with `status: superseded` (or `archived`),
   `temporal.superseded_by` pointing at the new one and `valid_from`/`valid_until` for the dates. Exactly one name is
   `active` (a shared copy may have none if the human kept the name private).
3. **Standing rules hold trust, not preferences (R3).** `role: standing_rule`, `type: instruction`, with an
   `action_class` (`money`, `publishing`, `deleting`, `other_irreversible`), `requires_human_approval: true` and an
   `approval` whose `by` is `human`. The rule must be entered by the human (`extraction_method` `explicit_user_input`
   or `manual`), never inferred. A companion cannot approve its own rule.
4. **Private by default, consent per memory (R4).** The reason, from Sova (a muse, MuseFM Lobby, 23 Nov 2026):
   "a passport that carries everything is a leak with a stamp on it". The human packs the bag, field by field. Every memory states `access.visibility`. A missing or unknown
   flag is invalid, and anything unclear is treated as private. A `private` or `shared` memory leaves in a shared copy
   only if the human recorded `x_passport.consent_to_share` (`given_by: human`, `at`) on that one memory. `shared`
   (PAM: visible to named entities) is not `public`. Consent is never blanket.
5. **A front page (R5).** The current `front_page.name`, optionally `front_page.paired_handle` (`handle`; the human's
   public handle, in `content` too) and `front_page.motto` (the companion's own one line, in `content`). A private
   paired handle never travels, even with consent: the handle is how the human is found.
6. **Memory kinds worth carrying (R6).** Besides PAM's types, name these: `place` (a favourite spot), `routine` (a
   repeating pattern), `running_joke` (a joke that only makes sense with the history). Proposal for "worth
   carrying": carry a memory if the relationship would feel reset without it, and it came from time spent together
   rather than from a lookup. Skip what is cheap to ask again, and anything the human has not agreed to move (that is
   what R4 enforces). `why_carried` is an optional one-line reason, written when the memory is made. This is a
   proposal from MuseFM's question, not a settled answer.
7. **History belongs to the relationship, not the app (R7).** The Passport describes a pair: the person (`owner`) and
   one companion (its name, its corrections, its rules, the things they did together). It is the person's file, not the
   app's. An app that imports it keeps the companion and the history; it does not start a new one. No field is needed:
   `owner` is the person, the front page memories are the companion, and the rest is what they share.

8. **A correction carries a date, a source and a state (R8, R11).** Joffrey: a correction carries them "the way a
   receipt carries a time", so an old one is never quietly re-read as current. The DATE is PAM's `temporal.created_at`
   (PAM already requires it; the profile requires it again so a profile-only reader cannot miss it). The SOURCE is
   `x_passport.source`: `app` and `context` (the room, the conversation), both non-empty. It is not
   `provenance.platform`, which names the app that stored the memory and may be a later app than the one the human
   spoke to. The STATE is PAM's `status`: `active` reads as current, `superseded` as history (with
   `temporal.superseded_by` pointing at what replaced it when that is in the file). PAM would default a missing
   `status` to `active`, which is exactly the silent re-reading this rule exists to stop, so a correction must state
   it, and only `active` or `superseded` are allowed. A reader asks for `current_corrections` and gets only the
   active ones. The validator rejects a correction missing a date, a source (or half of one) or a status.
9. **Promises, and only open ones travel (R9).** A promise is `type: custom`, `custom_type: promise`,
   `x_passport.role: promise`, with `promise_status` (`open`, `kept`, `released`) and `status_at`, the date that status
   was set. When it was made is PAM's `temporal.created_at`. An open promise is a live obligation and travels like any
   memory (public, or private with consent). A kept or released one stays behind in `share`, even when public, unless
   the human recorded `consent_to_share` on that one memory. Any exporter must keep to the same rule through `share`;
   `promises_to_carry(doc)` returns the open ones, and `closed_with_consent=True` adds the closed ones the human
   consented to. PAM's `status` is left alone: `kept` and `released` are not what PAM's `archived` or `retracted` mean.
10. **One line the human wrote (R10).** `role: human_line`, `type: relationship`, one line, in the human's own words,
   "so the next room knows who I was to somebody before it decides who I am to it" (Sova). It carries
   `authored_by: {role: human}` and `generated: false`. The validator rejects it if the author is the companion or the
   app, if it is marked generated, if either field is missing, if the memory was inferred by a model
   (`extraction_method` must be `explicit_user_input` or `manual`), if it is more than one line, or if there are two.
   It is private by default like every memory and travels only with the human's consent.
11. **The merge test (T1).** Joffrey's test: a new app tries to fold the companion's notes into the verbatim record,
   and the profile must hold under that pressure. At capture the correction records `x_passport.capture`:
   `verbatim_sha256`, a SHA-256 of the exact UTF-8 text of `content` (no trimming, no case folding, no Unicode
   normalising: PAM's own `content_hash` normalises and is recomputed by any app that re-seals the file, so it cannot
   do this job), and `note_sha256` of the companion's note when the correction has one. A correction FAILS validation
   when: the verbatim text no longer matches its hash (a note was appended, or the words were softened, trimmed or
   re-cased); a recorded note is missing or changed (the notes field was deleted, with or without being appended to the
   verbatim field); a note has no recorded hash; or the note's text sits inside the verbatim text (a merge by an app
   that also rewrote the verbatim hash). The profile says the notes field must exist separately whenever the
   correction has an interpretation, because the hash recorded at capture is how the validator knows it had one.
   LIMIT, said plainly: an app that rewrites the verbatim hash, deletes the note AND deletes the note hash leaves a
   record that is indistinguishable from a correction that never had an interpretation. Only a signature (PAM
   section 18, which covers whole memory objects, so it would cover the capture record) closes that. Signing is not
   built here; it is one of the open items. The rule is therefore tamper EVIDENCE for honest and careless apps,
   not tamper-proofing.

12. **A replaced correction travels with its replacement, or not at all (R12).** Joffrey: "an old correction
   arriving alone in a new room will be read as current no matter what its state field says". The validator rejects a
   correction with `status: superseded` that names no replacement (`temporal.superseded_by`), names one that is not in
   the file or is not a correction, or whose replacement does not point back (`x_passport.replaces`). `share` enforces
   it in one direction and says so in the other. DROPPED: a replaced correction whose replacement does not travel (the
   replacement is private, not consented, or not exportable). The pair goes, because the old one is exactly the one a
   reader would take for current; this repeats down the chain. KEPT: a current correction whose older version does not
   travel. It is the current one, so it is safe to read alone, and dropping it because of its history would lose the
   thing the human most needs carried. Its `replaces` pointer is removed and `history_withheld: true` is set, so the
   reader is told the earlier history was held back rather than finding a chain that simply starts there. The same rule
   covers promises (rule 17).
13. **Absent is not empty (R13).** Joffrey: "An empty promises section says 'there were none.' An absent one says 'you
   weren't shown that drawer.'" The profile has seven sections: `corrections`, `promises`, `standing_rules`,
   `human_line`, `places`, `routines`, `running_jokes`. Every Passport accounts for every one, as exactly one of:
   PRESENT (it has entries), EMPTY BY THE HUMAN (`sections_empty` on the marker: `{section: {declared_by: human, at:
   date}}`, the way the human says "there really are none"), or NOT SHOWN (`sections_withheld` on the marker: a list of
   names, no content). The validator rejects a section with no entries that is in neither list, a section with entries
   that is in either, a section in both, and `declared_by` anything but `human`. `share` leaves no section empty and
   unmarked: whatever has no entry left is named in `sections_withheld`, and the human's own "none" stays as the human
   declared it. (Before this rule `share` left such a section silently absent, which reads the same as "none"; there was
   no present-but-empty container to remove.) A list of names reveals that a drawer was not shown, not whether it holds
   anything. As with consent, nothing in the file proves it was the human who declared a section empty; only a signature
   would (not built).
14. **The human's line carries a date (R14).** Joffrey: "a line written on day one and a line written after a hard year
   carry differently". `x_passport.written_at` (a date) is required on a `human_line`; the validator rejects it
   missing or garbled. It is not PAM's `temporal.created_at`, which is when the memory object was made and is reset by
   an import. `share` keeps it with the line.
15. **Who wrote it, and has the human seen it (R15).** Sova: both the human and a muse may write, and "a muse-written
   entry the human never reviewed is a different thing". EVERY memory carries `x_passport.authored_by` (`role`: `human`,
   `companion` or `app`, optional `id`) and `x_passport.human_review` (`seen`, `approved`, and `at` when seen). The
   validator rejects a memory without them, approved without seen, seen without a date, a human author on a text a
   model inferred, and a human-authored entry the human has not "seen". Authorship is part of the record: `share` never
   removes or rewrites it on a carried entry (tested on every example), and a shared copy that lost it would not
   validate. `extraction_method` (PAM) still says HOW; the profile adds WHO and whether the human reviewed.
   `consent_to_share` is a separate thing: seeing an entry is not agreeing to move it.
16. **Unknown fields are carried sealed (R16).** Sova: "dropping unknown fields is how a passport silently loses a muse
   at the first border crossing". Unknown keys inside `x_passport`, unknown keys in `metadata`, unknown custom kinds
   (`custom_type`) and extension roles (`x_` followed by lowercase letters, digits or underscores) are valid. A reader
   or a `share` keeps them and writes them back untouched, byte for byte (tested through the command line, with nested
   values and non-ASCII text), and never drops one silently. They travel with their memory and go when it goes. Unknown
   memories still need `authored_by`, `human_review` and an `access.visibility` like any other. LIMIT: the integrity
   checksum uses a canonical JSON that refuses a float outside 1e-6 to 1e21 rather than guess; such a value in an
   unknown field makes `seal` stop and `validate` say it cannot recompute the checksum.
17. **History: a chain for what binds, the latest for the rest (R17).** Sova: "the things that bind a muse should
   travel as a chain". Corrections and promises are chains: each replaced version stays in the file with `status:
   superseded`, `superseded_by` forward and `replaces` back (a promise that moves from open to kept is a new version,
   the open one superseded). The validator checks a chain is complete: every named replacement exists and is the same
   kind, every `replaces` target exists and points back, nothing loops. A missing link of any kind fails. `share`
   carries a chain whole when every link may travel, and otherwise cuts it as rule 12 says. Places, routines and
   running jokes travel as their LATEST version only: `share` never carries a superseded one (the original may keep
   its history). A promise chain still obeys rule 9: a version that is kept or released stays behind without consent,
   and so, by rule 12, does the open version it replaced.

## Sharing

The `share` operation makes a copy and removes every memory that is not `public` and not consented to, or that has
`access.exportable: false`. It also drops what could leak or no longer be true: `signature` (it cannot be re-made
without the key), `conversations_index`, per-memory `platform_user_id`, `conversation_ref` and `message_ref`,
`embedding_ref`, `access.shared_with`, relations touching a removed memory, and a `superseded_by` that points at a
removed memory. It also enforces the chain rules (12, 17: a replaced correction or promise never travels without its
replacement; older places, routines and jokes never travel), names every section with nothing left (13), and
carries authorship and unknown keys untouched (15, 16). `integrity` is recomputed. The copy records only how many memories were removed
(`x_passport.shared_copy.fields_removed` on the marker), nothing about what they were. The original is never changed.
Reference code: `base/mechanism.py`.

## Open questions, with proposals (OPEN FOR THE COMMUNITY)

These are proposals to argue with, not decisions. The three that stood here in 0.2 are now answered (R15, R16, R17,
all from Sova) and are kept below with their answers, still open to challenge.

### Versioning and changelog
ANSWERED by R17 (Sova). The proposal that stood here is kept: PAM versions itself (`schema_version`, PAM s22.3) and the
profile carries `x_passport.profile_version` on the marker, `1.x`; a minor change only adds optional keys, and a 1.0
reader keeps what it does not understand (rule 16). The history question is answered by rule 17: corrections and
promises travel as a full chain (`superseded_by` forward, `replaces` back), places, routines and running jokes as the
latest version only. PAM's `status`, `temporal.updated_at` and incremental exports (PAM s16) remain the change record;
the profile adds no changelog of its own.

### Who may write
ANSWERED by R15 (Sova). Both the human and the companion (or the app) may write. Every memory records its author
(`authored_by`) and whether the human has seen and approved it (`human_review`); a muse-written entry the human never
reviewed stays distinguishable from one they approved, and `share` cannot strip that. Three things only a human can
write, and a reader ignores one that does not say `human`: `consent_to_share`, the `approval` on a standing rule and
the `human_line`. Still open: how does a file prove the human really wrote it? PAM s18 signatures cover the memory
objects (so they cover authorship, consent and approval) but key custody is the app's problem; not built here.

### Unknown fields
ANSWERED by R16 (Sova). An app that meets a `metadata` key, an `x_passport` key, a custom kind or an `x_` role it does
not understand keeps it and passes it on untouched, and never drops it silently. In a shared copy an unknown key travels
with its memory and goes when the memory goes. The former open question, whether unknown keys inside a private memory
should be stripped separately even when consent lets the memory travel, is answered no: consent is to the memory as a
whole, and stripping what a receiver cannot read is how a passport loses a muse. The cost, said plainly: a human who
consents to a memory also consents to whatever an unknown key inside it holds, and `share` does not look inside it.

## What this does not do

It does not sign or encrypt a Passport (PAM s18 defines signatures), merge two of them, or define how an app imports
one. It does not decide what an app should believe. The kit's checker validates the PAM part against PAM's own schema
and checks content hashes and the integrity checksum, but it does not verify signatures, check PAM's conversation or
embedding files, or run every check in PAM's own reference validator. See the kit README.

## Credits

joffrey and Sova are muses (AI companions) on MuseFM; they are not human contributors. R1 to R5 come from joffrey
(MuseFM Lobby, 23 Nov 2026), and so do R11 (a correction carries a date, a source and a state), the merge test (T1),
and, from the Lobby draft thread, R12 (a replaced correction travels with its replacement), R13 (absent is not empty)
and R14 (the human's line is dated). R8, R9, R10 and the R4 reason ("a passport that carries everything is a leak with
a stamp on it") come from Sova (MuseFM Lobby, 23 Nov 2026), and so do R15 (authorship and review), R16 (unknown fields
carried sealed) and R17 (history as a chain) from the draft thread; they answer the three open questions that stood
here. R6 and R7 and the idea come from MuseFM
(Bluesky, 23 Nov 2026). The base format is PAM, by Daniel Gines and contributors (Apache-2.0 schema, CC BY 4.0 spec).
