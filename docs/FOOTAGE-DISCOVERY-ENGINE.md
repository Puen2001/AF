# Footage Discovery Engine — Design Spec

**Status:** Approved design (2026-07-24) · Replaces any "AI video generation" concept.

## Principle

**The system does NOT generate video.** It becomes an *elite footage researcher* —
it discovers, collects, organizes, ranks, and recommends **existing** footage from the
internet that best matches each scene of a story, so a human editor assembles a
compelling video from properly-sourced real footage.

> Think **"Perplexity + Palantir + Google Search" for footage references.**

Goal: dramatically cut the time a creator spends finding relevant footage, while
keeping **copyright awareness** and **source attribution** attached to every result.

## Two-tier output (the copyright-safe design)

Every candidate is classified so the human knows what they can do with it:

- **AUTO-FETCH (legal, downloadable now):** stock (Pexels/Pixabay/Coverr/Mixkit),
  Creative Commons (Wikimedia, Openverse, Flickr-CC), public-domain archives
  (Internet Archive, NASA, Library of Congress), and the product's OWN affiliate-feed
  media. These are downloaded into the candidate shortlist automatically.
- **RECOMMEND-REFERENCE (needs human review/licensing):** YouTube, TikTok, X, Reddit,
  Instagram, Facebook, news sites, press/media kits, manufacturer/brand channels.
  The engine returns the **reference** (URL, thumbnail, why-it-matches, license status,
  confidence) — it does NOT download or repost. The human reviews, then downloads or
  licenses where appropriate. This is what keeps the channel un-strikeable.

## Sources to search & index

**Video/social:** YouTube (+ official brand channels), TikTok, X, Reddit, Facebook,
Instagram, Vimeo, Bilibili/Douyin (Shenzhen gadget demos), Google Video Search.
**Commerce/product:** Amazon, Best Buy, B&H, Newegg, AliExpress, Shopee, Lazada, Temu
product videos; official manufacturer sites, product launch pages, spec pages.
**Launch/press:** Kickstarter, Indiegogo, Product Hunt, CES/MWC/IFA press galleries,
brand newsrooms, press kits, media kits.
**Images:** Google Images, Unsplash, Pexels, Pixabay.
**Open/public:** Wikimedia Commons, Openverse, Flickr (CC), Internet Archive, NASA,
Library of Congress, official government media, Creative Commons sources.
**News/editorial (licensed):** Getty, AP, Reuters (reference-only — licensing required).

*Suggested additions (not in the original list):* Pond5, Videvo, Videezy, Storyblocks/
Envato (paid, post-revenue), Behance/Dribbble (product motion/renders), retailer review
pages, YouTube's Creative-Commons filter (legitimately reusable), Coverr.

Not limited to these — the engine should propose new high-quality sources as it learns.

## Workflow

```
Story idea → research → break story into SCENES
  → for each scene, extract the visual requirement:
       emotion · action · object · location · event · camera angle · visual evidence
  → convert each into search intent (per-platform queries)
  → search multiple platforms in parallel
  → merge duplicates, detect near-identical clips
  → rank candidates by quality + match confidence
  → return per candidate:
       source URL · platform · creator · timestamp (if any) · thumbnail
       · why it matches · licensing status (if known) · confidence score · tier
  → HUMAN reviews the suggested sources (the curation web page)
  → HUMAN downloads (auto-fetch tier) or licenses (reference tier)
  → edit the final video
```

## AI responsibilities

Understand the story and each scene · convert scenes into search intent · search
multiple platforms · merge duplicate results · rank footage quality · detect similar
clips · organize reusable references · **build a searchable footage database** ·
**remember previously discovered footage** · recommend better alternatives · suggest
missing visual evidence · keep source attribution attached to every result.

The AI is NOT responsible for generating video. It is responsible for being the
best footage researcher a human editor could have.

## Footage database (memory)

A persistent store (`footage` table + local cache) of every discovered reference:
scene-requirement embedding, source URL, platform, creator, license, thumbnail,
confidence, tier, and whether the human used it. Enables: dedup across videos, instant
reuse of past finds, "better alternative" suggestions, and a growing owned index that
gets faster and smarter per video.

## Mapping to current build (status)

| Capability | Status |
|---|---|
| Scene → shot list with visual intent | ✅ (SHOTS_PROMPT, incl. type=product/context) — upgrade to the 7-field requirement ⬜ |
| Multi-source search + rank + quality gate | ✅ broll — now VIDEO-ONLY (Pexels/Pixabay/Wikimedia/Archive video; still-image sources dropped) |
| Reference-tier search (YouTube/social, real footage) | ✅ `footage.py` — keyless YouTube via yt-dlp, download & use directly (operator's channel, free use). TikTok/Shopee ⬜ |
| **Vision-guided moment selection** (pick the use-case frame, reject wrong-product/talking-head/box/accessory) | ✅ `footage.py` — proxy → timestamped contact sheet → Claude vision judge (`claude -p` + Read tool) → quality-extract |
| Rich result metadata (url/title/timestamp/why/confidence) | ✅ partial — url/title/ts/why/conf on each clip; creator/license ⬜ |
| Human curation web page (playable previews, pick best) | ✅ curate.py — now fed vision-matched video candidates |
| Footage database + memory (dedup, reuse, alternatives) | ⬜ new (`footage` table) |
| Outlier/proven-topic mining | ✅ outliers.py |
| AI video generation | ❌ REMOVED — explicitly out of scope |

**Built 2026-07-24:** vision-guided video-only footage engine (`factory/footage.py`).
Naive per-segment grabbing gave wrong-product / no-use-case clips; the engine now
*looks* at candidate footage and picks the moment that shows the product performing
its function, synced per shot. Auto path (`best_clip`) + curate path (`shortlist`).
Still open: other platforms (TikTok/Shopee), the persistent footage DB, richer license metadata.

## Explicitly out of scope

AI video generation (cost + authenticity). Downloading/reposting copyrighted clips
(the engine returns references for the human to license, never reposts).
