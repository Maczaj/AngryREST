from __future__ import annotations

import pytest

from angryrest.domain.models.collection import Collection, KeyValue, RequestDef
from angryrest.domain.models.environment import Environment


class TestKeyValue:
    def test_defaults(self) -> None:
        kv = KeyValue()
        assert kv.key == ""
        assert kv.value == ""
        assert kv.enabled is True

    def test_round_trip(self) -> None:
        kv = KeyValue(key="Authorization", value="Bearer token", enabled=False)
        assert KeyValue.from_dict(kv.to_dict()) == kv

    def test_from_dict_missing_keys_use_defaults(self) -> None:
        kv = KeyValue.from_dict({})
        assert kv.key == ""
        assert kv.value == ""
        assert kv.enabled is True

    def test_to_dict_keys(self) -> None:
        kv = KeyValue(key="X-Foo", value="bar", enabled=True)
        d = kv.to_dict()
        assert set(d.keys()) == {"key", "value", "enabled"}


class TestRequestDef:
    def test_defaults(self) -> None:
        r = RequestDef()
        assert r.name == "New Request"
        assert r.method == "GET"
        assert r.url == ""
        assert r.body_type == "none"
        assert r.headers == []
        assert r.query_params == []

    def test_unique_ids(self) -> None:
        assert RequestDef().id != RequestDef().id

    def test_round_trip_minimal(self) -> None:
        r = RequestDef(name="Ping", method="GET", url="https://example.com")
        restored = RequestDef.from_dict(r.to_dict())
        assert restored.id == r.id
        assert restored.name == r.name
        assert restored.method == r.method
        assert restored.url == r.url

    def test_round_trip_with_headers_and_params(self) -> None:
        r = RequestDef(
            name="Full",
            method="POST",
            url="https://api.example.com/v1",
            headers=[KeyValue("Content-Type", "application/json")],
            query_params=[KeyValue("page", "1")],
            body_type="json",
            body_content='{"key": "value"}',
            pre_script="env['token'] = 'abc'",
            post_script="assert_status(200)",
        )
        restored = RequestDef.from_dict(r.to_dict())
        assert restored.headers[0].key == "Content-Type"
        assert restored.query_params[0].value == "1"
        assert restored.body_content == r.body_content
        assert restored.pre_script == r.pre_script
        assert restored.post_script == r.post_script

    def test_from_dict_unknown_keys_ignored(self) -> None:
        data = {"name": "Test", "unknown_field": "ignored"}
        r = RequestDef.from_dict(data)
        assert r.name == "Test"


class TestCollection:
    def test_defaults(self) -> None:
        c = Collection()
        assert c.name == "New Collection"
        assert c.requests == []

    def test_unique_ids(self) -> None:
        assert Collection().id != Collection().id

    def test_round_trip_empty(self) -> None:
        c = Collection(name="Empty")
        restored = Collection.from_dict(c.to_dict())
        assert restored.id == c.id
        assert restored.name == c.name
        assert restored.requests == []

    def test_round_trip_with_requests(self) -> None:
        c = Collection(
            name="My API",
            requests=[
                RequestDef(name="GET users", method="GET", url="https://api.example.com/users"),
                RequestDef(name="POST user", method="POST", url="https://api.example.com/users"),
            ],
        )
        restored = Collection.from_dict(c.to_dict())
        assert len(restored.requests) == 2
        assert restored.requests[0].name == "GET users"
        assert restored.requests[1].method == "POST"


class TestEnvironment:
    def test_defaults(self) -> None:
        e = Environment()
        assert e.name == "New Environment"
        assert e.variables == {}

    def test_unique_ids(self) -> None:
        assert Environment().id != Environment().id

    def test_round_trip(self) -> None:
        e = Environment(name="Staging", variables={"base_url": "https://staging.example.com", "token": "abc123"})
        restored = Environment.from_dict(e.to_dict())
        assert restored.id == e.id
        assert restored.name == e.name
        assert restored.variables == e.variables

    def test_variables_are_copied(self) -> None:
        e = Environment(variables={"key": "val"})
        restored = Environment.from_dict(e.to_dict())
        restored.variables["key"] = "changed"
        assert e.variables["key"] == "val"