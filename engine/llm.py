"""Optional Claude integration for the Executive briefing.

The engine works without it. Set ANTHROPIC_API_KEY to have Claude write the
leadership briefing from the prioritised decisions; otherwise a template is used.
Only aggregated decision text is sent, never raw emails or call transcripts.
"""
import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("SETU_MODEL", "claude-opus-5-5")


def complete(system, prompt, max_tokens=700):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        return "".join(b.get("text", "") for b in data.get("content", [])).strip() or None
    except Exception as exc:  # the template briefing is the fallback
        print(f"[setu] Claude briefing unavailable: {exc}")
        return None
