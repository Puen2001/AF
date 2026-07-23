# Visual Sourcing Flow (research 2026-07-23)

Operator direction: footage should be REAL and fit the product (from Shopee /
platform listings), not stock-first, not AI-generated. This flow encodes that
with the legal line drawn honestly.

## Per shot-line: classify, then route

Each shot from the planner is tagged **product / b-roll / trend-reference** and
routed down its own source chain.

### 1. Product shots — the footage that sells (source priority)
1. **Manufacturer press kit / brand affiliate media** — cleanest license (issued
   for reuse), but rare for long-tail Shopee sellers.
2. **Own product photography** — if the unit is ever bought.
3. **Platform listing media via the AFFILIATE API** — Shopee Affiliate Open API
   (GraphQL) returns product image URLs; **AliExpress Affiliate API explicitly
   ships "promotional materials"** (cleanest of the platform options — designed
   for promotion). TikTok Shop "Affiliate Creatives" only work *inside* TikTok
   Ads Manager, not external reuse.
4. **Transform, don't raw-copy:** run the listing image through **rembg / BiRefNet
   background removal → composite onto a clean/branded backdrop** (free,
   self-hosted). This is both better-looking AND legally safer (transformative
   work vs. a copy-paste of someone's photo). **Highest-leverage build.**
5. Raw listing cutaway + visible affiliate disclosure — last resort.

⚠️ **Honest legal note:** reusing a raw platform listing image baked into a video
is an **open legal question**, not a cleared right — the affiliate APIs hand you
the URL but don't clearly grant video-reuse. So: prefer the **transformed**
(bg-removed + composited) version, prefer manufacturer/own media for any shot a
purchase decision leans on, and keep a per-asset license ledger (source + license
+ date) as the audit trail.

### 2. Generic b-roll (illustrative, no product)
`Pexels` (primary, portrait filter) → `Pixabay` → `Coverr` → **CLIP re-rank the
top ~10 returned candidates** against the actual script line (open_clip,
self-hosted, free, runs on Mac CPU). CLIP re-rank is the one cheap upgrade that
fixes literal-keyword mismatches (the "open rates → footage of opening mail"
failure the commercial tools have) — the paid tools are NOT smarter at matching,
their only moat is a bigger catalog. Stock is the FALLBACK here, per operator
preference — used only for lines that aren't the product.

### 3. Trend / real-person reference
**Never resolve to identifiable footage/photo of the real person** when the
segment promotes a product — that's right-of-publicity territory (the operative
law, not copyright). Route to generic category b-roll ("viral phone leak" →
generic phone-in-hand, not the actual named person). Getty/AP editorial licensing
bars standalone monetized reposting anyway, so it's effectively unavailable here.
This is the "reference the trend, don't steal the likeness" rule, operationalized.

### ❌ Not sourced from: raw YouTube / TikTok / X clips
Downloading other creators' clips = copyright infringement + destination-platform
"reused/inauthentic content" strikes + Content-ID/DMCA exposure. Only exception:
**YouTube Creative-Commons-filtered** clips (legitimately reusable) — those are OK.

## What's buildable now vs gated

- **Buildable now (฿0, no signup):** the classify+route structure; CLIP re-rank of
  stock candidates; rembg/BiRefNet bg-removal + composite capability; the license
  ledger. Free stock chain (Pexels/Pixabay/Coverr) once keys exist.
- **Gated on operator:** Shopee/AliExpress affiliate API access (the product-media
  source) needs the affiliate signup + API credentials. That's the heart of the
  product-shot chain — until then, product shots fall back to composited stock
  product photos or the transformed listing image if supplied manually.

## Assembly (unchanged, already built)
shot list → source per line (above) → duration-sync to TTS → FFmpeg render with
narration-aligned cuts + Ken Burns + captions + music. The paid faceless tools do
nothing here we don't already do in FFmpeg for free.
