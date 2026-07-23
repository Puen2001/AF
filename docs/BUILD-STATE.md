# Shorts Factory — Build State (consolidated 2026-07-24)

Master index folding up every research thread + the story-first flow into one place:
what's IMPLEMENTED (✅), GATED on an operator signup (🔒), or PLANNED (⬜).

## The flow (v2, story-first)
```
Thailand trend/moment + audience + seasonal calendar        [trends.py] ✅
  → TOPIC (curiosity, trend/celebrity/season, ref-not-endorse guardrail) ✅
  → research the story (web, verified)                       [research.ensure_topic] ✅
  → STORY script: 3-draft → judge → opus polish → factcheck  [scriptgen.generate_from_topic] ✅
       ├ loop-close (replays=views) ✅   ├ hook-first, no brand intro ✅
       └ situational product-match + review-research quality gate ✅
  → SHOT PLAN (show product @ hook/mid/CTA, match noun/verb) [SHOTS_PROMPT] ✅
  → FOOTAGE per shot [broll.resolve] — adaptive multi-source ✅ (sources gated 🔒)
  → RENDER: hard cuts, Ken Burns, karaoke caps, music duck   [render.py] ✅
  → APPROVE (Telegram ✅/❌ via alfred bot) ✅ → PUBLISH (YT + TikTok handoff) ✅
```

## Research → implementation status

**TOGE study** (232K faceless channel): claim-first hooks ✅, declarative myth-bust
titles ✅, fixed hashtag block ✅, ~1-2/day cadence ✅, found-footage model ✅,
mascot bottom-center+logo ⬜ (needs asset).

**Shorts growth**: VVSA + avg-%-viewed are the ONLY reach signals (not likes) — feedback
loop must use them ⬜ (Phase 4 report.py); loop-close ✅; hook-first ✅; 1/day floor ✅;
⚠️ **inauthentic-content policy is channel-level & kills monetization** → structural
variation (angle+template rotation ✅, sameness-lint ⬜) is a survival requirement.

**Visual storytelling**: show product @ hook/mid/CTA ✅, match visual to concrete
noun/verb ✅, Ken Burns on stills ✅, product still support ✅.

**Auto-edit**: ✅ #1 hard cuts (killed blanket crossfade — the biggest "feels off" fix);
⬜ J-cut/L-cut (audio ±200ms offset), ⬜ SFX stings on cuts/emphasis (drop into
assets/sfx/), ⬜ word-pop caption color, ⬜ librosa emphasis-word detection →
punch-in zoom, ⬜ two-pass loudnorm. Verdict: stay on FFmpeg (renderers add nothing).

**Footage sourcing** (the bottleneck): HARD TRUTH — legal auto-pulled matching VIDEO =
stock APIs only. Affiliate feeds give product IMAGES not video (Amazon confirmed;
Shopee/AliExpress same pattern). Only product-VIDEO source = TikTok Shop scraper
(ToS-gray). Adaptive multi-source chain built ✅: product-listing media → product_shot
composite (rembg, ✅) → Pexels/Pixabay 🔒(key) → Wikimedia video ✅ → Archive.org
video ✅(keyless) → Wikimedia image ✅ → gradient ✅. CLIP re-rank ⬜. Product-video
hook (TikTok Shop) ⬜ (operator accepted ToS risk — "use all sources adaptively").

**AI voice**: edge-tts can't do SSML pauses (confirmed) → per-line synth + silence gaps
✅ (already the fix), rate -20% ✅. ⬜ FFmpeg polish chain (highpass+deesser+compressor),
⬜ variable gaps (longer before reveal). Phase-2: F5-TTS-THAI clone on gotham 🔒(voice sample).

**Product selection**: trending + review + sales + converts → triage weights all 4 ✅;
review-research quality gate (skip junk) ✅; Shopee-feed sales-rank/rating/Extra-Comm
filter 🔒 (needs affiliate API).

**Shopee affiliate**: base commission thin → target Extra-Comm SKUs 🔒; TikTok caption
links NOT clickable → pinned-comment/bio ⬜; ฿79-299 impulse band ✅ (in triage).

**Rejected** (researched, decided against): AI video generation (token cost), raw
YouTube/TikTok clip ripping (copyright/strikes), multi-agent frameworks, stock-as-only.

## Operator unblocks (all free, gate the 🔒 items)
1. Pexels API key → real stock b-roll. 2. Shopee affiliate signup → product media +
sales/review filter + Extra-Comm. 3. Google OAuth → YouTube publish. 4. Voice sample →
F5 clone. 5. Mascot image → brand overlay. 6. Activate Claude headless automation credit.
