"""Players for Mind Meld: humans (terminal input) and AI (Copilot SDK)."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod

from copilot.generated.session_events import AssistantMessageData
from copilot.session import PermissionHandler

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def clear_screen() -> None:
    """Clear the terminal, unless disabled (e.g. for testing/transcripts)."""
    if os.environ.get("MINDMELD_NOCLEAR"):
        print("\n" + "-" * 50)
    else:
        os.system("clear")


def normalize(word: str) -> str:
    """Canonical form used for comparing words (case/space/punct insensitive)."""
    return word.strip().lower().strip(".,!?;:\"'")


def extract_word(text: str) -> str:
    """Pull a single word out of a model response that may include extra text."""
    words = _WORD_RE.findall(text or "")
    if not words:
        return ""
    # Models usually answer with the bare word; if they ramble, the final token
    # is the most likely answer ("...so I'll say: river").
    return words[-1].lower()


SYSTEM_MESSAGE = (
    "You are playing 'Mind Meld', a word-convergence game. Two players each reveal "
    "one word per round at the same time, without communicating. The shared goal is "
    "to CONVERGE: across rounds both players try to end up saying the exact same "
    "word. Each round you look at the two words from the previous round and pick a "
    "single word that is a natural midpoint or strong bridge between them — the word "
    "you believe your partner is most likely to ALSO pick. Never reuse a word that "
    "either player has already said. Always respond with EXACTLY one single English "
    "word: lowercase, no punctuation, no quotes, no explanation."
)


class Player(ABC):
    def __init__(self, name: str):
        self.name = name

    @property
    def label(self) -> str:
        return self.name

    @abstractmethod
    async def get_word(self, round_no: int, you: list[str], partner: list[str],
                       used: set[str]) -> str:
        ...

    async def close(self) -> None:
        pass


class HumanPlayer(Player):
    @property
    def label(self) -> str:
        return f"{self.name} (human)"

    async def get_word(self, round_no, you, partner, used) -> str:
        # Clear the screen so the other human can't see this player's word.
        clear_screen()
        print(f"\n=== Round {round_no} — {self.name}'s turn (others look away!) ===")
        if round_no == 1:
            print("Think of any single word to open the game.")
        else:
            print(f"Last round  you said: '{you[-1]}'   partner said: '{partner[-1]}'")
            print("Pick a NEW word that bridges those two — aim to match your partner.")
        if used:
            print(f"(Already used, cannot repeat: {', '.join(sorted(used))})")
        while True:
            raw = input(f"{self.name}, enter your word: ").strip()
            word = extract_word(raw)
            if not word:
                print("  Please enter a single word.")
                continue
            if normalize(word) in used:
                print("  That word was already used — pick another.")
                continue
            clear_screen()
            return word


class AIPlayer(Player):
    """An AI player backed by one Copilot SDK session bound to a chosen model."""

    def __init__(self, name: str, client, model_id: str, model_name: str):
        super().__init__(name)
        self._client = client
        self.model_id = model_id
        self.model_name = model_name
        self._session = None

    @property
    def label(self) -> str:
        return f"{self.name} (AI: {self.model_name})"

    async def _ensure_session(self):
        if self._session is None:
            self._session = await self._client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=self.model_id,
                system_message={"mode": "replace", "content": SYSTEM_MESSAGE},
                available_tools=[],
            )
        return self._session

    def _build_prompt(self, round_no, you, partner, used) -> str:
        if round_no == 1:
            return ("Round 1. No words have been said yet. Open the game with one "
                    "common, fairly generic single word. Reply with only the word.")
        lines = [f"Round {round_no}.", "History (oldest first):"]
        for i, (y, p) in enumerate(zip(you, partner), start=1):
            lines.append(f"  Round {i}: you said '{y}', partner said '{p}'")
        used_list = ", ".join(sorted(used)) or "(none)"
        lines += [
            f"\nThe two words from the last round were: YOURS='{you[-1]}', "
            f"PARTNER'S='{partner[-1]}'.",
            "Pick ONE new word that bridges those two and that your partner is "
            "most likely to also pick this round.",
            f"You may NOT reuse any of these already-used words: {used_list}.",
            "Reply with only the single word.",
        ]
        return "\n".join(lines)

    async def get_word(self, round_no, you, partner, used) -> str:
        session = await self._ensure_session()
        prompt = self._build_prompt(round_no, you, partner, used)
        for attempt in range(3):
            resp = await session.send_and_wait(prompt, timeout=60)
            content = ""
            if resp and isinstance(resp.data, AssistantMessageData):
                content = resp.data.content or ""
            word = extract_word(content)
            if word and normalize(word) not in used:
                return word
            prompt = (
                f"That response ('{content.strip()[:40]}') was empty or already "
                "used. Reply with exactly ONE new, unused single English word."
            )
        # Fallback so the game never deadlocks on a stubborn model.
        return f"word{round_no}"

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.disconnect()
            except Exception:
                pass
