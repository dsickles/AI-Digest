/**
 * Wave 0 RED stub — Reader-confidence banner copy variants (OBS-03, D-24).
 *
 * Expected to FAIL until Plan 05-03 implements:
 *   - `src/components/StatusBanner.astro` exporting plain-English copy
 *     variants ("complete" / "filling in N videos" / "partial — N items
 *     skipped this week") driven by `pipeline_notes` + `budget` fields
 *     in the per-week report JSON.
 *   - `src/lib/copy.ts` exposing the variant strings so the banner and
 *     this test agree on a single canonical source (D-24).
 *
 * Until Plan 05-03 lands and Plan 05-03 wires up vitest in `web/`, this
 * file deliberately fails import — that satisfies the Wave 0 RED stub
 * contract from 05-VALIDATION.md.
 */
import { describe, it, expect } from "vitest";
import {
  bannerCopy,
  type StatusBannerInput,
} from "../lib/copy";

describe("StatusBanner copy variants (OBS-03 / D-24)", () => {
  it("complete: full digest, no pending transcripts, no cap hit", () => {
    const input: StatusBannerInput = {
      pendingTranscriptsCount: 0,
      hardCapHit: false,
      deferredItemsCount: 0,
    };
    expect(bannerCopy(input).variant).toBe("complete");
  });

  it("filling-in: cron published but home worker has not picked up yet", () => {
    const input: StatusBannerInput = {
      pendingTranscriptsCount: 3,
      hardCapHit: false,
      deferredItemsCount: 0,
    };
    const result = bannerCopy(input);
    expect(result.variant).toBe("filling_in");
    expect(result.text).toContain("3");
  });

  it("partial: weekly spend cap reached, N items skipped", () => {
    const input: StatusBannerInput = {
      pendingTranscriptsCount: 0,
      hardCapHit: true,
      deferredItemsCount: 7,
    };
    const result = bannerCopy(input);
    expect(result.variant).toBe("partial_cap");
    expect(result.text).toContain("7");
    expect(result.text.toLowerCase()).toContain("skipped");
  });

  it("D-24: no internal sentinel values leak into reader copy", () => {
    const input: StatusBannerInput = {
      pendingTranscriptsCount: 0,
      hardCapHit: true,
      deferredItemsCount: 2,
    };
    const text = bannerCopy(input).text;
    expect(text).not.toMatch(/deferred_budget/);
    expect(text).not.toMatch(/quota_exhausted/);
    expect(text).not.toMatch(/summary_status/);
  });
});
