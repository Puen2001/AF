# YouTube Shorts Growth & Channel-Ops Playbook (research 2026-07-23)

Rigorously sourced — separates YouTube-official signals from vendor-blog noise.
Actionable items marked ✅ done / ⬜ to-do / ⚠️ risk.

## The load-bearing facts (official / one real dataset)

- **Only two metrics drive distribution: "Viewed vs Swiped Away" (VVSA) + average-%-
  viewed.** Likes/comments/shares showed NO relationship with Shorts performance
  (Galloway/Gileta 3.3B-view study). → Build the feedback loop on VVSA, ignore vanity
  + don't do comment-bait mechanics.
- **Per-video testing** — a 0-sub channel gets genuinely tested (explore→expand), one
  bad video doesn't hurt the channel. No "momentum" to protect. Cold-start is real,
  not shadow-throttled.
- ⚠️ **EXISTENTIAL: the July 2025 "inauthentic content" policy is channel-level and
  precision-targets low-variation automated pipelines** — "template with little
  variation across videos, easily replicable at scale" = whole channel demonetized.
  This is aimed exactly at our production model. Variation in hook structure, pacing,
  visuals, voice — not just swapped topic text — is a survival requirement.

## Applied now ✅

- **Hook-first, no brand intro before the hook** — the first line carries all the VVSA
  weight; branding-first is pure cost. (Our claim-first hooks already do this.)
- **Loop-close the story** — last line returns to the hook so replays feel seamless;
  replays count as views since Mar 2025. (Just encoded in both script prompts.)
- **1/day cadence floor** (not 2/day early) — consistency matters, but volume of
  mediocre-hook content dilutes + doesn't substitute for hook quality. (config = 1.)
- **Angle + template rotation** (5 story angles, rotating render templates) — the
  first layer of the anti-templating defense.

## To build ⬜

- **Feedback loop on VVSA + avg-%-viewed** (report.py / Phase 4): pull these from the
  YouTube Analytics API as the fitness function for hook/format iteration — NOT views
  or likes. Add `vvsa`, `avg_pct_viewed` to the metrics table.
- **Structural-sameness lint**: diff recent scripts/renders for templated repetition
  before it becomes a channel-level monetization risk. The anti-templating policy is
  channel-scoped, so this is worth automating even if imperfect.
- **Description link + link card** (card is YPP-gated) — Shorts have NO end screens.
  Caption/description link is the only day-one affiliate mechanism.

## Operator habits

- **Weekly**: sort last week's Shorts by avg-%-viewed; read the retention graph on
  top/bottom 3 — sharp early drop = hook problem, gradual bleed = pacing problem. Feed
  that back into next week's template, not just "new topic."
- **Posting time**: no credible Thai-specific data exists — set the schedule from your
  own Studio → Audience "when viewers are on" once you have 2 weeks of data. Don't
  trust generic "5–9pm" guesses.
- **Advanced Features verification** early (passive 2-month path) → unlocks community
  Posts without a sub threshold.
- **Thumbnails**: skip optimization for v1 — they don't appear in the swipe feed where
  cold-start discovery happens (only in 5 other surfaces). Revisit once search/sub
  traffic is material.
- **Don't judge a format before ~20–30 published Shorts** — below that is explore/
  exploit noise, not signal.
- **Scale ceiling**: 2–3 channels max per solo operator (QC burden of the anti-
  templating requirement doesn't scale linearly).

## Confidence
Levers on VVSA, loop-close, hook-first, anti-templating policy, no-end-screens rest on
official docs / one real dataset — high confidence. Cadence, timing, thumbnail,
20-30-video, 2-3-channel are converged vendor consensus — validate against own data in
60–90 days.
