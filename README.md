# Shorts Factory

Automated Thai gadget-shorts pipeline: discover products → generate curiosity-driven
scripts → TTS voice → render vertical video → Telegram approval → publish → learn.
Design spec: `docs/2026-07-23-shorts-factory-design.md`.

## Run

```bash
conda activate shorts
python run.py dry-run    # one product end-to-end (built stages only)
python run.py daily      # normal daily batch
python run.py status     # pipeline counts
```

## Setup

1. `cp config/secrets.env.example config/secrets.env` and fill in (all free tiers).
2. Add real Shopee affiliate links to `config/seed_products.yaml` after affiliate signup.

Production runs on gotham (Fedora) — see `docs/deploy-gotham.md`.

## Status

Phase 1 (discover + scriptgen) built. Voice/render = phase 2; approval/publish = phase 3.
