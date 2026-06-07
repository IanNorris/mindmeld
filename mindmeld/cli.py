"""Interactive setup menu and entry point for Mind Meld."""

from __future__ import annotations

import asyncio
import os

from copilot import CopilotClient

from .engine import DEFAULT_MAX_ROUNDS, Game, GameResult
from .models import Model, list_models
from .players import AIPlayer, HumanPlayer, Player, clear_screen

BANNER = r"""
  __  __ _           _   __  __      _     _
 |  \/  (_)_ __   __| | |  \/  | ___| | __| |
 | |\/| | | '_ \ / _` | | |\/| |/ _ \ |/ _` |
 | |  | | | | | | (_| | | |  | |  __/ | (_| |
 |_|  |_|_|_| |_|\__,_| |_|  |_|\___|_|\__,_|

  Think of a word. Say it together. Converge.
"""


def _choose(prompt: str, options: list[str], default: int | None = None) -> int:
    """Render a numbered menu and return the chosen 0-based index."""
    for i, opt in enumerate(options, start=1):
        marker = " (default)" if default is not None and i - 1 == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        raw = input(f"{prompt} ").strip()
        if not raw and default is not None:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("  Please enter a valid number.")


def _pick_model(models: list[Model], who: str) -> Model:
    print(f"\nChoose a model for {who}:")
    idx = _choose("Model #:", [f"{m.name}  [{m.id}]" for m in models], default=0)
    return models[idx]


async def _build_player(slot: int, client, models: list[Model]) -> Player:
    print(f"\n--- Player {slot} ---")
    kind = _choose("Is Player {} a human or an AI?".format(slot),
                   ["Human", "AI"], default=0)
    if kind == 0:
        default_name = f"Player {slot}"
        name = input(f"Name for Player {slot} [{default_name}]: ").strip() or default_name
        return HumanPlayer(name)
    model = _pick_model(models, f"Player {slot}")
    default_name = f"AI-{slot}"
    name = input(f"Name for this AI [{default_name}]: ").strip() or default_name
    return AIPlayer(name, client, model.id, model.name)


def _print_round(rr, p1: Player, p2: Player) -> None:
    print(f"\n  Round {rr.round_no}:")
    print(f"    {p1.label:<28} -> {rr.words[0]}")
    print(f"    {p2.label:<28} -> {rr.words[1]}")
    if rr.matched:
        print("    *** MIND MELD! Both said the same word. ***")
    else:
        print("    (no match — keep converging)")


def _print_result(result: GameResult, p1: Player, p2: Player) -> None:
    print("\n" + "=" * 50)
    if result.converged:
        print(f"  CONVERGED on '{result.final_word}' in "
              f"{len(result.rounds)} round(s)! ")
    else:
        print(f"  No convergence after {len(result.rounds)} rounds.")
        print(f"  Last words: {p1.name}='{result.rounds[-1].words[0]}', "
              f"{p2.name}='{result.rounds[-1].words[1]}'")
    print("=" * 50)


async def run_once(client, models: list[Model]) -> None:
    clear_screen()
    print(BANNER)
    print("Set up a new game.\n")

    p1 = await _build_player(1, client, models)
    p2 = await _build_player(2, client, models)

    raw = input(f"\nMax rounds [{DEFAULT_MAX_ROUNDS}]: ").strip()
    max_rounds = int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_MAX_ROUNDS

    print(f"\nStarting: {p1.label}  vs  {p2.label}  (up to {max_rounds} rounds)")
    input("Press Enter to begin...")

    game = Game(p1, p2, max_rounds=max_rounds)
    try:
        result = await game.play(on_round=_print_round)
    finally:
        await asyncio.gather(p1.close(), p2.close(), return_exceptions=True)
    _print_result(result, p1, p2)


async def main() -> None:
    print(BANNER)
    print("Connecting to Copilot...")
    async with CopilotClient() as client:
        models = await list_models(client)
        if not models:
            print("No models available. Are you authenticated?")
            return
        while True:
            await run_once(client, models)
            again = input("\nPlay again? [y/N]: ").strip().lower()
            if again not in ("y", "yes"):
                print("Thanks for playing Mind Meld!")
                break


def cli() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")


if __name__ == "__main__":
    cli()
