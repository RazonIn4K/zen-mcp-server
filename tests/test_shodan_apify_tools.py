import json

import pytest

from tools.apify_tool import ApifyTool
from tools.shodan_tool import ShodanTool


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    def __init__(self, get_handler=None, post_handler=None):
        self._get_handler = get_handler
        self._post_handler = post_handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, params=None):
        if self._get_handler is None:
            raise AssertionError("unexpected GET request")
        return self._get_handler(url, headers=headers, params=params)

    async def post(self, url, headers=None, json=None, data=None, params=None):
        if self._post_handler is None:
            raise AssertionError("unexpected POST request")
        return self._post_handler(url, headers=headers, json=json, data=data, params=params)


@pytest.mark.asyncio
async def test_shodan_get_facets_uses_count_endpoint(monkeypatch):
    import httpx

    def fake_get(url, headers=None, params=None):
        assert url.endswith("/shodan/host/count")
        assert params["key"] == "test-key"
        assert params["query"] == "ssl:google"
        assert params["facets"] == "country,port"
        return FakeResponse({"total": 42, "facets": {"country": [{"value": "US", "count": 42}]}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient(get_handler=fake_get))

    tool = ShodanTool()
    result = await tool._get_facets("test-key", "ssl:google", "country,port")

    assert result["status"] == "success"
    assert result["total"] == 42
    assert result["facets"]["country"][0]["value"] == "US"


@pytest.mark.asyncio
async def test_shodan_search_writes_credit_ledger(monkeypatch, tmp_path):
    import httpx

    import tools.shodan_tool as shodan_tool

    ledger_path = tmp_path / "credits.json"

    async def fake_rate_limit():
        return None

    def fake_get(url, headers=None, params=None):
        assert url.endswith("/shodan/host/search")
        return FakeResponse({"total": 1, "matches": [{"ip_str": "1.1.1.1"}]})

    monkeypatch.setattr(shodan_tool, "SHODAN_CREDIT_LEDGER", ledger_path)
    monkeypatch.setattr(shodan_tool, "_respect_chargeable_rate_limit", fake_rate_limit)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient(get_handler=fake_get))

    tool = ShodanTool()
    result = await tool._search_shodan("test-key", "ssl:google", 1)

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert result["credit_ledger_path"] == str(ledger_path)
    assert ledger["entries"][-1]["action"] == "search_shodan"
    assert ledger["entries"][-1]["subject"] == "ssl:google"
    assert ledger["entries"][-1]["credits_spent"] == 1


@pytest.mark.asyncio
async def test_apify_run_actor_surfaces_dataset_id(monkeypatch):
    import httpx

    def fake_post(url, headers=None, json=None, data=None, params=None):
        assert url.endswith("/acts/apify~sample/runs")
        assert headers["Authorization"] == "Bearer token"
        assert json == {"foo": "bar"}
        return FakeResponse(
            {
                "data": {
                    "id": "run-123",
                    "status": "RUNNING",
                    "startedAt": "2026-04-15T00:00:00Z",
                    "defaultDatasetId": "dataset-123",
                }
            }
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient(post_handler=fake_post))

    tool = ApifyTool()
    result = await tool._run_actor("token", "apify~sample", {"foo": "bar"})

    assert result["status"] == "success"
    assert result["run_id"] == "run-123"
    assert result["dataset_id"] == "dataset-123"


@pytest.mark.asyncio
async def test_apify_get_actor_run_fetches_dataset_items(monkeypatch):
    import httpx

    def fake_get(url, headers=None, params=None):
        assert url.endswith("/actor-runs/run-123")
        return FakeResponse(
            {
                "data": {
                    "id": "run-123",
                    "status": "SUCCEEDED",
                    "startedAt": "2026-04-15T00:00:00Z",
                    "finishedAt": "2026-04-15T00:00:03Z",
                    "defaultDatasetId": "dataset-123",
                }
            }
        )

    async def fake_get_dataset_items(api_token, dataset_id, limit=10):
        assert api_token == "token"
        assert dataset_id == "dataset-123"
        assert limit == 100
        return {"status": "success", "items": [{"url": "https://example.com"}]}

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient(get_handler=fake_get))

    tool = ApifyTool()
    monkeypatch.setattr(tool, "_get_dataset_items", fake_get_dataset_items)
    result = await tool._get_actor_run("token", "run-123")

    assert result["status"] == "success"
    assert result["dataset_id"] == "dataset-123"
    assert result["output"] == [{"url": "https://example.com"}]


@pytest.mark.asyncio
async def test_apify_get_dataset_items_uses_requested_limit(monkeypatch):
    import httpx

    def fake_get(url, headers=None, params=None):
        assert url.endswith("/datasets/dataset-123/items")
        assert params["clean"] is True
        assert params["limit"] == 10
        return FakeResponse([{"id": 1}, {"id": 2}])

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient(get_handler=fake_get))

    tool = ApifyTool()
    result = await tool._get_dataset_items("token", "dataset-123", 10)

    assert result["status"] == "success"
    assert result["returned"] == 2
    assert result["items"][0]["id"] == 1


@pytest.mark.asyncio
async def test_apify_missing_token_returns_hint(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)

    tool = ApifyTool()
    results = await tool.execute({"action": "run_actor", "actor_id": "apify~sample", "input_data": {}})
    payload = json.loads(results[0].text)

    assert payload["status"] == "error"
    assert "hint" in payload
    assert "console.apify.com" in payload["hint"]


@pytest.mark.asyncio
async def test_apify_run_actor_401_returns_hint(monkeypatch):
    import httpx

    def fake_post(url, headers=None, json=None, data=None, params=None):
        return FakeResponse({}, status_code=401)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient(post_handler=fake_post))

    tool = ApifyTool()
    result = await tool._run_actor("bad-token", "apify~sample", {})

    assert result["status"] == "error"
    assert "hint" in result
    assert "console.apify.com" in result["hint"]
