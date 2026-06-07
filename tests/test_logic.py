"""Pure-logic tests for Mind Meld — no Copilot / network required.

Run: python -m pytest tests/  (or)  python tests/test_logic.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mindmeld.engine import Game
from mindmeld.players import Player, extract_word, normalize


class ScriptedPlayer(Player):
    """A non-AI player that plays a fixed list of words, for testing."""

    def __init__(self, name, words):
        super().__init__(name)
        self._words = list(words)
        self._i = 0

    async def get_word(self, round_no, you, partner, used):
        w = self._words[self._i]
        self._i += 1
        return w


def test_normalize():
    assert normalize("  Hello! ") == "hello"
    assert normalize("WAVE") == normalize("wave")


def test_extract_word():
    assert extract_word("river") == "river"
    assert extract_word("I'll say: river.") == "river"
    assert extract_word("The word is OCEAN") == "ocean"
    assert extract_word("") == ""


def test_converges():
    p1 = ScriptedPlayer("A", ["light", "wave"])
    p2 = ScriptedPlayer("B", ["water", "wave"])
    res = asyncio.run(Game(p1, p2, max_rounds=8).play())
    assert res.converged is True
    assert res.final_word == "wave"
    assert len(res.rounds) == 2


def test_no_convergence_stops_at_max():
    p1 = ScriptedPlayer("A", ["a", "b", "c"])
    p2 = ScriptedPlayer("B", ["x", "y", "z"])
    res = asyncio.run(Game(p1, p2, max_rounds=3).play())
    assert res.converged is False
    assert len(res.rounds) == 3


def test_case_insensitive_match():
    p1 = ScriptedPlayer("A", ["Wave"])
    p2 = ScriptedPlayer("B", ["wave"])
    res = asyncio.run(Game(p1, p2, max_rounds=2).play())
    assert res.converged is True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} tests passed.")
