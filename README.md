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

### Terminal

```bash
python -m mindmeld
```

You'll be asked, for each of the two players: **Human or AI?**, **which model**
(if AI), a display name, and the maximum number of rounds. Any combination
works: Human vs Human, Human vs AI, or AI vs AI.

### Web / dev server

```bash
python -m mindmeld.web         # or ./run_server.sh
```

Then open `http://localhost:8000`. The web UI offers two modes:

- **Local game** — both players on one screen (pick Human/AI + model each),
  just like the terminal version.
- **Play online** — *matchmaking*: enter a name and you're paired with the
  **next player who joins**. Each player plays from their own browser and
  submits only their own word; you can also choose "play vs an AI now" if you
  don't want to wait. Open the page in two browser tabs/devices to play a
  human-vs-human match.

The web UI also shows each **AI's reasoning streaming live** ("thinking" panes)
as it decides its word, via a server-sent-events (SSE) stream.

### Environment

- Requires the `copilot` Python SDK (bundled in this sandbox) and a valid
  Copilot auth token in the environment (`COPILOT_SDK_AUTH_TOKEN` /
  `GITHUB_TOKEN`).
- `MINDMELD_NOCLEAR=1` disables the terminal's between-turn screen clears
  (useful for transcripts, logging, or piping output).

## How the AI plays

Each AI player owns its own Copilot SDK **session** bound to the chosen model,
with a system prompt explaining the convergence game. To avoid repetitive
openings, an AI's **first** word is drawn at random from a curated dictionary
(`mindmeld/dictionary.py`); from round two the model iterates, receiving the
full shared word history and the previous round's two words and replying in a
`THINKING:` / `WORD:` format so its reasoning can be shown. Separate sessions
keep two AIs from "seeing" each other's reasoning — they only know the revealed
words, exactly like human players.

## Project layout

| File | Purpose |
|------|---------|
| `mindmeld/models.py`     | Lists available models via the SDK (raw RPC). |
| `mindmeld/dictionary.py` | Curated common-word list for AI openers. |
| `mindmeld/players.py`    | `HumanPlayer` and `AIPlayer` (Copilot SDK, streaming). |
| `mindmeld/engine.py`     | Round loop and convergence detection. |
| `mindmeld/cli.py`        | Terminal setup menu + game presentation. |
| `mindmeld/web.py`        | Web server: matchmaking lobby, games, SSE stream. |
| `mindmeld/web_page.py`   | Single-page web UI (local + online modes). |
| `tests/`                 | Pure-logic tests (no network). |

