from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from typing import Any, Callable

from ..models.card import AgentCard

LOGGER = logging.getLogger(__name__)


class AgentCardRegistry:
    """In-memory registry and peer resolver for Agent Cards with TTL caching."""

    def __init__(self, default_ttl_seconds: int = 900) -> None:
        self.default_ttl = default_ttl_seconds
        self._cards: dict[str, AgentCard] = {}
        self._expires_at: dict[str, float] = {}

    def register(self, card: AgentCard, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._cards[card.did] = card
        self._expires_at[card.did] = time.time() + ttl
        LOGGER.debug("Registered agent card for %s (TTL: %ss)", card.did, ttl)

    def get(self, did: str) -> AgentCard | None:
        if did not in self._cards:
            return None
        if time.time() > self._expires_at.get(did, 0):
            self.remove(did)
            return None
        return self._cards[did]

    def remove(self, did: str) -> None:
        self._cards.pop(did, None)
        self._expires_at.pop(did, None)

    def list_all(self, include_expired: bool = False) -> list[AgentCard]:
        now = time.time()
        res: list[AgentCard] = []
        for did, card in list(self._cards.items()):
            if include_expired or now <= self._expires_at.get(did, 0):
                res.append(card)
            else:
                self.remove(did)
        return res

    def find_by_skill(self, skill_id: str) -> list[AgentCard]:
        return [c for c in self.list_all() if c.has_skill(skill_id)]

    def find_by_extension(self, extension_name: str) -> list[AgentCard]:
        return [c for c in self.list_all() if c.has_extension(extension_name)]

    async def resolve_from_url(
        self,
        base_url: str,
        verify_fn: Callable[[dict[str, Any]], bool] | None = None,
        ttl_seconds: int | None = None,
    ) -> AgentCard:
        """Fetches and caches an Agent Card from a remote agent's well-known endpoint."""
        url = base_url.rstrip("/")
        if not url.endswith((".json", "/extendedAgentCard")):
            url = f"{url}/.well-known/agent.json"

        def _fetch() -> dict[str, Any]:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "TalosA2A/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                content = resp.read()
                return json.loads(content.decode("utf-8"))

        data = await asyncio.to_thread(_fetch)

        if verify_fn and not verify_fn(data):
            raise ValueError(f"Agent Card signature verification failed for {url}")

        card = AgentCard.from_dict(data)
        self.register(card, ttl_seconds=ttl_seconds)
        return card
