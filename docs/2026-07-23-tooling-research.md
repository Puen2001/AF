# Tooling Research — pre-Phase-3 sweep (2026-07-23)

Four parallel research passes: OSS shorts-factory landscape, agent/harness patterns,
local Thai model stack, platform+affiliate APIs. Synthesis below is decision-oriented;
each claim traces to primary sources checked during the sweep.

## Verdicts that change Phase 3

1. **YouTube OAuth verification is a real pre-launch blocker (plan gap found).**
   An OAuth app in "Testing" mode gets refresh tokens that expire every 7 days
   (`youtube.upload` is not an exempt scope) — an unattended pipeline breaks weekly.
   Escape = publish app to Production **and** complete Google's OAuth verification
   (needs a public privacy-policy URL + scope justification; days-to-weeks review).
   → Phase 3 ships with weekly re-auth accepted; verification submission becomes an
   operator task at Phase 3 start, not launch day. Privacy policy page: free GitHub
   Pages. Source: support.google.com/cloud/answer/15549945.

2. **`claude -p` hardening (adopt in Phase 3 while touching scriptgen):**
   - `--bare` — skip skill/CLAUDE.md auto-discovery in cron (docs recommend for scripted use)
   - `--output-format json --json-schema '<schema>'` — replaces our find-the-braces
     parsing; pin Claude Code ≥ 2.1.205 (older versions silently degrade on bad schema)
   - `--max-turns 5` — budget circuit breaker; non-zero exit → state machine flags, no retry storm
   - **Operator task:** activate the headless automation credit. Since 2026-06-15,
     `claude -p` draws from a separate metered monthly credit (≈$100 value on Max 5x,
     no rollover), NOT the interactive session limits. Good isolation; hard ceiling —
     report.py should eventually track burn vs cadence.

3. **Upload flow pattern (validated by closest OSS twin):** upload with explicit
   `privacyStatus` and flip public only after human approval. Our order stays
   approve-first-then-upload (no junk private videos, quota irrelevant since the
   Dec-2025 quota cut made uploads ~100/day cheap). First real upload stays unlisted.
   Twin repo (Claude + edge-tts + ASS captions + official OAuth):
   github.com/rushindrasinha/youtube-shorts-pipeline.

4. **Compliance is now a measured line, not a vibe.** YouTube's inauthentic-content
   policy (renamed 2025-07-15): AI voiceover over an **original script = allowed**
   (doesn't even need the AI label); "generic/unoriginal templates giving the
   impression of mass production" = demonetization/termination (16 AI channels
   terminated Jan 2026). Our per-video real facts + rotating templates + varied hooks
   is the right side; template variety is a **compliance feature**. Cadence stays
   1/day, no burst-posting.

5. **TikTok:** Content Posting API is architecturally private-only until app audit —
   manual 2-tap posting isn't a compromise, it's the only path. Audit prep (privacy
   policy URL + demo video) can start whenever; no SLA published. TikTok Shop TH
   affiliate threshold ≈ 1,000 followers (community consensus, verify in-app).

6. **Shopee Affiliate has an official GraphQL Open API** (app_id/secret from the
   affiliate dashboard "Open API" tab; HMAC-SHA256) for programmatic link generation +
   product feeds → this is the real `discover.py` v2 + auto-affiliate-links.
   TH endpoint must be read from the dashboard after signup (regional URL pattern
   inferred, not verified). TH commission rate card is behind the dashboard — no
   public source. The "AI content → commissions off" policy applies to Shopee Video
   (in-app surface), not external link affiliates.

## Adopt (concrete, ranked)

| What | When | Source/note |
|---|---|---|
| `--bare` + `--json-schema` + `--max-turns` in scriptgen | Phase 3 | code.claude.com/docs headless |
| Approve→upload(public) YouTube flow, explicit privacyStatus | Phase 3 | twin repo pattern |
| OAuth verification submission + privacy-policy page | Phase 3 start | Google requirement |
| Word-level karaoke captions from **edge-tts WordBoundary events** (no Whisper — we know the script text) | Phase 3.5 | must first verify Thai boundary granularity vs pythainlp tokens |
| Shopee GraphQL feed → discover.py v2 + auto links | after affiliate signup | verify TH endpoint in dashboard |
| Thompson-sampling hook/template bandit (~30 lines + 2-col SQLite; no library) | Phase 4+ (needs clean per-video metrics rows first) | build-don't-borrow — no fitting OSS exists |
| BGM ducking (ffmpeg sidechaincompress) when music beds arrive | later | opensource-clipping technique |

## Local fallbacks (triggers, not migrations)

- **TTS:** edge-tts is an unofficial wrapper around Edge's internal endpoint — the risk
  is Microsoft closing it with zero notice. Fallback: **F5-TTS-THAI (VIZINTZOR)** —
  Thai-trained, CC-BY-4.0 (commercial-clean, attribute), ~3-5GB VRAM, RTF≈3 is fine
  for offline rendering. Switch trigger: edge-tts starts failing, or we want voice
  cloning. Avoid: MMS-TTS-tha + XTTS (non-commercial licenses), VAJA (dead, Windows).
- **LLM:** if headless Claude gets constrained → **Typhoon2-Qwen2.5-7B-Instruct**
  (SCB10X, Apache-2.0, creative-writing-tuned, fits any modern GPU). Precondition:
  Puen spot-checks its colloquial Thai copywriting against real scripts — all published
  Thai benchmarks are vendor-self-reported and measure exam Thai, not ad copy.
- **Generated b-roll (only when stock stops sufficing):** Flux.1-schnell stills
  (permissive tier — NOT flux-dev) + AnimateDiff loops; LTX-2 for real motion
  (weights license: free < $10M revenue). Honest read: local motion gen = ambient
  quality, not directed-shot quality.

## Skip (settled, with reasons)

- **Multi-agent frameworks** (CrewAI/LangGraph/AutoGen/smolagents): production reports
  show loop/token-burn failure modes and overhead scaling with complexity we don't
  have; the one thing LangGraph sells (state management) is what our SQLite state
  machine already is. The credible OSS "YouTube autopilot" case study is a linear
  pipeline with human gates — architecturally what we built.
- **Claude Agent SDK**: wraps the same CLI subprocess; zero marginal capability at
  2-3 calls/video. Revisit only for concurrent multi-video generation.
- **Remotion** (license cliff at 4-person team) / **revideo** (second runtime for a
  solved problem) — FFmpeg + libass stays.
- **Whisper anywhere in captions** — we author the script text; ASR is paying to
  rediscover what we already know.
- **AGPL code** (MoneyPrinterV2, podcli): read-only. **Cookie/browser-automation
  uploads** (MoneyPrinter V1/V2): the unofficial-API pattern we banned. **Paid posting
  SaaS** (Upload-Post): violates ฿0 rule.
- **Meta Reels API**: heaviest lift of all platforms (Business account + FB Page +
  Business verification + App Review). Revisit at day-90 gate if YT+TikTok show signal.

## Operator homework delta (all free)

1. Activate Claude headless automation credit (one-time, in account settings).
2. Create privacy-policy page (GitHub Pages) — feeds both Google OAuth verification
   and the eventual TikTok audit.
3. Shopee affiliate signup → note affiliate ID **and** check dashboard "Open API" tab
   for the TH GraphQL endpoint + app credentials.
4. (Unchanged) TikTok + YouTube channel creation, @BotFather bot token.
