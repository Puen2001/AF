"""Shared `claude -p` headless helper. Bills the metered automation credit."""
import json
import os
import signal
import subprocess


def claude_p(prompt: str, model: str, tools: str | None = None,
             timeout: int = 300) -> dict:
    cmd = ["claude", "-p", prompt, "--model", model]
    if tools:
        cmd += ["--allowedTools", tools]
    # start_new_session=True puts claude in its own process group. WebSearch spawns MCP
    # server grandchildren that inherit the stdout pipe; a plain subprocess.run(timeout)
    # kills `claude` but then deadlocks in communicate() waiting on the grandchild's pipe
    # (that hung the pipeline for 70 min). Killing the whole GROUP on timeout avoids that.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        raise RuntimeError(f"claude -p timed out after {timeout}s")
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {(stderr or '')[:500]}")
    start, end = stdout.find("{"), stdout.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in claude output: {stdout[:200]}")
    return json.loads(stdout[start:end + 1])
