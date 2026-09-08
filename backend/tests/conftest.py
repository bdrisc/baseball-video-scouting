"""Shared lightweight database doubles for API and SQL unit tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

import pytest


@dataclass
class SqlCall:
    operation: str
    query: str
    parameters: Any


class ScriptedCursor:
    """Return predetermined rows while recording every parameterized SQL call."""

    def __init__(self, connection: "ScriptedConnection") -> None:
        self.connection = connection
        self.response: Any = None

    def __enter__(self) -> "ScriptedCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, parameters: Any = None) -> None:
        self.connection.calls.append(SqlCall("execute", query, parameters))
        self.response = self.connection.next_response()

    def executemany(self, query: str, parameters: Iterable[Any]) -> None:
        materialized = list(parameters)
        self.connection.calls.append(SqlCall("executemany", query, materialized))
        self.response = self.connection.next_response()

    def fetchone(self) -> Any:
        if isinstance(self.response, list):
            return deepcopy(self.response[0]) if self.response else None
        return deepcopy(self.response)

    def fetchall(self) -> list[Any]:
        if self.response is None:
            return []
        if isinstance(self.response, list):
            return deepcopy(self.response)
        return [deepcopy(self.response)]


class ScriptedConnection:
    """Small psycopg-compatible connection used only by the test suite."""

    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[SqlCall] = []

    def cursor(self) -> ScriptedCursor:
        return ScriptedCursor(self)

    def next_response(self) -> Any:
        if not self.responses:
            return None
        return self.responses.pop(0)


@pytest.fixture
def scripted_connection_factory():
    def factory(responses: list[Any] | None = None) -> ScriptedConnection:
        return ScriptedConnection(responses)

    return factory
