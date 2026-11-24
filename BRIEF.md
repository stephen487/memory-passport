# Memory Passport, one small open file so a companion's history travels with it

slug: memory-passport
status: DRAFT

## Technical obstacle
A companion app holds a person's corrections, the companion's name and the rules the person has set, but each app stores them in its own format, so moving to another app means starting again. A portable file also has to keep private things private and keep the person's own words unsoftened.

## Mechanism
A Passport profile for PAM v1.0 (Portable AI Memory): a valid PAM document whose memories carry a namespaced `metadata.x_passport` block and three custom memory kinds (place, routine, running_joke). A profile JSON Schema composes with PAM's own schema (vendored unchanged); a stdlib checker validates the PAM part (schema, content hashes, integrity checksum) and the profile rules; a report lists which memories are private or public; a share command strips every private memory the human has not consented to. The base proves validation and stripping on fictional examples with no model call.

## Who would buy it
Not yet researched: no buyer has been asked. Likely users are companion-app builders who want users to be able to leave, and users who want their companion's history to follow them.

## Sources quoted
- https://gdpr-info.eu/art-20-gdpr/
  > "in a structured, commonly used and machine-readable format"

## What's left for you
- An importer that reads a Passport back into a companion app, keeping unknown keys.
- Signatures and tamper detection for a Passport (PAM defines the signature; the kit does not implement it).
- A merge for two Passports that diverged.
- An exporter from a real companion app's own export format (the kit ships none).

## Existence
SIMILAR, and crowded (searched 2026-11-23). Pieces exist, no single format has all four of our rules (verbatim corrections apart from the companion's reading; name + pronunciation + renames; human-approval standing rules; field-level consent with a stripping `share`). Closest: Soul Protocol https://github.com/qbtrix/soul-protocol (MIT), Portable AI Memory (PAM) https://portable-ai-memory.pages.dev/spec/v1.0/ , MIF https://varun29ankus.github.io/mif-spec/spec . Several general memory-interchange formats already exist, so the better move is to ship this as a profile/extension on one of them (PAM first), not as a new base format.
