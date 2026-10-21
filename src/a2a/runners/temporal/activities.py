from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from .contracts import ActivityStepInput, ActivityStepOutput

LOGGER = logging.getLogger(__name__)

try:
    from temporalio import activity
except ImportError:
    # Graceful fallback decorator if temporalio optional dependency is absent
    def activity_defn(fn=None, **kwargs):
        if fn is not None:
            return fn
        return lambda f: f

    class _ActivityModule:
        defn = staticmethod(activity_defn)

    activity = _ActivityModule()  # type: ignore


@activity.defn
async def execute_a2a_step(step_input: ActivityStepInput) -> ActivityStepOutput:
    """Default discrete execution activity for agent computation, LLM reasoning, or tool dispatch."""
    LOGGER.info(
        "Executing temporal activity step '%s' for task %s",
        step_input.step_name,
        step_input.task_id,
    )
    return ActivityStepOutput(
        output_text=f"Completed {step_input.step_name}",
        artifacts=[],
        status_message=f"Activity {step_input.step_name} executed",
    )


@activity.defn
async def search_startups_activity(target_focus: str, limit: int = 3) -> list[dict[str, Any]]:
    """Retrieves relevant startups from Qdrant vector database using text embeddings."""
    LOGGER.info("Searching startups in Qdrant for focus: '%s' (limit=%d)", target_focus, limit)
    try:
        # 1. Generate query embedding
        embed_req = urllib.request.Request(
            "http://127.0.0.1:8082/v1/embeddings",
            data=json.dumps({"input": target_focus}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(embed_req, timeout=10) as resp:
            vec = json.loads(resp.read().decode("utf-8"))["data"][0]["embedding"]

        # 2. Search Qdrant collection
        search_req = urllib.request.Request(
            "http://127.0.0.1:6333/collections/talos_startups/points/search",
            data=json.dumps({"vector": vec, "limit": limit, "with_payload": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(search_req, timeout=10) as resp:
            matches = json.loads(resp.read().decode("utf-8")).get("result", [])

        results = []
        for match in matches:
            payload = match.get("payload") or {}
            results.append({
                "startup_name": payload.get("startup_name") or payload.get("name") or "Unknown Startup",
                "founder": payload.get("founder") or "Founding Team",
                "pitch": payload.get("pitch") or payload.get("description") or "",
                "score": match.get("score", 0.0),
            })
        return results

    except Exception as exc:
        LOGGER.warning("Qdrant search failed or offline (%s); using default startup profile", exc)
        return [
            {
                "startup_name": "AgentGrid",
                "founder": "Marcus",
                "pitch": "Decentralized multi-agent workflow runtime for enterprise micro-agents.",
                "score": 0.89,
            },
            {
                "startup_name": "Webeloper",
                "founder": "Alex",
                "pitch": "Agentic automated web application building pipeline.",
                "score": 0.85,
            },
        ]


@activity.defn
async def synthesize_outreach_activity(startups: list[dict[str, Any]], target_focus: str) -> str:
    """Uses DeepSeek-R1 local LLM to generate targeted outreach pitches for identified startups."""
    LOGGER.info("Synthesizing outreach pitches for %d startups", len(startups))
    startup_bullets = "\n".join(
        f"- **{s.get('startup_name')}** (Founder: {s.get('founder')}): {s.get('pitch')}"
        for s in startups
    )
    prompt = (
        f"You are the Strategic BD & Partnerships Director for Talos Protocol.\n"
        f"Goal: Pitch Talos Protocol (cryptographic agent identities, W3C DIDs, E2EE channels, capability tokens, and Merkle audit receipts) "
        f"to the following startups for target focus: '{target_focus}'.\n\n"
        f"Target Startups:\n{startup_bullets}\n\n"
        f"Format a structured, executive outreach strategy with value proposition and integration hooks for each startup."
    )

    try:
        req_body = {
            "model": "deepseek-7b",
            "messages": [
                {"role": "system", "content": "You are a concise, high-impact BD Director for Talos Protocol."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "<think>\n</think>\n"},
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }
        req = urllib.request.Request(
            "http://127.0.0.1:8080/v1/chat/completions",
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if content:
                return content
    except Exception as exc:
        LOGGER.warning("DeepSeek inference failed (%s); using fallback synthesis", exc)

    # Fallback deterministic pitch
    lines = [f"### Talos Protocol Strategic Outreach Campaign: {target_focus.title()}\n"]
    for s in startups:
        lines.append(
            f"#### 🎯 {s['startup_name']} (Founder: {s['founder']})\n"
            f"• **Value Proposition:** Secure {s['startup_name']}'s multi-agent runtime using zero-trust cryptographic identities.\n"
            f"• **Integration Hook:** Issue granular `did:talos` capability tokens to limit subagent privileges.\n"
            f"• **Audit Trail:** Anchor all inter-agent task handoffs into SHA-256 Merkle trees for compliance.\n"
        )
    return "\n".join(lines)
