# Strict Script-to-Footage + Story-First Redesign — Build Plan

**Spec source:** operator directive 2026-07-24 (strict sentence-level footage matching +
story-first content engine). This file tracks what is built vs aspirational so the
redesign survives across sessions.

## Core rule (the one that governs everything)
For every narration unit: *"If the audio were muted, would this footage still visually
communicate THIS exact sentence?"* If no → reject. Never fill with generic/topical/random
footage. **Better to show an honest card than misleading footage.**

## Evidence that motivated this
Label-printer run (vision-guided v1): accepted a MakerBot **3D printer** as "a printer in
use" (same category, wrong product) and gradient-filled 3 of 6 shots. Both failures this
plan must kill.

## Feasibility (honest)
| Capability | Verdict |
|---|---|
| Sentence-level shot units + structured visual requirements | ✅ buildable (LLM) |
| 10+ query variants per unit | ✅ buildable (LLM) |
| Strict per-criterion vision scoring + thresholds | ✅ buildable (Claude vision on keyframes) |
| **Exact-product rejection** (label printer ≠ 3D printer) | ✅ buildable (vision judge, explicit negatives) |
| Transcript/subtitle-guided timestamp | ✅ buildable (yt-dlp auto-subs) |
| Object/action recognition, "embeddings" | ✅ approximated by Claude vision on keyframes + OCR |
| Honest NO-FOOTAGE → product image / text card / infographic | ✅ buildable (text card now; product-image fetch next) |
| QC / Visual-Continuity agent (2nd-pass reject + re-search) | ✅ buildable (second vision pass) |
| Sources: YouTube (+ auto-subs) | ✅ live |
| Sources: TikTok | 🟡 best-effort via yt-dlp |
| Sources: Reddit/X/FB/IG/Amazon/Shopee/Lazada/news/Kickstarter | 🔴 no reliable keyless pull — pluggable stubs, honest labels |
| Story-first structure (hook→…→soft CTA), deep product+market research, use-case discovery | ✅ buildable (scriptgen upgrade) — the system already has story-first mode to extend |

## Phases
- **P1 — Strict footage matching (IN PROGRESS).** Strict vision judge (exact product,
  per-criterion score, reject thresholds) · kill gradient filler → honest no-footage card ·
  sentence-level shot units + forbidden-visuals · multi-query. Prove on label printer.
- **P2 — QC agent.** Second-pass Visual-Continuity+Relevance review of the assembled
  storyboard; reject + re-search; repetition/timeline/subject-jump checks.
- **P3 — Story-first script engine.** Deep product + market research; story-idea generation;
  hook design; hook→context→problem→escalation→event→evidence→peak→reveal→product→use-case→soft-CTA;
  footage follows the SCRIPT not the product.
- **P4 — Source expansion + footage memory.** TikTok/others where feasible; persistent
  `footage` table (dedup/reuse/alternatives); richer license metadata.

## Non-negotiables
Accuracy > visual quality. No filler. Honest no-match. Exact product/event/timeline match.
