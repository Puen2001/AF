"""Shared `claude -p` headless helper. Bills the metered automation credit."""
import json
import subprocess


def claude_p(prompt: str, model: str, tools: str | None = None,
             timeout: int = 300) -> dict:
    cmd = ["claude", "-p", prompt, "--model", model]
    if tools:
        cmd += ["--allowedTools", tools]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed: {out.stderr[:500]}")
    text = out.stdout
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in claude output: {text[:200]}")
    return json.loads(text[start:end + 1])
