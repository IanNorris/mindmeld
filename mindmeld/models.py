"""Model discovery for the Copilot SDK.

The SDK's :meth:`CopilotClient.list_models` currently raises on some models
because of a missing ``multiplier`` field in their billing payload. We sidestep
that by calling the raw ``models.list`` JSON-RPC and reading the fields we need.
"""

from __future__ import annotations

from dataclasses import dataclass

# Internal/experimental models are noisy for a game menu, so we hide them.
# Matched (case-insensitively) against both the model id and its display name.
_HIDE_SUBSTR = ("internal",)


@dataclass(frozen=True)
class Model:
    id: str
    name: str


async def list_models(client) -> list[Model]:
    """Return selectable models via the raw RPC, skipping internal ones."""
    resp = await client._client.request("models.list", {})
    out: list[Model] = []
    for m in resp.get("models", []):
        mid = m.get("id")
        name = m.get("name") or mid
        if not mid:
            continue
        haystack = f"{mid} {name}".lower()
        if any(s in haystack for s in _HIDE_SUBSTR):
            continue
        out.append(Model(id=mid, name=name))
    return out
