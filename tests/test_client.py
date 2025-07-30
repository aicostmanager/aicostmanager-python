import configparser
import json
from typing import Any

import pytest
import requests

from aicostmanager.client import (
    APIRequestError,
    CostManagerClient,
    MissingConfiguration,
)
from aicostmanager.models import (
    ApiUsageRecord,
    ApiUsageRequest,
    CustomerFilters,
    CustomerIn,
    Period,
    RollupFilters,
    ThresholdType,
    UsageEventFilters,
    UsageLimitIn,
)


class DummyResponse:
    def __init__(self, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._content = json.dumps(data or {}).encode()
        self.headers = {"Content-Type": "application/json"}
        if headers:
            self.headers.update(headers)
        self.text = self._content.decode()

    def json(self):
        return json.loads(self._content)


def _patch(
    monkeypatch, method, path, data=None, status=200, headers=None, response_headers=None
):
    def requester(self, m, url, **kwargs):
        assert m == method
        assert url.endswith(path)
        assert self.headers["Authorization"].startswith("Bearer ")
        if headers:
            for k, v in headers.items():
                assert kwargs["headers"].get(k) == v
        return DummyResponse(status_code=status, data=data, headers=response_headers)

    monkeypatch.setattr("requests.Session.request", requester)


def test_missing_configuration(monkeypatch):
    monkeypatch.delenv("AICM_API_KEY", raising=False)
    with pytest.raises(MissingConfiguration):
        CostManagerClient()


def test_env_var_configuration(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    monkeypatch.setenv("AICM_INI_PATH", "/tmp/custom.ini")
    client = CostManagerClient()
    assert client.api_key == "sk-test"
    assert client.ini_path == "/tmp/custom.ini"


def test_default_ini_path(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    monkeypatch.delenv("AICM_INI_PATH", raising=False)
    client = CostManagerClient()
    assert client.ini_path.endswith(".config/aicostmanager/AICM.INI")


def test_methods(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    client = CostManagerClient()

    record = ApiUsageRecord(
        config_id="cfg", service_id="svc", timestamp="t", response_id="r", usage={}
    )
    specs = [
        (
            "GET",
            "/configs",
            client.get_configs,
            (),
            {},
            {"service_configs": [], "triggered_limits": {}},
        ),
        (
            "POST",
            "/track-usage",
            client.track_usage,
            (ApiUsageRequest(usage_records=[record]),),
            {},
            {"event_ids": [], "triggered_limits": {}},
            201,
        ),
        (
            "GET",
            "/usage/events/",
            client.list_usage_events,
            (),
            {"limit": 1},
            {"count": 0, "next": None, "previous": None, "results": []},
        ),
        (
            "GET",
            "/usage/event/evt/",
            client.get_usage_event,
            ("evt",),
            {},
            {
                "event_id": "evt",
                "config_id": "cfg",
                "timestamp": "t",
                "response_id": "r",
                "status": "done",
            },
        ),
        (
            "GET",
            "/usage/rollups/",
            client.list_usage_rollups,
            (),
            {},
            {"count": 0, "next": None, "previous": None, "results": []},
        ),
        (
            "GET",
            "/customers/",
            client.list_customers,
            (),
            {},
            {"count": 0, "next": None, "previous": None, "results": []},
        ),
        (
            "POST",
            "/customers/",
            client.create_customer,
            (CustomerIn(client_customer_key="c"),),
            {},
            {
                "uuid": "c1",
                "client_customer_key": "c",
                "name": None,
                "phone": None,
                "email": None,
            },
            201,
        ),
        (
            "GET",
            "/customers/cid/",
            client.get_customer,
            ("cid",),
            {},
            {
                "uuid": "cid",
                "client_customer_key": "c",
                "name": None,
                "phone": None,
                "email": None,
            },
        ),
        (
            "PUT",
            "/customers/cid/",
            client.update_customer,
            ("cid", CustomerIn(client_customer_key="c", name="y")),
            {},
            {
                "uuid": "cid",
                "client_customer_key": "c",
                "name": "y",
                "phone": None,
                "email": None,
            },
        ),
        ("DELETE", "/customers/cid/", client.delete_customer, ("cid",), {}, None, 204),
        ("GET", "/usage-limits/", client.list_usage_limits, (), {}, []),
        (
            "POST",
            "/usage-limits/",
            client.create_usage_limit,
            (
                UsageLimitIn(
                    threshold_type=ThresholdType.LIMIT, amount=1, period=Period.DAY
                ),
            ),
            {},
            {
                "uuid": "lim",
                "threshold_type": "limit",
                "amount": 1,
                "period": "day",
                "vendor": None,
                "service": None,
                "client": None,
                "notification_list": None,
                "active": True,
            },
            201,
        ),
        (
            "GET",
            "/usage-limits/lid/",
            client.get_usage_limit,
            ("lid",),
            {},
            {
                "uuid": "lid",
                "threshold_type": "limit",
                "amount": 1,
                "period": "day",
                "vendor": None,
                "service": None,
                "client": None,
                "notification_list": None,
                "active": True,
            },
        ),
        (
            "PUT",
            "/usage-limits/lid/",
            client.update_usage_limit,
            (
                "lid",
                UsageLimitIn(
                    threshold_type=ThresholdType.ALERT, amount=2, period=Period.MONTH
                ),
            ),
            {},
            {
                "uuid": "lid",
                "threshold_type": "alert",
                "amount": 2,
                "period": "month",
                "vendor": None,
                "service": None,
                "client": None,
                "notification_list": None,
                "active": True,
            },
        ),
        (
            "DELETE",
            "/usage-limits/lid/",
            client.delete_usage_limit,
            ("lid",),
            {},
            None,
            204,
        ),
        ("GET", "/vendors/", client.list_vendors, (), {}, []),
        (
            "GET",
            "/services/",
            client.list_vendor_services,
            (),
            {"vendor": "openai"},
            [],
        ),
        (
            "GET",
            "/service-costs/",
            client.list_service_costs,
            (),
            {"vendor": "openai", "service": "gpt-4"},
            [],
        ),
        (
            "GET",
            "/openapi.json",
            client.get_openapi_schema,
            (),
            {},
            {"openapi": "3.1.0"},
        ),
    ]

    for spec in specs:
        method, path, func, args, kwargs, data, *rest = spec
        status = rest[0] if rest else 200
        _patch(monkeypatch, method, client.api_root + path, data, status)
        result = func(*args, **kwargs)
        from pydantic import BaseModel

        if data is None:
            assert result is None
        elif isinstance(result, BaseModel):
            assert isinstance(result, BaseModel)
        elif isinstance(data, list):
            assert isinstance(result, list)
        else:
            assert isinstance(result, dict)


def test_get_configs_etag(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    client = CostManagerClient()

    def requester_first(self, method, url, **kwargs):
        assert method == "GET" and url.endswith("/configs")
        return DummyResponse(
            data={"service_configs": [], "triggered_limits": {}},
            headers={"ETag": "tag1"},
        )

    def requester_second(self, method, url, **kwargs):
        assert kwargs.get("headers", {}).get("If-None-Match") == "tag1"
        return DummyResponse(status_code=304, headers={"ETag": "tag1"})

    monkeypatch.setattr("requests.Session.request", requester_first)
    result = client.get_configs()
    assert result is not None
    assert client.configs_etag == "tag1"

    monkeypatch.setattr("requests.Session.request", requester_second)
    result = client.get_configs(etag=client.configs_etag)
    assert result is None


def test_error_response(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")

    def requester(self, method, url, **kwargs):
        return DummyResponse(
            status_code=400,
            data={"error": "bad", "message": "oops", "timestamp": "now"},
        )

    monkeypatch.setattr("requests.Session.request", requester)
    client = CostManagerClient()
    with pytest.raises(APIRequestError) as exc:
        client.get_configs()
    err = exc.value
    assert err.status_code == 400
    assert err.error == "bad"
    assert err.message == "oops"


def test_custom_session_and_proxies(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    session = requests.Session()
    client = CostManagerClient(
        session=session, proxies={"http": "proxy"}, headers={"X-Test": "1"}
    )
    assert session.proxies["http"] == "proxy"
    assert client.session.headers["X-Test"] == "1"


def test_filter_objects(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    client = CostManagerClient()

    captured: dict[str, Any] = {}

    def requester(self, method, url, **kwargs):
        captured.update(kwargs)
        return DummyResponse(data={})

    monkeypatch.setattr("requests.Session.request", requester)

    filters = UsageEventFilters(client_customer_key="c1")
    client.list_usage_events(filters)
    assert captured.get("params") == {"client_customer_key": "c1"}

    filters = RollupFilters(limit=10, offset=5)
    client.list_usage_rollups(filters)
    assert captured.get("params") == {"limit": 10, "offset": 5, "granularity": "daily"}

    filters = CustomerFilters(name="n", limit=2)
    client.list_customers(filters)
    assert captured.get("params") == {"name": "n", "limit": 2}

    client.list_vendor_services("openai")
    assert captured.get("params") == {"vendor": "openai"}

    client.list_service_costs("openai", "gpt-4")
    assert captured.get("params") == {"vendor": "openai", "service": "gpt-4"}


def test_track_usage_persists_triggered_limits(monkeypatch, tmp_path):
    monkeypatch.setenv("AICM_API_KEY", "sk-test")
    ini = tmp_path / "AICM.INI"
    client = CostManagerClient(aicm_api_key="sk-test", aicm_ini_path=str(ini))

    def fake_request(self, method, path, **kwargs):
        assert method == "POST" and path == "/track-usage"
        return {
            "event_ids": [],
            "triggered_limits": {"encrypted_payload": "tok", "public_key": "pk"},
        }

    monkeypatch.setattr(CostManagerClient, "_request", fake_request)

    client.track_usage({"usage_records": []})

    cp = configparser.ConfigParser()
    cp.read(ini)
    assert cp.has_section("triggered_limits")
    assert json.loads(cp["triggered_limits"]["payload"]) == {
        "encrypted_payload": "tok",
        "public_key": "pk",
    }
