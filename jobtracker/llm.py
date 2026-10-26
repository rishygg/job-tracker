"""Minimal Ollama client (local models). Uses only the standard library.

Answers are streamed so the interface can show progress (and so a cancelled task really stops Ollama). Speed is
measured on every call, which lets the app estimate how long the next review will take on this computer.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

DEFAULT_URL = "http://localhost:11434"
NUM_CTX = 8192  # the same for every call: changing it makes Ollama reload the model

_local = threading.local()


class LLMError(RuntimeError):
    pass


@contextmanager
def use_progress(progress):
    """Report streaming progress of every chat_json call in this thread to `progress` (an aijobs.Progress)."""
    prev = getattr(_local, "progress", None)
    _local.progress = progress
    try:
        yield
    finally:
        _local.progress = prev


def _progress():
    return getattr(_local, "progress", None)


def parse_loose(text: str):
    """json.loads, or the longest prefix that parses once open strings/brackets are closed (truncated answers)."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Prefer cutting after a complete object/array, so a half-written item is dropped rather than kept.
    closes = [i for i, ch in enumerate(text) if ch in "}]"][-300:]
    commas = [i for i, ch in enumerate(text) if ch == ","][-100:]
    for i in list(reversed(closes)) + list(reversed(commas)):
        cand = text[:i] if text[i] == "," else text[:i + 1]
        stack, in_str, esc = [], False, False
        for ch in cand:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack:
                stack.pop()
        if in_str:
            continue
        try:
            return json.loads(cand + "".join(reversed(stack)))
        except json.JSONDecodeError:
            continue
    raise LLMError("The model didn't return valid JSON. Try again or pick a larger model.")


class Ollama:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 600):
        self.base_url = (base_url or DEFAULT_URL).rstrip("/")
        self.model = model or ""
        self.timeout = timeout
        self.last_stats: dict | None = None

    def _open(self, path: str, payload: dict | None = None, timeout: float | None = None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data,
                                     headers={"Content-Type": "application/json"} if data else {},
                                     method="POST" if data else "GET")
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            raise LLMError(f"Ollama returned {e.code}: {body}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise LLMError(f"Can't reach Ollama at {self.base_url}. Is it running?") from e

    def _req(self, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        with self._open(path, payload, timeout) as r:
            return json.loads(r.read().decode())

    def models(self) -> list[str]:
        return [m["name"] for m in self._req("/api/tags", timeout=4).get("models", [])]

    def loaded(self) -> bool | None:
        """Is the model already in memory? None if this Ollama version can't say."""
        try:
            names = [m.get("name") or m.get("model") for m in self._req("/api/ps", timeout=3).get("models", [])]
        except Exception:  # noqa: BLE001
            return None
        want = self.model if ":" in self.model else f"{self.model}:latest"
        return any((n if ":" in (n or "") else f"{n}:latest") == want for n in names)

    def status(self) -> dict:
        try:
            models = self.models()
        except LLMError as e:
            return {"available": False, "models": [], "model": self.model, "error": str(e)}
        model = self.model if self.model in models else (models[0] if models else "")
        return {"available": bool(models), "models": models, "model": model,
                "error": None if models else "Ollama is running but has no models. Run: ollama pull qwen2.5:7b"}

    def chat_json(self, system: str, user: str, schema: dict, temperature: float = 0.2, num_ctx: int = NUM_CTX,
                  num_predict: int = 700, max_seconds: float = 420) -> dict:
        """Ask for JSON that follows `schema`. Streams; stops after `max_seconds` and keeps what parsed."""
        if not self.model:
            raise LLMError("No Ollama model selected. Pick one in Settings.")
        prog = _progress()
        if prog:
            prog.phase("loading model" if self.loaded() is False else "reading")
        payload = {
            "model": self.model, "stream": True, "format": schema,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            # Keep the model in memory between calls so it isn't reloaded each time (the slowest part).
            "keep_alive": "30m",
            "options": {"temperature": temperature, "num_ctx": NUM_CTX, "num_predict": num_predict},
        }
        start = time.time()
        first = None
        parts: list[str] = []
        stats: dict = {}
        stopped = None
        with self._open("/api/chat", payload) as r:
            for raw in r:
                line = raw.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise LLMError(f"Ollama: {chunk['error']}")
                piece = (chunk.get("message") or {}).get("content", "")
                if piece:
                    if first is None:
                        first = time.time()
                    parts.append(piece)
                    if prog:
                        prog.token()  # raises Cancelled; leaving the with-block closes the stream
                if chunk.get("done"):
                    stats = chunk
                    break
                if time.time() - start > max_seconds:
                    stopped = "time"
                    break
                # JSON mode sometimes degenerates into endless whitespace: stop and keep what we have.
                if len(parts) > 60 and not "".join(parts[-60:]).strip():
                    stopped = "whitespace"
                    break
        text = "".join(parts)
        self._record(stats, start, first, len(parts))
        try:
            return parse_loose(text)
        except LLMError:
            if stopped == "time":
                raise LLMError(f"The model took longer than {int(max_seconds // 60)} minutes and its answer was "
                               "incomplete. Try a smaller model or close other programs.")
            raise

    def _record(self, stats: dict, start: float, first: float | None, n: int) -> None:
        end = time.time()
        if stats.get("eval_count") and stats.get("eval_duration"):
            gen = stats["eval_count"] / (stats["eval_duration"] / 1e9)
        else:
            gen = n / max(0.1, end - (first or end)) if n and first else None
        prompt = None
        if stats.get("prompt_eval_count") and stats.get("prompt_eval_duration"):
            prompt = stats["prompt_eval_count"] / (stats["prompt_eval_duration"] / 1e9)
        self.last_stats = {"gen_tps": round(gen, 2) if gen else None, "prompt_tps": round(prompt, 1) if prompt else None,
                           "prompt_tokens": stats.get("prompt_eval_count"), "tokens": stats.get("eval_count") or n,
                           "load_s": round(stats.get("load_duration", 0) / 1e9, 1), "seconds": round(end - start, 1),
                           "model": self.model, "at": time.strftime("%Y-%m-%d %H:%M")}
