"""Model discovery for the Copilot SDK.

The SDK's :meth:`CopilotClient.list_models` currently raises on some models
because of a missing ``multiplier`` field in their billing payload. We sidestep
that by calling the raw ``models.list`` JSON-RPC and reading the fields we need.
"""

from __future__ import annotations

from dataclasses import dataclass

# Models flagged "Internal only" in their display name are noisy for a game
# menu, so we hide them by default.
_HIDE_SUBSTR = ("internal only",)


@dataclass(frozen=True)
class Model:
    id: str
    name: str


async def list_models(client) -> list[Model]:
    """Return selectable models via the raw RPC, skipping internal-only ones."""
    resp = await client._client.request("models.list", {})
    out: list[Model] = []
    for m in resp.get("models", []):
        mid = m.get("id")
        name = m.get("name") or mid
        if not mid:
            continue
        if any(s in name.lower() for s in _HIDE_SUBSTR):
            continue
        out.append(Model(id=mid, name=name))
    return out
