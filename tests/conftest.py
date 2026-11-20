from __future__ import annotations

from typing import Any, Dict, List

import pytest

API_ORIGIN = "https://api.cleanedweb.com"
APP = "https://app.cleanedweb.com"
SITE = "https://cleanedweb.com"
API_ID = "generated_aaaaaaaaaaaaaaaaaaaaaaaa"
ENDPOINT_ID = f"{API_ID}_search"
RUN_BASE = f"{API_ORIGIN}/v1/catalog/public/apis/{API_ID}/endpoints/{ENDPOINT_ID}"
RUN_ID = "0123456789abcdef0123456789abcdef"

LIVE_ITEMS = [
    {
        "api_id": API_ID,
        "name": "GitHub Topics Repositories",
        "short_description": "Repos under a topic",
        "category": "uncategorized",
        "site": {"name": "GitHub", "domain": "github.com"},
        "endpoints": [{"endpoint_id": ENDPOINT_ID, "name": "Extract records", "status": "available"}],
    }
]
INDEX = {
    "apis": [
        {
            "api_id": API_ID,
            "slug": "github-topics-repositories-api",
            "source": {"name": "GitHub", "domain": "github.com"},
            "key_fields": ["title", "url"],
        }
    ]
}
SITE_CONTRACT = {
    "name": "GitHub Topics Repositories API",
    "api_id": API_ID,
    "slug": "github-topics-repositories-api",
    "description": "Repos",
    "source": {"name": "GitHub", "domain": "github.com"},
    "version": "1.0",
    "endpoints": [
        {
            "endpoint_id": ENDPOINT_ID,
            "name": "Extract records",
            "input_schema": {"type": "object", "properties": {"sort": {"type": "string"}}, "required": []},
            "output_schema": {"type": "object", "properties": {"title": {}, "url": {}}},
            "examples": [
                {"records": [{"title": f"r{n}", "url": f"https://github.com/r{n}"} for n in range(5)]}
            ],
        }
    ],
}


def final_body(**overrides: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "records": [{"title": "a", "url": "https://x.test/a"}],
        "summary": {"status": "bounded", "within_scope_passed": True, "records": 1},
        "run": {"run_id": RUN_ID, "status": "finished", "stop_reason": "max_items", "units_charged": 1},
        "delivery": {"runId": RUN_ID, "recordCount": 1},
    }
    body.update(overrides)
    return body


def run_object() -> Dict[str, Any]:
    return {"run_id": RUN_ID, "status": "running", "poll_after_seconds": 30}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> List[float]:
    recorded: List[float] = []

    def fake(seconds: float) -> None:
        recorded.append(seconds)

    async def fake_async(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr("cleanedweb._sync.time.sleep", fake)
    monkeypatch.setattr("cleanedweb._async.asyncio.sleep", fake_async)
    return recorded
