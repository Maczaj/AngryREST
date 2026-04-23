from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class KeyValue:
    key: str = ""
    value: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return {"key": self.key, "value": self.value, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict) -> KeyValue:
        return cls(
            key=data.get("key", ""),
            value=data.get("value", ""),
            enabled=data.get("enabled", True),
        )


@dataclass
class RequestDef:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    headers: list[KeyValue] = field(default_factory=list)
    query_params: list[KeyValue] = field(default_factory=list)
    body_type: str = "none"  # none, form, json, graphql, multipart
    body_content: str = ""
    body_form: list[KeyValue] = field(default_factory=list)
    body_files: list[KeyValue] = field(default_factory=list)  # key=field_name, value=file_path
    graphql_variables: str = ""
    pre_script: str = ""
    post_script: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "method": self.method,
            "url": self.url,
            "headers": [h.to_dict() for h in self.headers],
            "query_params": [q.to_dict() for q in self.query_params],
            "body_type": self.body_type,
            "body_content": self.body_content,
            "body_form": [f.to_dict() for f in self.body_form],
            "body_files": [f.to_dict() for f in self.body_files],
            "graphql_variables": self.graphql_variables,
            "pre_script": self.pre_script,
            "post_script": self.post_script,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RequestDef:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "New Request"),
            method=data.get("method", "GET"),
            url=data.get("url", ""),
            headers=[KeyValue.from_dict(h) for h in data.get("headers", [])],
            query_params=[KeyValue.from_dict(q) for q in data.get("query_params", [])],
            body_type=data.get("body_type", "none"),
            body_content=data.get("body_content", ""),
            body_form=[KeyValue.from_dict(f) for f in data.get("body_form", [])],
            body_files=[KeyValue.from_dict(f) for f in data.get("body_files", [])],
            graphql_variables=data.get("graphql_variables", ""),
            pre_script=data.get("pre_script", ""),
            post_script=data.get("post_script", ""),
        )


@dataclass
class Collection:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Collection"
    requests: list[RequestDef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "requests": [r.to_dict() for r in self.requests],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Collection:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "New Collection"),
            requests=[RequestDef.from_dict(r) for r in data.get("requests", [])],
        )
