"""Record a Mind Meld playthrough (human vs AI) with Playwright -> webm -> gif.

The "human" side is auto-played for the recording: each human word is chosen by
a fast helper model so the game converges quickly and looks natural on camera.
The AI opponent in the game also uses a fast flash/mini model to keep waits low.

Run from the repo root with the web server already listening on :8000:

    PYTHONPATH=/tmp/pw python tools/record_demo.py
"""

from __future__ import annotations

import asyncio
import os
import re

from playwright.async_api import async_playwright

from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.generated.session_events import AssistantMessageData

CHROME = os.environ.get("CHROME_BIN",
    "/nix/store/n8vvjnxkp72149l2f9nwp6hm9cqxlfx1-chromium-149.0.7827.53/bin/chromium")
URL = os.environ.get("DEMO_URL", "http://localhost:8000")
AI_MODEL = os.environ.get("DEMO_AI_MODEL", "gemini-3.5-flash")   # fast opponent
HUMAN_MODEL = os.environ.get("DEMO_HUMAN_MODEL", "gpt-5-mini")    # fast helper
OUT_DIR = os.environ.get("DEMO_OUT", "/workspace/mindmeld/media")
DEMO_ROUNDS = int(os.environ.get("DEMO_ROUNDS", "6"))
# Force the human's opening word (e.g. a deliberately off-beat one so the game
# takes a few rounds to converge). Empty -> let the helper choose.
DEMO_OPENER = os.environ.get("DEMO_OPENER", "").strip()

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def extract_word(text: str) -> str:
    ws = _WORD_RE.findall(text or "")
    return ws[-1].lower() if ws else ""


class HumanBrain:
    """A fast helper that picks the human's word each round (for the recording)."""

    SYS = (
        "You are playing Mind Meld with a partner. Each round you each say one word "
        "simultaneously, trying to CONVERGE on the same word over time by naming the "
        "conceptual midpoint of the previous two words. Never reuse a used word. "
        "Reply with EXACTLY one lowercase English word, nothing else."
    )

    def __init__(self, client):
        self._client = client
        self._session = None

    async def _ensure(self):
        if self._session is None:
            self._session = await self._client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=HUMAN_MODEL,
                system_message={"mode": "replace", "content": self.SYS},
                available_tools=[],
            )
        return self._session

    async def pick(self, state) -> str:
        used = set(state.get("used", []))
        last = state.get("last")
        if not last:
            prompt = "Round 1. Open with one common single word. Reply with only the word."
        else:
            prompt = (
                f"Your last word: '{last['w1']}'. Partner's last word: '{last['w2']}'. "
                f"Already used (cannot repeat): {', '.join(sorted(used)) or 'none'}. "
                "Say one new word that bridges the two and your partner is likely to "
                "also pick. Reply with only the word."
            )
        s = await self._ensure()
        for _ in range(3):
            resp = await s.send_and_wait(prompt, timeout=45)
            content = resp.data.content if resp and isinstance(resp.data, AssistantMessageData) else ""
            w = extract_word(content)
            if w and w not in used:
                return w
            prompt = "Reply with exactly one NEW, unused lowercase word."
        return "river"


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    async with CopilotClient() as client:
        brain = HumanBrain(client)
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=CHROME,
                                              args=["--no-sandbox"])
            context = await browser.new_context(
                viewport={"width": 720, "height": 900},
                record_video_dir=OUT_DIR,
                record_video_size={"width": 720, "height": 900},
            )
            page = await context.new_page()
            await page.goto(URL)
            await page.wait_for_timeout(1000)

            # Home -> Local game (human vs AI on one screen, capped rounds).
            await page.click("#localBtn")
            await page.wait_for_timeout(500)
            # Player 1 = Human "Ian"
            await page.select_option('.ptype[data-slot="1"]', "human")
            await page.fill('.pname[data-slot="1"]', "Ian")
            # Player 2 = AI on a fast flash/mini model
            await page.select_option('.ptype[data-slot="2"]', "ai")
            await page.wait_for_timeout(300)
            await page.select_option('.pmodel[data-slot="2"]', AI_MODEL)
            await page.fill('.pname[data-slot="2"]', "Copilot")
            await page.fill("#maxRounds", str(DEMO_ROUNDS))
            await page.wait_for_timeout(500)
            await page.click("#startBtn")

            await page.wait_for_selector("#game", state="visible", timeout=20000)
            await page.wait_for_timeout(900)

            # Play rounds until finished.
            for _ in range(DEMO_ROUNDS + 1):
                state = await page.evaluate("() => STATE")
                if state and state.get("finished"):
                    break
                try:
                    await page.wait_for_selector(".wordin", state="visible", timeout=60000)
                except Exception:
                    break
                state = await page.evaluate("() => STATE")
                # Force the opener on the very first human turn if requested.
                if DEMO_OPENER and state.get("round_no", 0) == 0:
                    word = DEMO_OPENER
                else:
                    word = await brain.pick(state)
                await page.fill(".wordin", word)
                await page.wait_for_timeout(500)
                await page.click("#goBtn")
                # Wait for round resolution (board grows or finished).
                prev = len((state or {}).get("rounds", []))
                for _ in range(50):
                    await page.wait_for_timeout(400)
                    st = await page.evaluate("() => STATE")
                    if st and (len(st.get("rounds", [])) > prev or st.get("finished")):
                        break
                await page.wait_for_timeout(700)

            # Linger on the result for the recording.
            await page.wait_for_timeout(3000)

            video = page.video
            await context.close()
            await browser.close()
            path = await video.path() if video else None
            print("VIDEO:", path)


if __name__ == "__main__":
    asyncio.run(main())
