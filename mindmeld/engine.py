"""The Mind Meld game engine: run rounds until the two players converge."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .players import Player, normalize

DEFAULT_MAX_ROUNDS = 12


@dataclass
class RoundResult:
    round_no: int
    words: tuple[str, str]
    matched: bool


@dataclass
class GameResult:
    converged: bool
    rounds: list[RoundResult] = field(default_factory=list)
    final_word: str | None = None


class Game:
    def __init__(self, p1: Player, p2: Player, max_rounds: int = DEFAULT_MAX_ROUNDS):
        self.p1 = p1
        self.p2 = p2
        self.max_rounds = max_rounds
        self.history1: list[str] = []
        self.history2: list[str] = []
        self.used: set[str] = set()

    async def play(self, on_round=None) -> GameResult:
        result = GameResult(converged=False)
        for rnd in range(1, self.max_rounds + 1):
            # Both players choose "simultaneously": gather without revealing.
            w1, w2 = await asyncio.gather(
                self.p1.get_word(rnd, self.history1, self.history2, set(self.used)),
                self.p2.get_word(rnd, self.history2, self.history1, set(self.used)),
            )
            self.history1.append(w1)
            self.history2.append(w2)
            matched = normalize(w1) == normalize(w2)
            rr = RoundResult(rnd, (w1, w2), matched)
            result.rounds.append(rr)
            if on_round:
                on_round(rr, self.p1, self.p2)
            if matched:
                result.converged = True
                result.final_word = normalize(w1)
                break
            self.used.add(normalize(w1))
            self.used.add(normalize(w2))
        return result
