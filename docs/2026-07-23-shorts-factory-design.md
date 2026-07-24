# Shorts Factory — Design Spec

**Date:** 2026-07-23 · **Status:** Approved · **Owner:** Puen

## What this is

An automated Thai-language gadget-shorts factory: curiosity-driven short videos (TikTok primary, YouTube Shorts auto-crosspost) monetized through affiliate links. Built to run near-passively (~20 min/week of approval taps) alongside the owner's full-time work, startup, and Master's — at ฿0 marginal cost per video.

## Constraints (load-bearing)

- **Budget: ฿0.** Paid tools may be adopted *only* out of earned commissions. Free stack: Claude Code subscription (script engine, routed to sonnet), Edge-TTS, FFmpeg, Pexels free tier, YouTube Data API, Telegram bot, Shopee Affiliate.
- **Time: <3 hrs/week post-launch.** The human's only recurring job is the approval gate.
- **Base: Thailand.** This decides the market (below).
- **Compliance: hard rules.** Original scripts only; licensed/free media only; affiliate disclosure in every caption; no unofficial posting APIs; human approval on every video.

## Market decision: TH first, EN/US phase 2

1. **Access** — Shopee/Lazada affiliate = instant approval + Thai bank payout. US stack is mostly closed from TH (TikTok Shop US requires residency; Amazon Associates needs Payoneer/Wise *and* closes accounts without 3 qualifying sales in 180 days — so Amazon is opened only after traffic exists).
2. **Validation speed** — US English gadget shorts is maximally saturated; Thai-language gadget content is comparatively underserved and Thai viewers already buy on Shopee inside TikTok.
3. **Judgment edge** — the owner can natively judge Thai hooks during approval; American hooks would be guesswork.
4. **Cheap failure, transferable success** — if TH validates, EN is mostly a config change (language, sources, affiliate links). Day-90 gate decides.

Honest expectation: months 1–3 ≈ ฿0–2k/month. This is a compounding asset; what starts immediately is the machine, not the income.

## Content strategy

- Niche: gadgets (AI gadgets, desk setup, smart home, travel tech, under-฿1000 finds, EDC).
- Style: educational curiosity — "รู้มั้ยว่า…", hidden features, ทำไมใครๆ ก็ซื้อ — never ad-shaped. Structure: hook → curiosity → fact → soft product reveal → soft CTA (ลิงก์ในแคปชัน). 20–40 s.
- Cadence: 1/day generated; owner approves 5–7/week in one or two Telegram sessions.
- Anti-sameness: 3–4 rotating visual templates + varied hook bank (platform mass-produced-content policies are a real demonetization/suppression risk).

## Architecture

Linear 7-stage pipeline, SQLite state machine, launchd-scheduled on the M4 MacBook Air. No VPS, no agent framework — rejected as pre-revenue cost/overkill.

```
discover → scriptgen → voice → render → approve (Telegram) → publish → report
```

- **discover** — Shopee affiliate product feed + Google Trends TH; seed list fallback so the pipeline never blocks.
- **scriptgen** — `claude -p` (sonnet): Thai script from hook bank; second pass fact-checks claims against product-page text, rejects unverifiable claims.
- **voice** — Edge-TTS Thai neural voices (Premwadee/Niwat).
- **footage** — the **Footage Discovery Engine** (see `docs/FOOTAGE-DISCOVERY-ENGINE.md`): the system does NOT generate video. It researches, ranks, and recommends *existing* footage references per scene (auto-fetch tier for stock/CC/product-media; recommend-reference tier for YouTube/social, with attribution + licensing + confidence), and a human picks the best on the curation web page.
- **render** — FFmpeg 1080×1920: chosen footage + product-shot composites + kinetic Thai captions (Noto Sans Thai), hard cuts, Ken Burns, burn-in subs from script text.
- **approve** — video + caption + links → Telegram; ✅/❌ reply flips status. This gate is the entire recurring human job.
- **publish** — YouTube Shorts fully auto (Data API); TikTok = ready-to-post package delivered to phone for a 2-tap manual post (official Content Posting API applied for in parallel; never unofficial APIs).
- **report** — weekly digest to Telegram: top hooks/products/CTR + commissions → reweights next week's generation.

State: `products → scripts → videos` with status transitions `discovered → scripted → rendered → pending_approval → approved|rejected → posted`; `posts` and `metrics` tables close the loop. Stages are idempotent; failures alert via the existing batcave `telegram-send`.

## Build plan

See `/Users/puen/.claude-rico/plans/flickering-mapping-hearth.md` (4 weekend sessions: scaffold+scripts → render → approve+publish → launch+loop). MVP scope excludes: paid video-gen, VPS, multi-channel, EN/US, website/newsletter, brand deals — all revisit at the day-90 gate.

## Day-90 gate

Followers + first commissions decide: expand to EN/US (open Amazon Associates only then), iterate TH, or kill. Kill criterion honesty: if 90 days of consistent posting produces no traction signal, the loop — not the effort — is the problem.
