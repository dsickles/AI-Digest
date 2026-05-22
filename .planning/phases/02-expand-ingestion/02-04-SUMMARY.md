---
phase: 02-expand-ingestion
plan: "04"
status: complete
type: execute
wave: 4
requirements:
  - INGEST-03
completed: 2026-05-22
self_check: PASSED
---

# Plan 02-04 — `--only-pending-transcripts` catch-up + D-22 discoverability

## What shipped

The cloud → residential catch-up path that closes the D-23 free-first
transcript strategy. A weekly cloud ingest can now legitimately leave
YouTube items at `transcript_status='pending_local'`; the operator runs
the same pipeline from a residential network with one documented CLI
flag and pending items advance to `ok` (or `missing` if YouTube confirms
captions don't exist). The D-22 discoverability triad — CONTEXT decision +
README + `--help` + UAT — is satisfied for this hidden capability.

## Tasks

| Task | Files touched | Commit |
|------|---------------|--------|
| 2-04-01 — Catch-up ingest path (CLI + orchestrator + adapter + store) | `pipeline/run.py`, `pipeline/orchestrator.py`, `pipeline/adapters/youtube.py`, `store/db.py`, `tests/test_catch_up.py` | `1ea55df` |
| 2-04-02 — README catch-up section + Phase 2 UAT checklist | `README.md`, `.planning/phases/02-expand-ingestion/02-UAT.md` | `d2b4187` |
| 2-04-03 — Full-suite gate (integration test landed in 2-04-01) | (no new files) | covered by `1ea55df` |

## Symbols added

- `store.get_pending_transcript_items(conn, *, source_id=None)`
- `store.update_item_transcript(conn, item_id, *, transcript_status, raw_content=None)`
- `pipeline.adapters.youtube.YoutubeAdapter.fetch_transcript(video_id, *, catch_up=False)`
- `pipeline.adapters.youtube._classify_transcript_error(exc, *, catch_up=False)` — new `catch_up` kwarg
- `pipeline.orchestrator._ingest_pending_transcripts(conn, log, stats)`
- `pipeline.orchestrator.run_ingest(..., only_pending_transcripts=False)` kwarg
- `pipeline.orchestrator.run_all(..., only_pending_transcripts=False)` kwarg
- `pipeline.run._PENDING_TRANSCRIPTS_HELP` + `_add_only_pending_transcripts_arg`
- `tests/test_catch_up.py` (8 tests)
- `.planning/phases/02-expand-ingestion/02-UAT.md`

## Decisions honored

- **D-23 (free-first transcript strategy with local catch-up)** — Cloud
  ingest never sets `missing`; only the catch-up path with
  `catch_up=True` may flip `TranscriptsDisabled`/`NoTranscriptFound`/
  `TranscriptsNotFound` to `missing`. Network errors stay `pending_local`
  in both modes so retries are always available.
- **D-22 (hidden-capability discoverability triad)** — CONTEXT decision
  already documented; README has a "YouTube transcript catch-up" section
  with three worked examples; `uv run python -m pipeline.run ingest --help`
  surfaces `--only-pending-transcripts` with plain English; `02-UAT.md`
  has explicit catch-up checklist entries (tests 4–6).
- **D-24 (plain-English reader surface)** — No CLI flag syntax,
  `pending_local`, `transcript_status`, or other engineer tokens appear
  in the rendered HTML. The flag is operator-facing only.

## Verification

```
uv run python -m pipeline.run ingest --help | grep -i pending      # ✓
grep -q "only-pending-transcripts" README.md                       # ✓
uv run pytest tests/test_catch_up.py -x -q                         # 8 green
uv run pytest tests/ -q                                            # 68 green
uv run ruff check pipeline/ store/ tests/                          # clean
```

Live residential verification of an actual `pending_local → ok` transition
against the real YouTube transcript API is reserved for `02-UAT.md` test 5;
it requires an operator on a residential network and is out of scope for
the automated suite (validated per the 02-RESEARCH "Manual UAT" row).

## Self-Check: PASSED

- [x] All tasks executed (3/3, with 2-04-03 integration test landed inside 2-04-01)
- [x] Each task committed individually (2-04-01 catch-up code, 2-04-02 docs/UAT)
- [x] Full test suite green (68/68)
- [x] ruff clean
- [x] `--only-pending-transcripts` accepted by `ingest` and `all`, rejected by `summarize`/`render`
- [x] Successful catch-up writes both `transcript_status='ok'` AND new `raw_content`
- [x] `TranscriptsDisabled` in catch-up mode advances to `missing`
- [x] Still-blocked catch-up keeps `pending_local` (retry allowed)
- [x] Catch-up mode never dispatches to RSS adapters
- [x] No new dependencies (T-02-SC mitigated: same approved 1.2.4 pin)

## Deviations

- The integration test `test_catch_up_ok_updates_status_and_raw_content`
  asked for by Task 2-04-03 was written and committed alongside Task
  2-04-01 (in `tests/test_catch_up.py`, not `tests/test_youtube.py`). This
  is a deliberate split — catch-up tests are a coherent suite that lives
  in its own module rather than being scattered into the YouTube-adapter
  unit tests. Plan acceptance is unchanged (test runs as part of `uv run
  pytest tests/`).
- The default `transcript_fetcher` on `YoutubeAdapter.__init__` changed
  from a frozen-at-import-time function reference to a late-bound module
  lookup. This is a small backwards-compatible refactor that makes
  `monkeypatch.setattr("pipeline.adapters.youtube._transcript_text", ...)`
  affect every `YoutubeAdapter()` instantiation downstream — the
  alternative (passing fakes through every orchestrator call site) would
  have leaked test concerns into production code paths.

## Handoff to phase verification

Plan 02-04 closes the four-plan Phase 2 sequence. Remaining work for the
phase is wholly verification-shaped:

1. Run `uv run pytest tests/ -q` as the phase gate (current: 68 green).
2. Write `.planning/phases/02-expand-ingestion/02-VERIFICATION.md`
   summarising the requirement coverage (INGEST-03, INGEST-06), referencing
   the four plan summaries, and listing the manual UAT items in
   `02-UAT.md` as pending.
3. Update `.planning/STATE.md` + `.planning/ROADMAP.md` to mark
   Phase 2 complete and route to Phase 3.
4. Commit phase verification artifacts.
