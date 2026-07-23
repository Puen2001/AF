# Shopee Affiliate Thailand — Operator Playbook (research 2026-07-23)

Full research synthesis. The load-bearing corrections are flagged ⚠️. Sourced from
Shopee TH Help Center (primary), YouTube/TikTok official policy, ACCESSTRADE TH, and
cross-corroborated creator sources (community consensus flagged as such).

## ⚠️ The two findings that change the plan

1. **Commission reality — don't model "~20%".** Shopee's OWN base rate is thin:
   **2% on a direct order, 0.6% indirect, hard-capped at 225 THB/order.** The
   10–50% rates creators quote are **seller-funded "Extra Commission" (ค่าคอมพิเศษ)**
   on specific SKUs, not the platform base. → The pipeline must **filter product
   candidates to Extra-Comm-tagged SKUs** (via dashboard/Open API offer lookup), or
   the unit economics are off by an order of magnitude.

2. **TikTok caption links are NOT clickable** — only the bio-link field or a pinned
   comment work. Our "ลิงก์ในแคปชัน" convention is literally non-functional on
   TikTok. → **Platform-conditional CTA**: TikTok = caption says "ลิงก์ปักหมุดใน
   คอมเมนต์/ไบโอ" + auto-pinned first comment carries the link; YouTube = link as
   description line 1 (natively clickable, Shorts included).

## Mechanics

- **Signup**: affiliate.shopee.co.th, Shopee account + phone/email + one social
  channel + national ID/tax/Thai bank; "Approved" status needed within 3 months.
- **Cookie**: 7-day, last-click attribution (community-consensus for TH; strong).
- **Payout**: min 100 THB, biweekly to Thai bank once tax/bank "Approved".
- **Links**: (1) dashboard paste-to-convert (what solo creators use); (2) Open API
  GraphQL `generateShortLink` + **subIds** (tag each link to a video → attribution) —
  App ID/Secret requested by email after approval, ~2-week turnaround, official docs thin.
- **YouTube Shopping native tagging** with Shopee in TH — subscriber floor dropped
  10k → **500 subs** (Mar 2026). Milestone to design toward; a 0-sub channel doesn't
  qualify day one, so month-one uses description links.

## What converts

- **Categories**: beauty, fashion, home/living, problem-solving household items
  convert steadily; pure-novelty trend items spike and fade.
- **Price**: 79–299 THB impulse band; >500 THB needs justification (TikTok-audience
  proxy, not Shopee-native — treat as directional). Given the 225 THB cap, low-ticket
  high-conversion SKUs beat big-ticket ones for cold traffic.
- **Campaign dates** (9.9/10.10/11.11/12.12): concentrate intent + boosts — batch
  impulse content into the 2–4 day run-up.
- **SKU links only** are trackable (storefront links aren't) → always SKU-level.
- **Shopee Coins cashback**: upside-framed conversion lever, fits non-hard-sell tone.

## Pitfalls (account/earnings killers)

- ⚠️ **Self/same-device/IP/household purchase = fraud** — including QA-testing a
  generated link from a machine with a logged-in Shopee account. **Operational rule:
  never click-test links from any Shopee-logged-in device/network.**
- ⚠️ **"Low-quality, high-volume, templated, clickbait" content is explicitly
  prohibited** — the faceless automated pipeline is the profile most exposed. Story/
  hook diversity is now a **compliance requirement**, not just a quality nicety.
- Commission reversals: cancellations, returns, last-click loss (a newer link wins),
  unsubmitted tax info, 12-month unvalidated forfeit.
- Disclosure required (FTC "material connection" + Shopee) — we already do #ad.
- Branded short domain beats a raw cryptic Shopee URL in a low-trust caption/comment.

## Pipeline actions (ranked)

1. Platform-conditional CTA (TikTok pinned-comment/bio vs YouTube description-line-1).
2. Filter to Extra-Comm SKUs (needs affiliate Open API / dashboard).
3. Cap candidate price ~300–500 THB unless Extra-Comm confirmed.
4. Product attached only when story resolves around it (already enforced).
5. SKU link + subId per video for attribution.
6. Batch impulse content into 9.9/10.10/11.11/12.12 run-ups (feed the seasonal calendar).
7. Coin-cashback soft-CTA variant when the SKU has it.
8. Branded short-domain link wrapper at publish.
9. Hook/archetype diversity as an anti-templating budget.
10. Never QA links from a Shopee-logged-in device.
11. KYC/tax/bank done before first publish.
12. YouTube native Shopping tagging as a 500-sub milestone upgrade.
