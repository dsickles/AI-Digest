/** Reader-surface copy — mirrors pipeline/render/partition.py (D-24).
 *
 * StatusBanner copy lives here too so vitest can exercise the variant
 * logic without rendering an Astro component. The Astro template at
 * `src/components/StatusBanner.astro` is a thin shell over
 * {@link bannerCopy}.
 */
export const BRIEFING_HEADER_TEMPLATE = 'Briefing — Top {n} this week';

export const WEEKLY_ROLLUP_FAILURE_COPY =
  "This week's narrative roll-up couldn't be generated. The Top {n} stories are below.";

export function formatBriefingHeader(topN: number): string {
  return BRIEFING_HEADER_TEMPLATE.replace('{n}', String(topN));
}

export function formatWeeklyRollupFailure(topN: number): string {
  return WEEKLY_ROLLUP_FAILURE_COPY.replace('{n}', String(topN));
}

/**
 * StatusBanner inputs — sourced from the per-week report JSON
 * (`web/src/content/reports/{week_id}.json`) and the pending-transcript
 * count derived from the digest cards.
 *
 * `updatedAt` is the digest's `updated_at` ISO timestamp. When provided,
 * the banner surfaces a "Last successful run …" line so the reader can
 * tell the missed-run case from a fresh full-success at a glance
 * (OBS-03 / ROADMAP SC4).
 */
export interface StatusBannerInput {
  pendingTranscriptsCount: number;
  hardCapHit: boolean;
  deferredItemsCount: number;
  updatedAt?: string | null;
}

export type StatusBannerVariant =
  | 'complete'
  | 'filling_in'
  | 'partial_cap';

export interface StatusBannerCopy {
  /** Stable variant identifier — tests and Astro template branch on this. */
  variant: StatusBannerVariant;
  /** Primary reader-facing line. Plain English, never exposes
   * internal sentinel strings (D-24). */
  text: string;
  /** Secondary "Last successful run …" line; omitted when no
   * timestamp is available so the banner stays minimal. */
  lastSuccessfulRun?: string;
}

/** Locked reader-surface phrasing — referenced by tests and template. */
const COMPLETE_COPY =
  "This week's digest is complete.";
const CAP_LABEL = 'skipped';

function pluralize(n: number, singular: string, plural?: string): string {
  return n === 1 ? singular : (plural ?? `${singular}s`);
}

/**
 * Resolve banner copy from report-JSON inputs.
 *
 * Variant precedence (highest wins):
 *   1. `partial_cap` — weekly spend cap hit AND deferred items exist.
 *   2. `filling_in` — pending YouTube transcripts (cron published but
 *      home worker hasn't drained yet).
 *   3. `complete` — full digest, no pending work.
 *
 * The order matches the reader's anxiety hierarchy: a cap hit is the
 * loudest signal ("we skipped real content"), pending transcripts are a
 * soft "more is coming" signal, and complete is the steady state.
 */
export function bannerCopy(input: StatusBannerInput): StatusBannerCopy {
  const pending = Math.max(0, input.pendingTranscriptsCount);
  const deferred = Math.max(0, input.deferredItemsCount);

  let variant: StatusBannerVariant;
  let text: string;

  if (input.hardCapHit && deferred > 0) {
    variant = 'partial_cap';
    const noun = pluralize(deferred, 'item');
    text =
      `Partial week — ${deferred} ${noun} ${CAP_LABEL} this week after the weekly spend cap was reached.`;
  } else if (pending > 0) {
    variant = 'filling_in';
    const noun = pluralize(pending, 'video');
    text = `Filling in ${pending} ${noun} — refreshes when the home worker finishes.`;
  } else {
    variant = 'complete';
    text = COMPLETE_COPY;
  }

  const out: StatusBannerCopy = { variant, text };
  if (input.updatedAt) {
    out.lastSuccessfulRun = formatLastSuccessfulRun(input.updatedAt);
  }
  return out;
}

/**
 * Format the digest's `updated_at` as a reader-friendly "Last successful
 * run …" string. We keep the raw ISO inside the output so the test (and
 * a curious reader inspecting the page source) can parse it back.
 */
export function formatLastSuccessfulRun(iso: string): string {
  // The ISO string IS the parseable timestamp — including it verbatim
  // means the page source carries a machine-readable value alongside
  // any human-friendly formatting a future refinement might add.
  return `Last successful run: ${iso}`;
}
