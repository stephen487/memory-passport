# base/

The smallest code that proves the Passport profile for PAM v1.0 works.

- `pam.py` checks a document against PAM v1.0's own schema (vendored unchanged in `spec/pam/`), content hashes, ids, references and the integrity checksum. The hashing and canonical JSON are written fresh from the PAM spec.
- `schema_check.py` is the small JSON Schema checker both schemas run through. It refuses a keyword it does not know.
- `mechanism.py` holds the profile rules, the visibility report, the front page view, `share` and `seal`.

Standard library only. No network calls, no model calls, no secrets. It proves validation and stripping on fictional examples. It does not verify signatures, merge or import; the harness says what is missing.
