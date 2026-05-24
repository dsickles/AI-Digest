---
phase: 4
slug: dashboard-archive
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-23
---

# Phase 4 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Python partition → JSON emitter | Routing decisions must not drift when extracted; `partition.py` is source of truth for LOCKED-01 | `DigestCard` lists → pre-partitioned `main_feed`, `footer_aside`, `briefing_top_n` |
| SQLite → JSON files → git | Committed digest JSON must never contain secrets or stack traces | Week metadata, cards, `pipeline_notes` plain-English strings |
| pipeline_report → pipeline_notes | Reader-facing strings only; no raw error payloads or category enums | Aggregated health counts → whitelisted copy templates |
| pipeline_notes → reader | Plain English only; no error class names or paths (D-24) | `summary_line` + `details[]` → Astro `<details>` |
| SQLite history → JSON | Read-only queries for silent-source streak; no secrets in output | Consecutive `empty_feed` weeks → silent-source detail line |
| Committed JSON → static HTML | Astro text interpolation auto-escapes; no `dangerouslySetInnerHTML` | Digest JSON fields → escaped HTML |
| External story URLs | Outbound links open in new tab with `noopener` | Publisher/article URLs → `<a target="_blank">` |
| Third-party images | No hotlinked YouTube thumbnails (D-A7b) | Card visuals → inline SVG / text badge only |
| git committed JSON → public static host | Static `web/dist` must contain zero API keys or env material | Built HTML/JSON → public CDN (Phase 5) |
| Backfill CLI | Render-only path; no credential loading beyond existing lazy imports | SQLite read → JSON emit; no LLM stages |
| build output → static host | Permalink hrefs and `rel=canonical` must match on-disk routes case-exactly | Week slugs → `/digest/2026-w21/…` paths |
| npm supply chain (Plan 04-03) | Only vetted Astro/Tailwind packages in `web/` | Package manifests → `node_modules` at build time |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-4-01-01 | Tampering | partition.py extract | mitigate | pytest partition suite unchanged; no logic edits during move | closed |
| T-4-01-02 | Tampering | REQUIREMENTS drift | mitigate | Mechanical reconciliation to 3 tabs per PROJECT.md | closed |
| T-4-01-SC | Tampering | npm/pip installs | accept | No package installs in this plan | closed |
| T-4-02-01 | Information disclosure | digest_json.py | mitigate | Whitelist pipeline_notes fields; grep tests forbid GEMINI/sk- in emitter | closed |
| T-4-02-02 | Tampering | LOCKED-01 routing | mitigate | Partition parity tests; Astro not in routing path | closed |
| T-4-02-03 | Tampering | schema_version drift | mitigate | Pydantic `Literal[1]`; tests assert schema_version | closed |
| T-4-02-SC | Tampering | npm/pip installs | accept | No npm in this plan | closed |
| T-4-03-01 | Information disclosure | static build output | mitigate | No `.env` in web/; no API keys in components | closed |
| T-4-03-02 | Spoofing | Card links | mitigate | `rel=noopener noreferrer` on `target=_blank` | closed |
| T-4-03-03 | Tampering | Zod schema | mitigate | `schema_version` literal 1; build fails on bad JSON | closed |
| T-4-03-SC | Tampering | npm install | mitigate | RESEARCH Package Legitimacy: astro/tailwindcss/@tailwindcss/vite Approved [VERIFIED] | closed |
| T-4-04-01 | Spoofing | external links | mitigate | `rel=noopener noreferrer` on all Card links | closed |
| T-4-04-02 | Information disclosure | PlayIcon/thumbnails | mitigate | Inline SVG only; grep dist for ytimg.com | closed |
| T-4-04-03 | Tampering | LOCKED-01 UI | mitigate | FooterAside only consumes `footer_aside[]`; no Astro partition | closed |
| T-4-04-SC | Tampering | npm | accept | No new packages this plan | closed |
| T-4-05-01 | Information disclosure | pipeline_notes | mitigate | Whitelist copy templates; tests forbid raw exception strings | closed |
| T-4-05-02 | Tampering | OBS-01 over-surface | mitigate | 3+ week empty_feed threshold unit tested | closed |
| T-4-05-03 | Repudiation | zero-state | mitigate | DOM omission tested; not CSS hidden | closed |
| T-4-05-SC | Tampering | npm | accept | No new packages | closed |
| T-4-06-01 | Information disclosure | web/dist | mitigate | grep GEMINI/sk- after build; PITFALLS #5 | closed |
| T-4-06-02 | Tampering | backfill wrong command | mitigate | Document render-only; UAT checks log absence of summarize | closed |
| T-4-06-03 | Tampering | LOCKED-01 regression W21 | mitigate | UAT compare footer_aside vs HTML; partition tests | closed |
| T-4-06-SC | Tampering | npm | accept | pnpm build only; packages already verified | closed |
| T-4-07-01 | Tampering | canonicalUrl / ArchiveList emit wrong slug | mitigate | pnpm build + dist grep: archive hrefs and canonical tags must match dist/digest/ dir names case-exactly | closed |

*Status: open · closed*  
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-4-01 | T-4-01-SC | Plan 04-01 is a Python module extract and docs reconciliation only; no new pip or npm dependencies introduced. | gsd-security-auditor | 2026-05-23 |
| AR-4-02 | T-4-02-SC | Plan 04-02 extends the Python JSON emitter and orchestrator only; no npm packages added to `web/`. | gsd-security-auditor | 2026-05-23 |
| AR-4-03 | T-4-04-SC | Plan 04-04 adds Astro components and pages using packages already installed in Plan 04-03; no new npm dependencies. | gsd-security-auditor | 2026-05-23 |
| AR-4-04 | T-4-05-SC | Plan 04-05 extends emitter tests and archive UI; no new npm packages. | gsd-security-auditor | 2026-05-23 |
| AR-4-05 | T-4-06-SC | Plan 04-06 runs `pnpm build` against the existing vetted dependency set from Plan 04-03; no new package installs. | gsd-security-auditor | 2026-05-23 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-23 | 24 | 23 | 1 | gsd-security-auditor |
| 2026-05-23 | 24 | 24 | 0 | /gsd-secure-phase remediation — added `test_emitter_source_has_no_api_key_prefix` |

### Verification Notes (2026-05-23)

- **T-4-01-01:** `tests/render/test_partition_cards_phase3.py` — 17 tests pass with `partition.py` at `pipeline/render/partition.py`.
- **T-4-01-02:** `.planning/REQUIREMENTS.md` DISPLAY-02/04 cite Briefing + three topic tabs (`Edtech`, `Business`, `Technical`).
- **T-4-02-01:** Whitelist implementation in `_build_pipeline_notes` (`pipeline/render/digest_json.py:256-336`) and `PipelineNotesJson` model (`:92-95`). Defense-in-depth grep tests: `test_emitter_source_has_no_gemini_string` (forbids `GEMINI`) and `test_emitter_source_has_no_api_key_prefix` (forbids `sk-`) at `tests/render/test_digest_json_schema.py:55-66`. Both pass against current emitter source.
- **T-4-02-02:** `tests/render/test_digest_json_partition_parity.py`; `web/src` has no `_partition_cards` or partition routing (only label mirrors in `topics.ts`, `copy.ts`).
- **T-4-02-03:** `DigestDocument.schema_version: Literal[1]` at `digest_json.py:104`; `test_emitted_json_has_schema_version_one_and_validates` at `test_digest_json_schema.py:31-46`.
- **T-4-03-01:** No `.env` under `web/`; no `GEMINI`, `API_KEY`, or `sk-` in `web/src/`.
- **T-4-03-02 / T-4-04-01:** `rel="noopener noreferrer"` on Card and FooterAside outbound links (`Card.astro:41,59,82`; `FooterAside.astro:29`).
- **T-4-03-03:** `schema_version: z.literal(1)` in `web/src/content.config.ts:44,72`.
- **T-4-03-SC:** Package Legitimacy Audit in `04-RESEARCH.md:113-121` — astro, tailwindcss, `@tailwindcss/vite` Approved [VERIFIED].
- **T-4-04-02:** `PlayIcon.astro` inline SVG (`:5-12`); no `<img>` or `ytimg` in `web/src/`; post-build `web/dist` grep for `ytimg` — no matches.
- **T-4-04-03:** `FooterAside.astro` consumes `items` prop only; `DigestBriefing.astro:18` passes `data.footer_aside`.
- **T-4-05-01:** Template-only `_build_pipeline_notes`; `test_fetch_failure_copy_in_details` asserts plain-English output without raw `fetch_timeout` category string (`test_pipeline_notes.py:117-138`).
- **T-4-05-02:** `test_silent_source_requires_three_consecutive_empty_weeks` (`test_pipeline_notes.py:38-114`).
- **T-4-05-03:** `test_zero_state_returns_none` (`:28-35`); `PipelineNotes.astro:16` conditional render (no `display:none` / `hidden`).
- **T-4-06-01:** Post-build grep `web/dist` for `GEMINI`/`sk-` — no matches; aligns with PITFALLS #5 (`.planning/research/PITFALLS.md:134-156`).
- **T-4-06-02:** README Phase 4 dashboard section (`README.md:221-246`); `tests/test_pipeline.py::test_render_does_not_call_llm` (`:206-228`); backfill render-only documented in `04-06-SUMMARY.md:67`.
- **T-4-06-03:** `04-UAT.md` test 1 LOCKED-01 JSON partition evidence; partition parity + phase3 regression tests green.
- **T-4-07-01:** `pnpm build` exit 0; `web/dist/archive/index.html` href `/digest/2026-w21` matches `web/dist/digest/2026-w21/`; canonical tags on `dist/index.html` and `dist/business/index.html` use lowercase `/digest/2026-w21` paths; `canonicalUrl.ts:5` applies `toLowerCase()`.

### Unregistered Flags

None — no `## Threat Flags` sections found in plan SUMMARY files.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-23
