# Phase 3 UAT — AI Quality

Manual verification watch list (deferred from 03-CONTEXT.md `<deferred>`).

## Future UAT Watch (first 1–2 live Phase 3 weeks)

| # | Area | What to verify | Trigger to escalate |
|---|------|----------------|---------------------|
| 1 | Categorization accuracy | Spot-check 10–15 random clusters per week | Poor accuracy → few-shot examples ladder (03-CONTEXT) |
| 2 | Top N ranking quality | Read Briefing Sunday morning — missing or inflated stories? | Ranking escalation ladder (03-CONTEXT) |
| 3 | Weekly rollup voice + length | Sharp editor tone; ~150–200 words; ties week together | Prompt iteration |
| 4 | Partial publish at $2 cap | Set `pipeline.hard_stop_usd: 0.01` in `config/digest.yaml`; run once; confirm plain-English `partial-publish-notice`; restore cap | N/A — mechanism test |
| 5 | Per-category mini-rollup quality | Each section opener useful, not duplicate of cards | Prompt iteration |
| 6 | YouTube catch-up cascade | After `--only-pending-transcripts`, confirm re-summarize + dedup when transcript flips | D-68 integration |

## Automated coverage (03-05)

- `tests/budget/test_budget_halt.py` — budget halt + partial publish HTML
- `tests/reporting/test_pipeline_report_schema.py` — OBS-02 JSON shape
- `tests/test_cascade.py` — D-68 invalidation rules
- `tests/test_cli_phase3.py` — D-22 `--help`, PIPELINE-05 double render, PIPELINE-06 resume
