from typing import Any

import pytest
from a2a import (
    AgentCapabilities,
    AgentCard,
    AgentCardRegistry,
    AgentEndpoints,
    CrewAIA2AAdapter,
    InMemoryTaskRunner,
    LangGraphA2AAdapter,
    Message,
    Skill,
    TaskState,
)


def test_agent_card_serialization() -> None:
    card = AgentCard(
        name="test-agent",
        description="Testing card serialization",
        did="did:talos:agent:test:12345",
        endpoints=AgentEndpoints(rpc="http://localhost:8000/rpc"),
        capabilities=AgentCapabilities(
            streaming=True,
            extensions=["talos.security.v1", "talos.audit.v1"],
        ),
        skills=[
            Skill(
                id="search",
                name="Search Tool",
                description="Performs query lookups",
                parameters={"query": {"type": "string"}},
            )
        ],
        metadata={"owner": "platform"},
    )

    data = card.to_dict()
    assert data["name"] == "test-agent"
    assert data["endpoints"]["rpc"] == "http://localhost:8000/rpc"
    assert "talos.security.v1" in data["capabilities"]["extensions"]
    assert card.has_extension("talos.audit.v1")
    assert not card.has_extension("talos.nonexistent")
    assert card.has_skill("search")

    json_str = card.to_json()
    restored = AgentCard.from_json(json_str)
    assert restored.did == card.did
    assert restored.skills[0].id == "search"


def test_agent_card_registry() -> None:
    registry = AgentCardRegistry(default_ttl_seconds=60)
    card1 = AgentCard(
        name="agent-1",
        description="Scout node",
        did="did:talos:agent:scout:1",
        skills=[Skill(id="scout:slots", name="Slot Scout", description="Scans slots")],
        capabilities=AgentCapabilities(extensions=["talos.security.v1"]),
    )
    card2 = AgentCard(
        name="agent-2",
        description="Remediator node",
        did="did:talos:agent:remediator:2",
        skills=[Skill(id="cluster:drain", name="Node Drainer", description="Drains nodes")],
        capabilities=AgentCapabilities(extensions=["talos.temporal.v1"]),
    )

    registry.register(card1)
    registry.register(card2)

    assert registry.get("did:talos:agent:scout:1") is not None
    assert len(registry.list_all()) == 2

    # Query by skill
    scouts = registry.find_by_skill("scout:slots")
    assert len(scouts) == 1
    assert scouts[0].name == "agent-1"

    # Query by extension
    temporal_nodes = registry.find_by_extension("talos.temporal.v1")
    assert len(temporal_nodes) == 1
    assert temporal_nodes[0].name == "agent-2"


@pytest.mark.asyncio
async def test_langgraph_adapter() -> None:
    class MockGraph:
        async def ainvoke(self, inputs: dict) -> dict:
            return {"messages": [{"content": f"Graph response to: {inputs['messages'][0]['content']}"}]}

    graph = MockGraph()
    adapter = LangGraphA2AAdapter(
        graph=graph,
        name="graph-agent",
        description="LangGraph Assistant",
        did="did:talos:agent:graph:1",
    )

    card = adapter.as_agent_card()
    assert card.name == "graph-agent"
    assert card.metadata["framework"] == "langgraph"

    runner = InMemoryTaskRunner()
    handler = adapter.as_task_handler()
    task, reply = await runner.execute_immediate(
        context_id="ctx-graph",
        message=Message.from_text("Analyze traffic", role="user"),
        handler=handler,
    )

    assert task.status.state == TaskState.COMPLETED
    assert "Graph response to: Analyze traffic" in reply.get_text()


@pytest.mark.asyncio
async def test_crewai_adapter() -> None:
    class MockTool:
        name = "terminal_exec"
        description = "Runs shell command"

    class MockAgent:
        role = "DevOps Engineer"
        goal = "Keep cluster operational"
        tools = [MockTool()]

        async def kickoff_async(self, inputs: dict) -> Any:
            class Result:
                raw = f"Executed task for {inputs['prompt']}"
            return Result()

    agent = MockAgent()
    adapter = CrewAIA2AAdapter(
        crew_or_agent=agent,
        name="devops-crew",
        description="",
        did="did:talos:agent:crew:1",
    )

    card = adapter.as_agent_card()
    assert card.name == "devops-crew"
    assert card.skills[0].id == "tool:terminal_exec"

    runner = InMemoryTaskRunner()
    handler = adapter.as_task_handler()
    task, reply = await runner.execute_immediate(
        context_id="ctx-crew",
        message=Message.from_text("Deploy patch", role="user"),
        handler=handler,
    )

    assert task.status.state == TaskState.COMPLETED
    assert "Executed task for Deploy patch" in reply.get_text()
