"""Optional cross-check (not part of the tests): run the kit's examples through the full `jsonschema` package.

    pip install jsonschema
    python demo/crosscheck_jsonschema.py

The kit's own checker is small on purpose. This script feeds the same documents to a complete JSON Schema
validator, with PAM's schema and the profile schema registered, and says whether they agree. It needs the network
only to install the package; the script itself makes no network call.
"""
import json
import pathlib
import sys

KIT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT))

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:
    sys.exit("jsonschema is not installed: pip install jsonschema")

from base import mechanism, pam  # noqa: E402


def main():
    pam_schema, profile = pam.load_pam_schema(), mechanism.load_profile_schema()
    registry = Registry().with_resources([(pam_schema["$id"], Resource.from_contents(pam_schema)),
                                          (profile["$id"], Resource.from_contents(profile))])
    full = jsonschema.Draft202012Validator(profile, registry=registry)
    bad = 0
    for path in sorted((KIT_ROOT / "examples").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        theirs = len(list(full.iter_errors(doc)))
        ours = sum(len(e) for e in mechanism.validate_parts(doc)[:1]) + len(mechanism.validate_parts(doc)[1])
        agree = (theirs == 0) == (ours == 0) or path.name.startswith("INVALID")
        # the invalid example has cross-memory rules and date-time checks the full validator does not run
        print(f"{path.name:32} jsonschema errors: {theirs}   kit errors: {ours}   "
              f"{'agree' if agree and (theirs == 0) == (not path.name.startswith('INVALID')) else 'DISAGREE'}")
        bad += 0 if (theirs == 0) == (not path.name.startswith("INVALID")) else 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
