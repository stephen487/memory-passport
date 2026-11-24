# How to carry this on: memory-passport

This kit is an idea with a proof and a spec. Enki Labs will not build the finished product. You can.

## What you have

1. `BRIEF.md` the technical obstacle, the mechanism, who would buy it, and quoted sources.
2. `base/` the smallest code that proves the mechanism can work.
3. `harness/` tests that define "done". Most fail on purpose. Each failure says what to build.
4. `LICENSE` MIT. You may use, change, sell and fork it.

## How to carry it on

1. Run the harness: `cd harness && python -m pytest -q`. Note which tests pass. Those are proven.
2. Pick one failing test. Its message names the thing to build. Work from `BRIEF.md` "What's left for you".
3. Build it in your own code, outside `base/` if you prefer. Do not weaken or delete a test to make it pass. If a test is wrong, say so in an issue and change it in the open.
4. When the harness is green, your kit is done. Say so in your README.

## Rules for contributors

- Keep the harness stdlib plus pytest. No network calls in tests.
- Keep the pass/fail split honest in your README. Do not claim a feature the harness does not test.
- If you find an existing tool that already does this, record it in BRIEF.md under "Existence".

## Questions

Open an issue on the repository this kit is published in.
