"""Web server for Mind Meld.

A dependency-free HTTP server (stdlib only) that lets you play Mind Meld in the
browser. AI players run on the Copilot SDK inside a single background asyncio
event loop; the HTTP handlers dispatch coroutines onto that loop.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from copilot import CopilotClient

from .models import list_models
from .players import AIPlayer, extract_word, normalize
from .web_page import INDEX_HTML

# ---------------------------------------------------------------------------
# Background asyncio loop hosting the shared Copilot client
# ---------------------------------------------------------------------------

_loop = asyncio.new_event_loop()
_client: CopilotClient | None = None
_models: list = []
_games: dict[str, "WebGame"] = {}


def _run_loop() -> None:
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


def _submit(coro):
    """Run a coroutine on the background loop from a handler thread."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()


async def _bootstrap() -> None:
    global _client, _models
    _client = CopilotClient()
    await _client.start()
    _models = await list_models(_client)


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------


class WebGame:
    def __init__(self, p1cfg: dict, p2cfg: dict, max_rounds: int):
        self.id = uuid.uuid4().hex[:8]
        self.max_rounds = max_rounds
        self.p1 = self._make_player(1, p1cfg)
        self.p2 = self._make_player(2, p2cfg)
        self.hist1: list[str] = []
        self.hist2: list[str] = []
        self.used: set[str] = set()
        self.round_no = 0
        self.finished = False
        self.converged = False
        self.final_word: str | None = None

    def _make_player(self, slot: int, cfg: dict):
        name = (cfg.get("name") or f"Player {slot}").strip()
        if cfg.get("type") == "ai":
            model_id = cfg.get("model") or "auto"
            model_name = next((m.name for m in _models if m.id == model_id), model_id)
            return AIPlayer(name, _client, model_id, model_name)
        return {"human": True, "name": name}

    @staticmethod
    def _is_ai(p) -> bool:
        return isinstance(p, AIPlayer)

    def _label(self, p) -> str:
        if self._is_ai(p):
            return f"{p.name} (AI: {p.model_name})"
        return f"{p['name']} (human)"

    def _name(self, p) -> str:
        return p.name if self._is_ai(p) else p["name"]

    def public_state(self) -> dict:
        rounds = [
            {"round": i + 1, "w1": a, "w2": b, "matched": normalize(a) == normalize(b)}
            for i, (a, b) in enumerate(zip(self.hist1, self.hist2))
        ]
        return {
            "game_id": self.id,
            "max_rounds": self.max_rounds,
            "round_no": self.round_no,
            "p1": {"label": self._label(self.p1), "name": self._name(self.p1),
                   "human": not self._is_ai(self.p1)},
            "p2": {"label": self._label(self.p2), "name": self._name(self.p2),
                   "human": not self._is_ai(self.p2)},
            "rounds": rounds,
            "used": sorted(self.used),
            "finished": self.finished,
            "converged": self.converged,
            "final_word": self.final_word,
            "last": {"w1": self.hist1[-1], "w2": self.hist2[-1]} if self.hist1 else None,
        }

    def _human_word(self, p, submitted: str) -> tuple[str | None, str | None]:
        word = extract_word(submitted or "")
        if not word:
            return None, f"{self._name(p)}: please enter a single word."
        if normalize(word) in self.used:
            return None, f"{self._name(p)}: '{word}' was already used — pick another."
        return word, None

    async def play_round(self, words: dict) -> dict | None:
        """Advance one round. `words` holds submitted words for human slots.

        Returns an error dict on invalid human input, else None.
        """
        if self.finished:
            return {"error": "Game already finished."}
        nxt = self.round_no + 1

        async def word_for(p, hist_self, hist_other, key):
            if self._is_ai(p):
                return await p.get_word(nxt, hist_self, hist_other, set(self.used))
            w, err = self._human_word(p, words.get(key, ""))
            if err:
                raise ValueError(err)
            return w

        try:
            w1, w2 = await asyncio.gather(
                word_for(self.p1, self.hist1, self.hist2, "p1"),
                word_for(self.p2, self.hist2, self.hist1, "p2"),
            )
        except ValueError as e:
            return {"error": str(e)}

        self.hist1.append(w1)
        self.hist2.append(w2)
        self.round_no = nxt
        if normalize(w1) == normalize(w2):
            self.finished = True
            self.converged = True
            self.final_word = normalize(w1)
        else:
            self.used.add(normalize(w1))
            self.used.add(normalize(w2))
            if self.round_no >= self.max_rounds:
                self.finished = True
        return None

    async def close(self) -> None:
        for p in (self.p1, self.p2):
            if self._is_ai(p):
                await p.close()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")
        elif self.path == "/api/models":
            self._json([{"id": m.id, "name": m.name} for m in _models])
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        try:
            data = self._read_json()
            if self.path == "/api/new":
                game = WebGame(data.get("p1", {}), data.get("p2", {}),
                               int(data.get("max_rounds", 12)))
                _games[game.id] = game
                self._json(game.public_state())
            elif self.path == "/api/round":
                game = _games.get(data.get("game_id"))
                if not game:
                    return self._json({"error": "unknown game"}, 404)
                err = _submit(game.play_round(data.get("words", {})))
                state = game.public_state()
                if err:
                    state["error"] = err["error"]
                self._json(state)
            elif self.path == "/api/quit":
                game = _games.pop(data.get("game_id"), None)
                if game:
                    _submit(game.close())
                self._json({"ok": True})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    threading.Thread(target=_run_loop, daemon=True).start()
    _submit(_bootstrap())
    print(f"Mind Meld web server: {len(_models)} models loaded.")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    serve()
