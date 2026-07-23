# Visual Storytelling Rules (research 2026-07-23) — encoded into the shot planner

The bug this fixes: the pipeline used thematic/mood b-roll (airplanes for a power-bank
story) as the DEFAULT. Per documentary craft that's backwards — literal
visual-narration matching is the baseline; metaphor is an advanced layer on top.
Rules below are now encoded in `scriptgen.SHOTS_PROMPT` + `broll`/`render`.

## Encoded rules

**Show the subject.** Product must appear at three structural beats: the hook (shot 1,
product mid-action/result — never an establishing/mood shot), once mid-explanation,
and the CTA/close. No more than 2 consecutive lines without a product-or-context shot.

**Match visual to the actual words.** Each line's shot depicts the concrete noun/verb
in that line ("battery swells" → swelling battery; "3C mark" → the label), not the
paragraph's general topic. Metaphor only when a line has no literal referent.

**Pacing.** Hook shots ≤1.5s; body 2–4s with variation (no 2 equal-length in a row);
reveal/payoff may hold 4–6s. Cuts snap to narration line-ends (done — voice `line_spans`).

**Motion on stills.** Every still gets Ken Burns 5–7s, ease in/out; push toward the
named detail; consecutive stills must not share pan direction/zoom polarity (done —
render alternates zoom in/out).

**9:16 composition.** Product in the center 70% vertical band; top ~7% / bottom ~18%
reserved for UI + captions (percentage-based). Captions in the bottom-safe band.

**Limited-assets mode (our reality: 2–3 clips + stills).** A clip appears ≤2× per
video, different crop each time, never back-to-back; interleave product stills between
clips to disguise scarcity.

## Sourcing implications (broll)

- Product shots (`type: product`) now also pull **still images** (Commons keyless +
  product-listing media later), Ken-Burns'd — because a product photo shown well beats
  a tangential clip. Video preferred where a matching one exists.
- The real product-shot source is the **Shopee listing media** (the exact item sold,
  license-clean) — reinforces the affiliate-feed signup. Pexels covers category footage.

Confidence: the matching/sandwich/Ken-Burns rules are solid documentary craft; the
exact pacing numbers are content-mill lore (directional only). Full research in the
session transcript.
