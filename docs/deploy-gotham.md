# Deploying on gotham (Fedora)

All free. One-time setup:

```bash
# 1. Clone
git clone https://github.com/Puen2001/AF.git shorts-factory && cd shorts-factory

# 2. Python env (system python is fine, 3.12+)
python3 -m venv .venv && .venv/bin/pip install pyyaml requests edge-tts

# 3. FFmpeg — Fedora's ffmpeg-free has NO x264 encoder; use the RPM Fusion build:
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf swap ffmpeg-free ffmpeg --allowerasing

# 4. Claude CLI (scriptgen engine) + login with the existing subscription account
curl -fsSL https://claude.ai/install.sh | bash
claude   # complete the login once, then exit

# 5. Secrets
cp config/secrets.env.example config/secrets.env   # fill in

# 6. Thai font for captions (phase 2 render)
sudo dnf install google-noto-sans-thai-fonts
```

## Scheduler (phase 3 — systemd user timer)

Runs daily without anyone logged in:

```bash
loginctl enable-linger $USER   # once, lets user timers run at boot
```

Unit files land in `deploy/` when phase 3 is built:
`shorts-factory.service` (oneshot: `.venv/bin/python run.py daily`) +
`shorts-factory.timer` (`OnCalendar=daily`, `Persistent=true`), installed to
`~/.config/systemd/user/` with `systemctl --user enable --now shorts-factory.timer`.

Failure alerts go to Telegram via the approve-stage bot token (same `secrets.env`).

## Sanity check

```bash
.venv/bin/python run.py dry-run   # should end with scripts.checked >= 1
```
