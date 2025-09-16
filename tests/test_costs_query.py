from aicostmanager import CostQueryManager
from aicostmanager.models import CostEventFilters, CostEventItem, CostEventsResponse


class DummyResponse:
    def __init__(self, data):
        self.status_code = 200
        self.ok = True
        self._data = data
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._data


def test_list_costs_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    manager = CostQueryManager()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "provider_id": "v1",
                "service_key": "s1",
                "cost_unit_id": "cu1",
                "quantity": "1",
                "cost_per_unit": "0.01",
                "cost": "0.01",
            }
        ],
    }

    captured = {}

    def requester(self, method, url, **kwargs):
        captured.update(kwargs.get("params", {}))
        return DummyResponse(data)

    monkeypatch.setattr("requests.Session.request", requester)

    filters = CostEventFilters(response_id="resp_123")
    resp = manager.list_costs_typed(filters)

    assert isinstance(resp, CostEventsResponse)
    assert isinstance(resp.results[0], CostEventItem)
    assert resp.results[0].provider_id == "v1"
    assert captured["response_id"] == "resp_123"


def test_iter_costs(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    manager = CostQueryManager()

    pages = [
        {
            "results": [
                {
                    "provider_id": "v1",
                    "service_key": "s1",
                    "cost_unit_id": "cu1",
                    "quantity": "1",
                    "cost_per_unit": "0.01",
                    "cost": "0.01",
                }
            ],
            "next": manager.client.api_root + "/costs/?offset=1",
        },
        {
            "results": [
                {
                    "provider_id": "v2",
                    "service_key": "s2",
                    "cost_unit_id": "cu2",
                    "quantity": "2",
                    "cost_per_unit": "0.02",
                    "cost": "0.04",
                }
            ],
            "next": None,
        },
    ]

    def requester(self, method, url, **kwargs):
        return DummyResponse(pages.pop(0))

    monkeypatch.setattr("requests.Session.request", requester)

    events = list(manager.iter_costs())
    assert [e.provider_id for e in events] == ["v1", "v2"]
    assert str(events[0].cost) == "0.01"


def test_list_costs_with_context_filters(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    manager = CostQueryManager()

    captured = {}

    def requester(self, method, url, **kwargs):
        captured.update(kwargs.get("params", {}))
        return DummyResponse(
            {"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr("requests.Session.request", requester)

    manager.list_costs({"context.environment": "prod"})
    assert captured["context.environment"] == "prod"
