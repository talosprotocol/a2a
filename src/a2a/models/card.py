from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Skill:
    id: str
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Skill:
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            returns=data.get("returns", {}),
            tags=data.get("tags", []),
        )


@dataclass
class AgentCapabilities:
    streaming: bool = True
    pushNotifications: bool = False
    extendedAgentCard: bool = True
    extensions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "streaming": self.streaming,
            "pushNotifications": self.pushNotifications,
            "extendedAgentCard": self.extendedAgentCard,
            "extensions": list(self.extensions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCapabilities:
        return cls(
            streaming=bool(data.get("streaming", True)),
            pushNotifications=bool(data.get("pushNotifications", False)),
            extendedAgentCard=bool(data.get("extendedAgentCard", True)),
            extensions=list(data.get("extensions", [])),
        )


@dataclass
class AgentEndpoints:
    rpc: str
    stream: str | None = None
    didDocument: str | None = None
    health: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"rpc": self.rpc}
        if self.stream:
            res["stream"] = self.stream
        if self.didDocument:
            res["didDocument"] = self.didDocument
        if self.health:
            res["health"] = self.health
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentEndpoints:
        return cls(
            rpc=data["rpc"],
            stream=data.get("stream"),
            didDocument=data.get("didDocument"),
            health=data.get("health"),
        )


@dataclass
class AgentCard:
    name: str
    description: str
    did: str
    version: str = "1.0.0"
    protocol: str = "a2a-v1"
    endpoints: AgentEndpoints | None = None
    supportedTaskModes: list[str] = field(
        default_factory=lambda: ["immediate", "streaming", "wait", "get"]
    )
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    protocols: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"protocol": "a2a-v1", "role": "server"},
            {"protocol": "jsonrpc-2.0", "role": "bidirectional"},
        ]
    )
    skills: list[Skill] = field(default_factory=list)
    proof: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_proof: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://talosprotocol.com/schemas/agent-card/v1.json",
            ],
            "name": self.name,
            "description": self.description,
            "did": self.did,
            "version": self.version,
            "protocol": self.protocol,
            "supportedTaskModes": list(self.supportedTaskModes),
            "capabilities": self.capabilities.to_dict(),
            "protocols": self.protocols,
            "skills": [s.to_dict() for s in self.skills],
            "metadata": self.metadata,
        }
        if self.endpoints:
            data["endpoints"] = self.endpoints.to_dict()
        if include_proof and self.proof:
            data["proof"] = self.proof
        return data

    def to_json(self, include_proof: bool = True, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(include_proof=include_proof), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCard:
        capabilities = data.get("capabilities", {})
        if isinstance(capabilities, dict):
            cap_obj = AgentCapabilities.from_dict(capabilities)
        else:
            cap_obj = capabilities

        endpoints = data.get("endpoints")
        if isinstance(endpoints, dict):
            end_obj = AgentEndpoints.from_dict(endpoints)
        else:
            end_obj = endpoints

        skills_raw = data.get("skills", [])
        skills = [Skill.from_dict(s) if isinstance(s, dict) else s for s in skills_raw]

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            did=data["did"],
            version=data.get("version", "1.0.0"),
            protocol=data.get("protocol", "a2a-v1"),
            endpoints=end_obj,
            supportedTaskModes=list(data.get("supportedTaskModes", ["immediate", "streaming", "wait", "get"])),
            capabilities=cap_obj,
            protocols=data.get("protocols", []),
            skills=skills,
            proof=data.get("proof"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> AgentCard:
        data = json.loads(raw)
        return cls.from_dict(data)

    def has_extension(self, extension_name: str) -> bool:
        return extension_name in self.capabilities.extensions

    def has_skill(self, skill_id: str) -> bool:
        return any(s.id == skill_id for s in self.skills)
