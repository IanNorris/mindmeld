"""Web server for Mind Meld.

A dependency-free HTTP server (stdlib only) that lets you play Mind Meld in the
browser. AI players run on the Copilot SDK inside a single background asyncio
event loop; the HTTP handlers dispatch coroutines onto that loop.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
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

# Matchmaking lobby: tickets for players waiting to be paired as they join.
_tickets: dict[str, dict] = {}
_waiting: list[str] = []          # ticket ids waiting for a human opponent
_lobby_lock = threading.Lock()


def _new_token() -> str:
    return uuid.uuid4().hex


def join_lobby(name: str, vs: str, model: str | None) -> dict:
    """Enqueue a player and pair them as opponents arrive.

    ``vs`` is "human" (wait for another human) or "ai" (start vs AI now).
    Returns the player's ticket (status "waiting" or "matched").
    """
    name = (name or "Player").strip()[:24] or "Player"
    tid = uuid.uuid4().hex[:10]
    ticket = {"id": tid, "name": name, "status": "waiting",
              "game_id": None, "slot": None, "token": None, "opponent": None}
    _tickets[tid] = ticket

    if vs == "ai":
        _start_match(ticket, ai_opponent=True, model=model)
        return ticket

    with _lobby_lock:
        # Try to pair with someone already waiting for a human.
        partner_id = None
        while _waiting:
            cand = _waiting.pop(0)
            ct = _tickets.get(cand)
            if ct and ct["status"] == "waiting":
                partner_id = cand
                break
        if partner_id is None:
            _waiting.append(tid)
            return ticket
        partner = _tickets[partner_id]
    _pair_humans(partner, ticket)
    return ticket


def _make_human_cfg(name: str) -> dict:
    return {"type": "human", "name": name}


def _pair_humans(t1: dict, t2: dict) -> None:
    """Create a human-vs-human game and bind both tickets to it."""
    game = WebGame(_make_human_cfg(t1["name"]), _make_human_cfg(t2["name"]),
                   max_rounds=DEFAULT_WEB_ROUNDS)
    tok1, tok2 = _new_token(), _new_token()
    game.tokens = {"p1": tok1, "p2": tok2}
    _games[game.id] = game
    t1.update(status="matched", game_id=game.id, slot="p1", token=tok1,
              opponent=t2["name"])
    t2.update(status="matched", game_id=game.id, slot="p2", token=tok2,
              opponent=t1["name"])


def _start_match(ticket: dict, ai_opponent: bool, model: str | None) -> None:
    """Create a human-vs-AI game for a single player who chose to play vs AI."""
    model_id = model or "auto"
    model_name = next((m.name for m in _models if m.id == model_id), model_id)
    game = WebGame(_make_human_cfg(ticket["name"]),
                   {"type": "ai", "model": model_id, "name": f"AI ({model_name})"},
                   max_rounds=DEFAULT_WEB_ROUNDS)
    tok = _new_token()
    game.tokens = {"p1": tok}
    _games[game.id] = game
    ticket.update(status="matched", game_id=game.id, slot="p1", token=tok,
                  opponent=f"AI ({model_name})")


def cancel_ticket(tid: str) -> None:
    with _lobby_lock:
        if tid in _waiting:
            _waiting.remove(tid)
    t = _tickets.get(tid)
    if t and t["status"] == "waiting":
        t["status"] = "cancelled"


def _ticket_view(t: dict) -> dict:
    """The owner-facing view of a ticket (includes their own auth token)."""
    return {
        "ticket": t["id"], "name": t["name"], "status": t["status"],
        "game_id": t["game_id"], "slot": t["slot"], "token": t["token"],
        "opponent": t["opponent"],
    }


DEFAULT_WEB_ROUNDS = 12



def _run_loop() -> None:
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


def _submit(coro, timeout: float | None = None):
    """Run a coroutine on the background loop from a handler thread."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout)


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
        # Per-round reasoning, aligned with hist1/hist2 ("" for human turns).
        self.reason1: list[str] = []
        self.reason2: list[str] = []
        self.finished = False
        self.converged = False
        self.final_word: str | None = None
        # Live-thinking fan-out: SSE subscribers each get their own queue.
        self._subscribers: set[queue.Queue] = set()
        self._sub_lock = threading.Lock()
        # Multiplayer: buffered per-slot human submissions for the current round,
        # auth tokens per human slot, and a lock serialising round resolution.
        self.pending: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self._round_lock = asyncio.Lock()

    # --- live streaming -----------------------------------------------------

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self._sub_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._sub_lock:
            self._subscribers.discard(q)

    def emit(self, event: dict) -> None:
        """Push an event to every SSE subscriber (drops if a queue is full)."""
        with self._sub_lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    def _delta_cb(self, slot: str):
        # Called from the asyncio loop thread as fragments stream in.
        def cb(fragment: str):
            self.emit({"kind": "delta", "slot": slot, "text": fragment})
        return cb


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

    def _player(self, slot: str):
        return self.p1 if slot == "p1" else self.p2

    def human_slots(self) -> list[str]:
        return [s for s in ("p1", "p2") if not self._is_ai(self._player(s))]

    def slot_for_token(self, token: str) -> str | None:
        for slot, tok in self.tokens.items():
            if tok == token:
                return slot
        return None

    def _label(self, p) -> str:
        if self._is_ai(p):
            return f"{p.name} (AI: {p.model_name})"
        return f"{p['name']} (human)"

    def _name(self, p) -> str:
        return p.name if self._is_ai(p) else p["name"]

    def public_state(self) -> dict:
        rounds = []
        for i, (a, b) in enumerate(zip(self.hist1, self.hist2)):
            rounds.append({
                "round": i + 1, "w1": a, "w2": b,
                "matched": normalize(a) == normalize(b),
                "r1": self.reason1[i] if i < len(self.reason1) else "",
                "r2": self.reason2[i] if i < len(self.reason2) else "",
            })
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
            "human_slots": self.human_slots(),
            "submitted": sorted(self.pending.keys()),
        }

    def _human_word(self, p, submitted: str) -> tuple[str | None, str | None]:
        word = extract_word(submitted or "")
        if not word:
            return None, f"{self._name(p)}: please enter a single word."
        if normalize(word) in self.used:
            return None, f"{self._name(p)}: '{word}' was already used — pick another."
        return word, None

    async def play_round(self, words: dict) -> dict | None:
        """Local mode: resolve a round given both human words at once."""
        async with self._round_lock:
            return await self._run_round(words)

    async def submit_word(self, slot: str, word: str) -> dict:
        """Multiplayer: a single human submits their word for the current round.

        Buffers the word; resolves the round once every human slot has submitted
        (AI slots are fetched during resolution). Returns a small status dict.
        """
        async with self._round_lock:
            if self.finished:
                return {"error": "Game already finished."}
            if slot not in self.human_slots():
                return {"error": "Not a human slot."}
            if slot in self.pending:
                return {"ok": True, "waiting": True}
            w, err = self._human_word(self._player(slot), word)
            if err:
                return {"error": err}
            self.pending[slot] = w
            self.emit({"kind": "submitted", "slot": slot,
                       "name": self._name(self._player(slot))})
            if all(s in self.pending for s in self.human_slots()):
                words = dict(self.pending)
                self.pending = {}
                err = await self._run_round(words)
                if err:
                    return {"error": err["error"]}
                return {"ok": True, "resolved": True}
            return {"ok": True, "waiting": True}

    async def _run_round(self, words: dict) -> dict | None:
        """Advance one round. `words` holds submitted words for human slots.

        Returns an error dict on invalid human input, else None.
        Caller must hold ``self._round_lock``.
        """
        if self.finished:
            return {"error": "Game already finished."}
        nxt = self.round_no + 1

        # Announce the new round and reset live-thinking panes; wire each AI's
        # streaming callback so fragments fan out to SSE subscribers.
        self.emit({"kind": "round_start", "round": nxt})
        for slot, p in (("p1", self.p1), ("p2", self.p2)):
            if self._is_ai(p):
                p.on_delta = self._delta_cb(slot)

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
            self._clear_delta_cbs()
            return {"error": str(e)}
        except Exception as e:  # noqa: BLE001 — never corrupt game state on a round
            self._clear_delta_cbs()
            return {"error": f"Round failed ({type(e).__name__}: {e}). Try again."}
        finally:
            self._clear_delta_cbs()

        self.hist1.append(w1)
        self.hist2.append(w2)
        self.reason1.append(self.p1.last_reasoning if self._is_ai(self.p1) else "")
        self.reason2.append(self.p2.last_reasoning if self._is_ai(self.p2) else "")
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
        self.emit({"kind": "round_done", "round": self.round_no,
                   "w1": w1, "w2": w2, "matched": normalize(w1) == normalize(w2)})
        return None

    def _clear_delta_cbs(self) -> None:
        for p in (self.p1, self.p2):
            if self._is_ai(p):
                p.on_delta = None


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
        elif self.path.startswith("/api/stream"):
            self._sse()
        else:
            self._json({"error": "not found"}, 404)

    def _sse(self):
        from urllib.parse import parse_qs, urlparse
        gid = (parse_qs(urlparse(self.path).query).get("game_id") or [""])[0]
        game = _games.get(gid)
        if not game:
            return self._json({"error": "unknown game"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = game.subscribe()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")  # keep-alive
                    self.wfile.flush()
                    continue
                self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            game.unsubscribe(q)

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
                try:
                    err = _submit(game.play_round(data.get("words", {})), timeout=180)
                except Exception as e:  # noqa: BLE001
                    err = {"error": f"Round error ({type(e).__name__}: {e}). Try again."}
                state = game.public_state()
                if err:
                    state["error"] = err["error"]
                self._json(state)
            elif self.path == "/api/quit":
                game = _games.pop(data.get("game_id"), None)
                if game:
                    _submit(game.close())
                self._json({"ok": True})
            elif self.path == "/api/join":
                ticket = join_lobby(data.get("name", ""), data.get("vs", "human"),
                                    data.get("model"))
                self._json(_ticket_view(ticket))
            elif self.path == "/api/poll":
                t = _tickets.get(data.get("ticket"))
                if not t:
                    return self._json({"error": "unknown ticket"}, 404)
                self._json(_ticket_view(t))
            elif self.path == "/api/cancel":
                cancel_ticket(data.get("ticket", ""))
                self._json({"ok": True})
            elif self.path == "/api/state":
                game = _games.get(data.get("game_id"))
                if not game:
                    return self._json({"error": "unknown game"}, 404)
                self._json(game.public_state())
            elif self.path == "/api/move":
                game = _games.get(data.get("game_id"))
                if not game:
                    return self._json({"error": "unknown game"}, 404)
                slot = game.slot_for_token(data.get("token", ""))
                if not slot:
                    return self._json({"error": "invalid token"}, 403)
                try:
                    res = _submit(game.submit_word(slot, data.get("word", "")),
                                  timeout=200)
                except Exception as e:  # noqa: BLE001
                    res = {"error": f"Move error ({type(e).__name__}: {e})."}
                state = game.public_state()
                state.update({k: v for k, v in res.items() if k != "ok"})
                self._json(state)
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
