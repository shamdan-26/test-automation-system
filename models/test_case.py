from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TestType(str, Enum):
    API_REST = "api_rest"
    API_SOAP = "api_soap"
    UI = "ui"
    MOBILE = "mobile"
    PERFORMANCE = "performance"
    REGRESSION = "regression"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class TestStep(BaseModel):
    order: int
    description: str
    action: str
    expected_result: str
    data: dict[str, Any] = Field(default_factory=dict)


class ApiTestCase(BaseModel):
    method: HttpMethod
    endpoint: str
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] | list[Any] | None = None
    expected_status: int = 200
    expected_schema: dict[str, Any] | None = None
    expected_fields: dict[str, Any] = Field(default_factory=dict)


class SoapTestCase(BaseModel):
    wsdl: str
    service: str
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_fields: dict[str, Any] = Field(default_factory=dict)


class UiTestCase(BaseModel):
    url: str
    steps: list[TestStep] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)


class PerformanceTestCase(BaseModel):
    endpoint: str
    method: HttpMethod = HttpMethod.GET
    body: dict[str, Any] | None = None
    weight: int = 1  # relative frequency for Locust


class TestCase(BaseModel):
    id: str
    title: str
    description: str
    type: TestType
    tags: list[str] = Field(default_factory=list)
    priority: str = "medium"   # low | medium | high | critical
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(default_factory=list)
    expected_result: str = ""
    api: ApiTestCase | None = None
    soap: SoapTestCase | None = None
    ui: UiTestCase | None = None
    performance: PerformanceTestCase | None = None
    source: str = ""           # origin: document name, story ID, task ID
    story_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
