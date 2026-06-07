"""A curated dictionary of common, concrete words used to seed an AI player's
opening move, so AI players don't always start with the same few words.

The system ``web2`` dictionary has ~236k entries but is dominated by obscure
words ("aalii", "aam", …) that make terrible Mind Meld openers. This curated
list keeps openings varied *and* playable — they're everyday nouns/concepts a
partner can plausibly bridge from.
"""

from __future__ import annotations

import random

# Everyday, broadly-associable words. Kept concrete and common on purpose.
WORDS: list[str] = sorted(set("""
apple river mountain ocean fire water earth wind storm cloud rain snow ice
sun moon star sky night day light shadow forest tree flower garden grass leaf
road bridge city town house door window roof wall floor table chair bed lamp
book paper pen pencil letter word story song music dance art color paint brush
dog cat horse bird fish lion tiger bear wolf fox rabbit mouse snake frog bee
ant spider eagle owl shark whale dolphin elephant monkey deer sheep cow pig
bread cheese butter milk egg honey sugar salt coffee tea wine beer apple fruit
orange lemon banana grape berry corn rice bean potato carrot onion pepper
car train plane boat ship bike wheel engine road track sail anchor harbor
king queen knight castle crown sword shield dragon wizard magic gold silver
iron stone glass wood metal cloth rope chain key lock clock watch mirror
hand foot eye ear nose mouth heart head hair tooth bone blood skin finger
love hope dream fear anger joy peace war truth lie time space life death birth
money market shop store coin price trade gift box bag basket bottle cup plate
school teacher student class lesson test grade pencil ruler desk chalk board
doctor nurse hospital medicine fever cough wound bandage health sickness cure
beach sand wave shell tide surf coast island cliff cave rock pebble harbor
winter summer spring autumn season weather climate temperature heat cold frost
phone screen camera radio television computer keyboard mouse button signal wire
ball game team score goal player field court net racket bat glove jersey medal
""".split()))


def random_word(rng: random.Random | None = None, exclude: set[str] | None = None) -> str:
    """Return a random dictionary word, avoiding any in ``exclude``."""
    r = rng or random
    exclude = exclude or set()
    pool = [w for w in WORDS if w not in exclude]
    if not pool:
        pool = WORDS
    return r.choice(pool)
