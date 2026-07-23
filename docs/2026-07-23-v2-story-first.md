# v2 — Story-First Pipeline (design)

Shift from **product-first** (pick product → build story) to **story-first**
(find a trend/story worth telling → attach a product only when it fits). Driven by
studying @kyoryu_toge (TOGE, 232K subs) and operator direction, 2026-07-23.

## Flow

```
Thailand trend  +  audience profile  +  seasonal calendar
        │
        ▼
   TOPIC (curiosity, trend-riding, category-free)     ← trends.py
        │
        ▼
   research the story (web, verified)                 ← research.ensure_topic
        │
        ▼
   STORY script  (3-draft → judge → opus polish)      ← scriptgen.generate_from_topic
        │            └─ situational product-match: attach ONLY if a product truly fits;
        │               else pure curiosity (audience-building)
        ▼
   footage (product media → Pexels → gradient)  →  edit  →  approve  →  publish
```

## Hook engine — what the discovery stage hunts

1. **Live viral moments** — celebrities, YouTubers (e.g. Speed in TH), memes, dramas, game/movie/song launches.
2. **Seasonal calendar** (config `seasonal:`) — anticipatory: post BEFORE the wave.
   Songkran → waterproofing; rainy season → rain gear/dehumidifiers; hot season →
   fans/cooling; back-to-school, CNY, year-end gifts. `trends._active_events()`
   opens a window ~21 days ahead so content ships early.
3. **Evergreen curiosity** — myths, hidden mechanisms, counterintuitive facts.

**Guardrail (baked into prompts):** ride the trend, don't borrow the person.
Reference public figures/moments factually; NEVER fabricate endorsement or use
their footage/likeness without rights. Keeps us un-strikeable and authentic.

## TOGE-derived rules (data-backed, some directional)

- **Claim-first hook, 0–2s, zero intro** (all 20 top transcripts skip "สวัสดีครับ").
- **Declarative myth-bust titles**, not questions/superlatives (questions 0.43×,
  superlatives 0.20× vs avg — small-N, treated as reversible bets). Applied in MARKETING_PROMPT.
- **Fixed hashtag block** reused every video + 3 dynamic (config `brand.hashtags`).
- **Mascot bottom-center + logo top-left, every video** — brand IP (assets/brand/,
  render overlay TODO once a mascot exists).
- **~2 uploads/day sustained** — cadence as infrastructure; automation suits it.
- **Found-footage + narration model** — validates using product/manufacturer media
  as b-roll rather than filming.
- Structure is topic-agnostic: `[surprising claim/visual] → [why, plain] → [kicker]`.

## Voice

Pluggable backend (config `voice.provider`): `edge-tts` (default, cloud, word-timed)
or `f5-clone` (F5-TTS-THAI on gotham GPU — zero-shot clone of the operator's own
voice from one ~30s ref clip; factory/voice_f5.py). First-person narration in the
operator's cloned voice matches TOGE's single-narrator-POV pattern.

## Open (needs operator / next build)

- **Product finding with media + quality vetting** — Shopee affiliate feed supplies
  image/video URLs (→ footage) + ratings (→ quality gate). Gated on affiliate signup.
- **Mascot asset** — design one gadget/curiosity mascot (few static poses) → render overlay.
- **Voice sample** — one clean ~30s Thai clip of the operator → F5 clone on gotham.
- Pexels key — footage until product media exists.
- YouTube OAuth, bot already shared (alfred).
