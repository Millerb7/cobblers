---
name: qa-review
description: Run the deterministic QA pipeline over a change and render the report — analyse the diff, map affected features, generate policy cases, run the required test suites, and summarise. Use when explicitly asked to QA a change, to check what a change puts at risk, or to debug the QA system itself. Not part of finishing a ticket.
---

# QA review

Runs the pipeline in `qa/`. Everything here is deterministic; a model is
involved only in the optional review step at the end, and only if asked for.

Do not invoke automatically after normal feature implementation. Independent QA
belongs to the PR workflow and starts when a human marks the draft PR ready for
review — running it yourself is implementation grading its own work.

This skill is intended for:

- CI-triggered QA review
- explicit local QA review
- QA-framework development/debugging

**Inputs:** a base ref (default `main`), or an explicit list of changed files.

## Steps

```bash
pip install -r qa/requirements.txt      # first run only

python qa/scripts/analyze_diff.py --base main --head HEAD
python qa/scripts/build_plan.py
python qa/scripts/run_qa.py             # --no-tests if the build is unavailable
python qa/scripts/summarize_results.py
python qa/scripts/render_report.py
```

Read `qa-output/qa-report.md`. It is short by design; `qa-output/qa-result.json`
holds every case.

## Optional AI step

Only if the manifest reports `deep_review_eligible` **and** the user asked, or
there are deterministic failures worth interpreting: hand
`qa-output/qa-manifest.json` and `qa-output/qa-result.json` — and nothing else
— to the `qa-reviewer` agent, write its JSON to `qa-output/ai-review.json`,
then re-run `summarize_results.py --ai-review qa-output/ai-review.json` and
`render_report.py`.

Do not paste full test logs into the agent's context. Do not ask it to
re-derive boundary values or restate passing results.

## Reporting back

Give the user the verdict, risk, counts, any blocking findings, and the
coverage gaps worth acting on. Do not paste the whole case list into the
conversation — point at the artifact.

If a suite could not run, say `NOT_EXECUTED` or `BLOCKED` and why. Never
describe an unexecuted case as passing.
