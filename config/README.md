# What the weekly run reads

Swartz writes each week's file, `content/digests/{week_id}.json`, by following the files in this folder. The site only renders that file, and `scripts/validate-weeks.mjs` checks it against these rules before a week can merge.

| File | Decides |
| --- | --- |
| `sources.yaml` | Which feeds are read, and which section each one files under |
| `inclusion-rubric.md` | Which items make the week, and which are left out |
| `story-grouping.md` | When several pieces are one story, and which source leads it |
| `takeaway.md` | Each story's one-line takeaway and its 60-word summary |
| `briefing.md` | The Briefing lead and its five themes |
| `number-of-week.md` | The Number of the week |
| `top5-ranking.md` | The order of the Top 5, and the reason shown for each rank |
| `x-review.md` | How the weekly run reads X, and what X may add to a week |
| `x-watchlist.yaml` | The X accounts that run reads, by section |

A change to any of these files changes the next week. Earlier weeks stay as they were written.

## Not in the repo yet

These still live only in Swartz's workspace, so a run can't be reviewed or repeated from the repo alone:

- The code that fetches the sources, applies these rules, and writes the week file.
- The prompts Swartz uses with these rules.
- `framing-split-rubric.md` and `framing-split-lessons.md`, for the planned two-takes split (DAS-64).
- `top5-ranking-rubric.md` (Oct 14). `top5-ranking.md` restates its criteria from DAS-63, but its tie-breaks are a draft until the original replaces them.

When they land, put rules here in `config/` and code under `scripts/`.
