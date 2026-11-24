from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Environment:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Environment"
    variables: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "variables": dict(self.variables),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Environment:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "New Environment"),
            variables=dict(data.get("variables", {})),
        )