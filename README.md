# Mind Meld 🧠✨

A word-convergence game. Two players each reveal one word per round **at the
same time**, without communicating. Each round you look at the two words from
the previous round and try to pick the word you think your partner will *also*
say — a conceptual midpoint between the two. The goal is to **converge**: keep
going until you both say the exact same word.

Example:
```
Round 1:  moon   /  water
Round 2:  wave   /  wave    <- Mind meld!
```

Either player can be a **human** (typing in the terminal) or an **AI** powered
by the GitHub Copilot SDK — and you choose the setup, including which AI model
each AI player uses, **at the start of every game**.

## Running

From the project root:

```bash
python -m mindmeld
```

You'll be asked, for each of the two players:

1. **Human or AI?**
2. If AI: **which model** (Claude, GPT, Gemini, …, discovered live from the SDK)
3. A display name
4. Finally, the maximum number of rounds.

Any combination works: Human vs Human, Human vs AI, or AI vs AI (great for
watching two different models try to read each other's mind).

### Environment

- Requires the `copilot` Python SDK (bundled in this sandbox) and a valid
  Copilot auth token in the environment (`COPILOT_SDK_AUTH_TOKEN` /
  `GITHUB_TOKEN`).
- `MINDMELD_NOCLEAR=1` disables the between-turn screen clears (useful for
  transcripts, logging, or piping output).

## How the AI plays

Each AI player owns its own Copilot SDK **session** bound to the chosen model,
with a system prompt explaining the convergence game. Each round it receives the
full shared word history and the previous round's two words, and is asked for a
single new (never-reused) word. Separate sessions keep the two AIs from "seeing"
each other's reasoning — they only know the words that were revealed, exactly
like human players.

## Project layout

| File | Purpose |
|------|---------|
| `mindmeld/models.py`  | Lists available models via the SDK (raw RPC). |
| `mindmeld/players.py` | `HumanPlayer` and `AIPlayer` (Copilot SDK). |
| `mindmeld/engine.py`  | Round loop and convergence detection. |
| `mindmeld/cli.py`     | Setup menu + game presentation. |
| `tests/`              | Pure-logic tests (no network). |
