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

## Demo

![Mind Meld demo — a human opening with "sausage" vs Gemini 3.5 Flash](media/mindmeld-demo.webp)

*A human (left) opening with "sausage" vs an AI on Gemini 3.5 Flash — it takes
five rounds (sausage → link → leash → dachshund → **park**) to converge, with
the AI tracking the sausage → dog → wiener theme. Recorded from the web UI with
Playwright; see [Recording a demo](#recording-a-demo).*
[Full-quality MP4.](https://github.com/IanNorris/mindmeld/releases/download/demo-v1/mindmeld-demo.mp4)






## Requirements

- **Python ≥ 3.11**
- The **GitHub Copilot CLI Python SDK** (`github-copilot-sdk`, imported as
  `copilot`) — installed automatically by the steps below.
- A working **GitHub Copilot** authentication. The SDK talks to the Copilot CLI
  backend, so you need either:
  - the [GitHub Copilot CLI](https://github.com/github/copilot-cli) installed
    and signed in (`copilot` on your `PATH`), or
  - a `GITHUB_TOKEN` (or `COPILOT_SDK_AUTH_TOKEN`) in your environment with
    Copilot access.

## Install

```bash
git clone https://github.com/IanNorris/mindmeld.git
cd mindmeld

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e .                   # installs the package + Copilot SDK
```

Prefer not to install the package? `pip install -r requirements.txt` pulls just
the runtime dependency, and you can then run the modules directly (see below).

## Running

### Terminal

```bash
mindmeld            # console entry point (installed by `pip install -e .`)
# or, without installing the package:
python -m mindmeld
```

You'll be asked, for each of the two players: **Human or AI?**, **which model**
(if AI), a display name, and the maximum number of rounds. Any combination
works: Human vs Human, Human vs AI, or AI vs AI.

### Web / dev server

```bash
mindmeld-web        # console entry point
# or:
python -m mindmeld.web        # or ./run_server.sh
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

### Configuration

- **Authentication** — the SDK uses your Copilot CLI session or a
  `GITHUB_TOKEN` / `COPILOT_SDK_AUTH_TOKEN` in the environment (see
  [Requirements](#requirements)).
- **`MINDMELD_NOCLEAR=1`** disables the terminal's between-turn screen clears
  (useful for transcripts, logging, or piping output).
- The web server binds to `0.0.0.0:8000` by default; edit the `serve()` call in
  `mindmeld/web.py` (or import and call `serve(host, port)`) to change it.

## How the AI plays

Each AI player owns its own Copilot SDK **session** bound to the chosen model,
with a system prompt explaining the convergence game. To avoid repetitive
openings, an AI's **first** word is drawn at random from a curated dictionary
(`mindmeld/dictionary.py`); from round two the model iterates, receiving the
full shared word history and the previous round's two words and replying in a
`THINKING:` / `WORD:` format so its reasoning can be shown. Separate sessions
keep two AIs from "seeing" each other's reasoning — they only know the revealed
words, exactly like human players.

## Tests

Pure-logic tests (no network/SDK calls) cover word parsing and the round/
convergence engine via a scripted player:

```bash
python tests/test_logic.py      # or: pytest
```

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
| `tools/record_demo.py`   | Playwright script that records a playthrough. |
| `tests/`                 | Pure-logic tests (no network). |
| `pyproject.toml`         | Packaging, dependencies, `mindmeld` / `mindmeld-web` entry points. |

## Recording a demo

`tools/record_demo.py` drives the web UI with [Playwright](https://playwright.dev/python/)
to record a human-vs-AI game as a video. The "human" side is auto-played by a
fast helper model so the recording converges quickly; the AI opponent uses a
fast flash/mini model too (configurable via `DEMO_AI_MODEL` / `DEMO_HUMAN_MODEL`).
Set `DEMO_OPENER` to force the human's first word (e.g. `DEMO_OPENER=sausage`
for a game that takes a few rounds), and `DEMO_ROUNDS` to cap the length.

```bash
pip install playwright imageio-ffmpeg
playwright install chromium          # plus system deps; see Playwright docs

mindmeld-web &                       # start the server on :8000
python tools/record_demo.py          # writes media/*.webm
```

Convert the recording to an MP4/GIF with ffmpeg (the committed
`media/mindmeld-demo.webp` (animated, shown above) and the release-hosted MP4 were
produced this way). On NixOS, run the script inside `tools/demo-shell.nix` so
headless Chromium has fontconfig and fonts.

## License

[MIT](LICENSE).


