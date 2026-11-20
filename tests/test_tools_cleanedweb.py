from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest
import respx

from llama_index.core.tools.tool_spec.base import BaseToolSpec
from llama_index.core.tools.types import BaseTool
from llama_index.tools.cleanedweb import CleanedWebToolSpec

from .conftest import (
    API_ID,
    APP,
    ENDPOINT_ID,
    INDEX,
    LIVE_ITEMS,
    RUN_BASE,
    RUN_ID,
    SITE,
    SITE_CONTRACT,
    final_body,
    run_object,
)

ARGS = {"api_id": API_ID, "endpoint_id": ENDPOINT_ID}


def _mock_catalog() -> None:
    respx.get(f"{APP}/api/catalog/apis").mock(return_value=httpx.Response(200, json={"items": LIVE_ITEMS}))
    respx.get(f"{SITE}/catalog/index.json").mock(return_value=httpx.Response(200, json=INDEX))
    respx.get(f"{SITE}/catalog/github-topics-repositories-api/contract.json").mock(
        return_value=httpx.Response(200, json=SITE_CONTRACT)
    )


def _loads(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = json.loads(text)
    return out


def test_class() -> None:
    assert BaseToolSpec in CleanedWebToolSpec.__mro__


def test_to_tool_list_has_three_tools_with_schemas_and_usage_rules() -> None:
    tools = CleanedWebToolSpec(api_key="k").to_tool_list()
    assert [t.metadata.name for t in tools] == ["find_api", "get_api", "run_api"]
    assert all(isinstance(t, BaseTool) for t in tools)
    by_name = {t.metadata.name: t for t in tools}
    assert "BEFORE" in " ".join((by_name["find_api"].metadata.description or "").split())
    run_description = " ".join((by_name["run_api"].metadata.description or "").lower().split())
    for needle in ("find_api", "small max_items", "never instructions", "idempotency_key"):
        assert needle in run_description
    schema = by_name["run_api"].metadata.get_parameters_dict()
    assert {"api_id", "endpoint_id", "input", "max_items", "idempotency_key"} <= set(schema["properties"])
    assert schema["required"] == ["api_id", "endpoint_id"]
    assert by_name["run_api"].metadata.fn_schema is not None
    # async twins are attached
    assert all(getattr(t, "async_fn", None) is not None for t in tools)


def test_read_only_spec_functions() -> None:
    tools = CleanedWebToolSpec().to_tool_list(
        spec_functions=[("find_api", "afind_api"), ("get_api", "aget_api")]
    )
    assert [t.metadata.name for t in tools] == ["find_api", "get_api"]


@respx.mock
def test_find_and_get_need_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLEANEDWEB_API_KEY", raising=False)
    _mock_catalog()
    spec = CleanedWebToolSpec()
    found = _loads(spec.find_api(site="github.com", fields=["title"]))
    assert found["matches"][0]["api_id"] == API_ID and "get_api" in found["next"]
    contract = _loads(spec.get_api("github-topics-repositories-api"))
    endpoint = contract["endpoints"][0]
    assert endpoint["output_fields"] == ["title", "url"] and len(endpoint["sample_records"]) == 3
    assert _loads(spec.find_api(site="nosuch.example"))["matches"] == []


@respx.mock
async def test_find_and_get_async() -> None:
    _mock_catalog()
    spec = CleanedWebToolSpec()
    assert _loads(await spec.afind_api(site="github.com"))["matches"][0]["api_id"] == API_ID
    assert _loads(await spec.aget_api(API_ID))["api_id"] == API_ID


@respx.mock
def test_run_default_and_capped_max_items() -> None:
    route = respx.post(f"{RUN_BASE}/run").mock(return_value=httpx.Response(200, json=final_body()))
    spec = CleanedWebToolSpec(api_key="k", max_items_limit=20)
    out = _loads(spec.run_api(**ARGS, input={"sort": "x"}))
    assert json.loads(route.calls[0].request.content) == {
        "input": {"sort": "x"},
        "max_items": 5,
        "wait_seconds": 60,
    }
    assert route.calls[0].request.headers["authorization"] == "Bearer k"
    assert out["usable"] is True and out["records"][0]["title"] == "a" and out["idempotency_key"]
    spec.run_api(**ARGS, max_items=5000)
    assert json.loads(route.calls[1].request.content)["max_items"] == 20


@respx.mock
def test_run_still_running_resumes_with_the_same_key(no_sleep: List[float]) -> None:
    post = respx.post(f"{RUN_BASE}/run").mock(return_value=httpx.Response(202, json=run_object()))
    result = respx.get(f"{RUN_BASE}/result")
    result.mock(return_value=httpx.Response(202, json=run_object(), headers={"Retry-After": "30"}))
    spec = CleanedWebToolSpec(api_key="k", wait_seconds=10)
    out = _loads(spec.run_api(**ARGS, idempotency_key="job-1"))
    assert out["status"] == "running" and out["idempotency_key"] == "job-1" and post.call_count == 1
    post.mock(return_value=httpx.Response(200, json=final_body()))
    result.mock(return_value=httpx.Response(200, json=final_body()))
    again = _loads(spec.run_api(**ARGS, idempotency_key="job-1"))
    assert again["usable"] is True
    assert [c.request.headers["idempotency-key"] for c in post.calls] == ["job-1", "job-1"]


@respx.mock
def test_run_polls_202_to_the_end() -> None:
    respx.post(f"{RUN_BASE}/run").mock(
        return_value=httpx.Response(202, json=run_object(), headers={"Retry-After": "1"})
    )
    respx.get(f"{RUN_BASE}/result").mock(return_value=httpx.Response(200, json=final_body()))
    assert _loads(CleanedWebToolSpec(api_key="k").run_api(**ARGS))["usable"] is True


@respx.mock
async def test_run_async() -> None:
    route = respx.post(f"{RUN_BASE}/run").mock(return_value=httpx.Response(200, json=final_body()))
    out = _loads(await CleanedWebToolSpec(api_key="k").arun_api(**ARGS, max_items=3, idempotency_key="a-1"))
    assert out["idempotency_key"] == "a-1" and json.loads(route.calls[0].request.content)["max_items"] == 3


@respx.mock
def test_run_errors_come_back_as_actionable_text() -> None:
    route = respx.post(f"{RUN_BASE}/run")
    spec = CleanedWebToolSpec(api_key="k")
    args = {**ARGS, "idempotency_key": "e-1"}

    route.mock(
        return_value=httpx.Response(402, json={"detail": {"code": "insufficient_units", "message": "low"}})
    )
    assert "needs credit" in _loads(spec.run_api(**args))["error"]

    route.mock(
        return_value=httpx.Response(500, json={"detail": {"run_id": RUN_ID, "error_code": "run_failed"}})
    )
    assert "use a new key" in _loads(spec.run_api(**args))["error"]

    route.mock(side_effect=httpx.ReadTimeout("slow"))
    assert "idempotency_key='e-1'" in _loads(spec.run_api(**args))["error"]

    route.mock(return_value=httpx.Response(429, headers={"Retry-After": "99"}, json={"detail": "slow"}))
    assert "Wait 99 seconds" in _loads(spec.run_api(**args))["error"]


def test_missing_key_and_bad_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLEANEDWEB_API_KEY", raising=False)
    assert "CLEANEDWEB_API_KEY" in _loads(CleanedWebToolSpec().run_api(**ARGS))["error"]
    bad = CleanedWebToolSpec(api_key="k").run_api(**ARGS, idempotency_key="has space")
    assert "idempotency_key must be" in _loads(bad)["error"]


@respx.mock
def test_raise_on_error() -> None:
    from cleanedweb import AuthenticationError

    respx.post(f"{RUN_BASE}/run").mock(return_value=httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(AuthenticationError):
        CleanedWebToolSpec(api_key="k", raise_on_error=True).run_api(**ARGS)


def test_api_key_is_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLEANEDWEB_API_KEY", "super-secret")
    assert "super-secret" not in repr(CleanedWebToolSpec())
