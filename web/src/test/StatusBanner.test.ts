/**
 * Reader-confidence banner copy variants (OBS-03, D-24, ROADMAP SC4).
 *
 * Wave 0 of plan 05-01 landed these as RED stubs; plan 05-03 task
 * 5-03-03 turns them GREEN by exporting `bannerCopy` and the variant
 * union from `src/lib/copy.ts`. The Astro template at
 * `src/components/StatusBanner.astro` is a thin shell over the same
 * function, so we only need to test the pure TS surface here —
 * vitest stays decoupled from Astro's renderer.
 */
import { describe, it, expect } from "vitest";
import {
  bannerCopy,
  formatLastSuccessfulRun,
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

  it("priority: partial_cap wins over filling_in when both signals fire", () => {
    const input: StatusBannerInput = {
      pendingTranscriptsCount: 4,
      hardCapHit: true,
      deferredItemsCount: 2,
    };
    expect(bannerCopy(input).variant).toBe("partial_cap");
  });

  it("hardCapHit without any deferred items stays 'complete'", () => {
    // Defensive: a cap-hit flag with zero deferred items is a degenerate
    // signal (the cap could have been hit on an earlier run that drained
    // its work). The banner should not falsely claim items were skipped.
    const input: StatusBannerInput = {
      pendingTranscriptsCount: 0,
      hardCapHit: true,
      deferredItemsCount: 0,
    };
    expect(bannerCopy(input).variant).toBe("complete");
  });

  it("singular vs plural noun agreement", () => {
    const oneVideo = bannerCopy({
      pendingTranscriptsCount: 1,
      hardCapHit: false,
      deferredItemsCount: 0,
    });
    expect(oneVideo.text).toContain("1 video");
    expect(oneVideo.text).not.toContain("1 videos");

    const oneItem = bannerCopy({
      pendingTranscriptsCount: 0,
      hardCapHit: true,
      deferredItemsCount: 1,
    });
    expect(oneItem.text).toContain("1 item");
    expect(oneItem.text).not.toContain("1 items");
  });

  it("negative inputs are clamped to zero (defensive against bad report data)", () => {
    const result = bannerCopy({
      pendingTranscriptsCount: -5,
      hardCapHit: false,
      deferredItemsCount: -3,
    });
    expect(result.variant).toBe("complete");
  });
});

describe("StatusBanner timestamp surface (OBS-03 / ROADMAP SC4)", () => {
  it("includes a parseable ISO-8601 timestamp when updatedAt is set", () => {
    const iso = "2026-05-25T14:32:11Z";
    const result = bannerCopy({
      pendingTranscriptsCount: 0,
      hardCapHit: false,
      deferredItemsCount: 0,
      updatedAt: iso,
    });
    expect(result.lastSuccessfulRun).toBeDefined();
    expect(result.lastSuccessfulRun).toContain(iso);
    // The string is round-trippable through `new Date(...)`.
    const parsed = new Date(iso);
    expect(Number.isNaN(parsed.getTime())).toBe(false);
  });

  it("omits the timestamp line when updatedAt is null/undefined", () => {
    expect(
      bannerCopy({
        pendingTranscriptsCount: 0,
        hardCapHit: false,
        deferredItemsCount: 0,
        updatedAt: null,
      }).lastSuccessfulRun,
    ).toBeUndefined();

    expect(
      bannerCopy({
        pendingTranscriptsCount: 0,
        hardCapHit: false,
        deferredItemsCount: 0,
      }).lastSuccessfulRun,
    ).toBeUndefined();
  });

  it("formatLastSuccessfulRun preserves the original ISO string verbatim", () => {
    const iso = "2026-05-29T13:23:45Z";
    expect(formatLastSuccessfulRun(iso)).toContain(iso);
  });
});
