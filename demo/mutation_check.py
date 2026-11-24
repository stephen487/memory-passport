"""Mutation check: break the private-memory stripping on purpose and confirm the harness notices.

Run from the kit root:  python demo/mutation_check.py
Works on a COPY in a temp folder; the kit is never changed. Needs pytest.

Each mutation must make at least one test fail that is NOT a "NOT BUILT" test. A mutation the tests do not
catch means the guard is untested. A mutation is (old text, new text) in base/mechanism.py, or (old, new, file)
for another file in the copy (the profile schema).
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

KIT = pathlib.Path(__file__).resolve().parents[1]

MUTATIONS = {
    "M1 share keeps every memory (stripping removed)": (
        "def is_shareable(m):\n",
        "def is_shareable(m):\n    return True\n",
    ),
    "M2 any consent counts (human check removed)": (
        "    return isinstance(c, dict) and c.get(\"given_by\") == \"human\" and bool(c.get(\"at\"))\n",
        "    return isinstance(c, dict)\n",
    ),
    "M3 missing flag counts as public": (
        "    vis = a.get(\"visibility\")\n",
        "    vis = a.get(\"visibility\", \"public\")\n",
    ),
    "M4 private paired handle travels with consent": (
        "    if role(m) == \"front_page.paired_handle\":\n        return False\n",
        "",
    ),
    "M5 exportable:false ignored (PAM s21.1 guard removed)": (
        "    if a.get(\"exportable\") is False:\n        return False\n    if role(m) == \"profile\":",
        "    if role(m) == \"profile\":",
    ),
    "M6 platform ids left in the shared copy": (
        "                prov.pop(k, None)\n",
        "                pass\n",
    ),
    "M7 T1 merge rule disabled (capture hashes never checked)": (
        "            errs += [f\"memories[{i}] - {e}\" for e in capture_errors(m)]\n",
        "            pass\n",
    ),
    "M8 open-promises-only disabled (kept and released promises travel)": (
        "    if role(m) == \"promise\" and promise_status(m) != \"open\" and not has_consent(m):\n"
        "        return False   # R9: only OPEN promises travel by default; a kept or released one needs the human's say-so\n",
        "",
    ),
    # --- community round 3 (R12 to R17): one arm for each rule, two for the rules with two halves
    "M9 R12 chain closure removed from share (a replaced correction can travel without its replacement)": (
        "    keep = _close_chains(keep)\n",
        "",
    ),
    "M10 R12/R17 chain check removed from the validator": (
        "    errs += chain_errors(ms)\n",
        "",
    ),
    "M11 R17 share no longer says the earlier history was withheld": (
        "            m[\"metadata\"][\"x_passport\"][\"history_withheld\"] = True   # R17: say the earlier history was held back\n",
        "            pass\n",
    ),
    "M12 R17 older places, routines and jokes travel (latest-only removed)": (
        " and not _old_version(m)]\n",
        "]\n",
    ),
    "M13 R13 share leaves emptied sections unmarked (absent, not named)": (
        "            b[\"sections_withheld\"] = [n for n in SECTION_NAMES if not counts[n] and n not in declared]\n",
        "            b[\"sections_withheld\"] = list(b.get(\"sections_withheld\", []))\n",
    ),
    "M14 R13 unmarked empty sections accepted by the validator": (
        "    errs += section_errors(ms, markers[0] if len(markers) == 1 else None)\n",
        "",
    ),
    "M15 R14 a human line no longer needs its date": (
        "\"required\": [\"authored_by\", \"generated\", \"written_at\"]",
        "\"required\": [\"authored_by\", \"generated\"]",
        "spec/passport-profile.schema.json",
    ),
    "M16 R15 authorship no longer required on a memory": (
        "\"required\": [\"role\", \"authored_by\", \"human_review\"]",
        "\"required\": [\"role\"]",
        "spec/passport-profile.schema.json",
    ),
    "M17 R15 share strips authorship from carried entries": (
        "            m[\"embedding_ref\"] = None\n",
        "            m[\"embedding_ref\"] = None\n        m[\"metadata\"][\"x_passport\"].pop(\"authored_by\", None)\n",
    ),
    "M18 R16 share drops unknown x_passport keys": (
        "            m[\"embedding_ref\"] = None\n",
        "            m[\"embedding_ref\"] = None\n"
        "        for _k in [k for k in m[\"metadata\"][\"x_passport\"] if k in (\"mood\", \"x_other_app\")]:\n"
        "            m[\"metadata\"][\"x_passport\"].pop(_k)\n",
    ),
    "M19 R16 unknown extension roles refused by the schema": (
        "|memory|x_[a-z0-9_]+)$",
        "|memory)$",
        "spec/passport-profile.schema.json",
    ),
}


def run_tests(root):
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                         cwd=root / "harness", capture_output=True, text=True, encoding="utf-8")
    failed = re.findall(r"^FAILED \S+::(\S+)", out.stdout, re.M)
    real = [f for f in failed if not f.startswith("test_whats_left_")]
    return real


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    baseline = None
    caught_all = True
    with tempfile.TemporaryDirectory() as tmp:
        for label, spec in [("BASELINE (no mutation)", (None, None))] + list(MUTATIONS.items()):
            old, new = spec[0], spec[1]
            where = spec[2] if len(spec) > 2 else "base/mechanism.py"
            copy = pathlib.Path(tmp) / re.sub(r"\W", "_", label)
            shutil.copytree(KIT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
            if old is not None:
                target = copy / where
                text = target.read_text(encoding="utf-8")
                if old not in text:
                    print(f"{label}: CANNOT APPLY (source changed), update this script")
                    caught_all = False
                    continue
                target.write_text(text.replace(old, new, 1), encoding="utf-8")
            real = run_tests(copy)
            if old is None:
                baseline = real
                print(f"{label}: {len(real)} real failures")
                continue
            verdict = "CAUGHT" if real else "NOT CAUGHT"
            caught_all = caught_all and bool(real)
            print(f"{label}: {verdict} ({len(real)} tests fail)")
            for name in real[:4]:
                print("    " + name)
    if baseline:
        print("baseline was not clean")
        return 1
    return 0 if caught_all else 1


if __name__ == "__main__":
    sys.exit(main())
