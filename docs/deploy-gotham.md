# Deploying on gotham (Fedora)

All free. One-time setup:

```bash
# 1. Clone
git clone https://github.com/Puen2001/AF.git shorts-factory && cd shorts-factory

# 2. Python env (system python is fine, 3.12+)
python3 -m venv .venv && .venv/bin/pip install pyyaml requests edge-tts \
    google-api-python-client google-auth-oauthlib

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

```bash
mkdir -p ~/.config/systemd/user
cp deploy/*.service deploy/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now shorts-factory.timer shorts-poll.timer
```

Two timers: `shorts-factory` (daily 09:00 — full production run) and
`shorts-poll` (every 15 min — processes ✅/❌ approval taps and publishes).

## YouTube auth (once, on any machine with a browser)

Set `YOUTUBE_CLIENT_SECRET_JSON` in `config/secrets.env` (OAuth client secret
file from Google Cloud Console), then `python run.py yt-auth` — the saved token
(`config/yt_token.json`) refreshes headlessly afterwards. Note: while the Google
OAuth app is in Testing mode the token dies every 7 days — submit the app for
verification (needs a public privacy-policy URL) to make it permanent.

## Sanity check

```bash
.venv/bin/python run.py dry-run   # should end with scripts.checked >= 1
```
