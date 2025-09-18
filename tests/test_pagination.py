from aicostmanager.client import CostManagerClient
from aicostmanager.models import CustomerOut, PaginatedResponse, UsageEvent, UsageRollup


class DummyResponse:
    def __init__(self, data):
        self.status_code = 200
        self.ok = True
        self._data = data
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._data


def test_iter_usage_events(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = CostManagerClient()

    pages = [
        {
            "results": [
                {
                    "event_id": "e1",
                    "config_id": "c",
                    "timestamp": "t",
                    "response_id": "r",
                    "status": "done",
                }
            ],
            "next": client.api_root + "/usage/events/?offset=1",
        },
        {
            "results": [
                {
                    "event_id": "e2",
                    "config_id": "c",
                    "timestamp": "t",
                    "response_id": "r",
                    "status": "done",
                }
            ],
            "next": None,
        },
    ]

    def requester(self, method, url, **kwargs):
        return DummyResponse(pages.pop(0))

    monkeypatch.setattr("requests.Session.request", requester)

    events = list(client.iter_usage_events())
    assert [e.event_id for e in events] == ["e1", "e2"]


def test_list_usage_events_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = CostManagerClient()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "event_id": "e1",
                "config_id": "c",
                "timestamp": "t",
                "response_id": "r",
                "status": "done",
            }
        ],
    }

    def requester(self, method, url, **kwargs):
        return DummyResponse(data)

    monkeypatch.setattr("requests.Session.request", requester)

    resp = client.list_usage_events_typed()
    assert isinstance(resp, PaginatedResponse)
    assert isinstance(resp.results[0], UsageEvent)


def test_list_usage_rollups_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = CostManagerClient()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "customer_key": "c1",
                "service_id": "svc",
                "date": "2024-01-01",
                "quantity": 1,
                "cost": 0.1,
            }
        ],
    }

    def requester(self, method, url, **kwargs):
        return DummyResponse(data)

    monkeypatch.setattr("requests.Session.request", requester)

    resp = client.list_usage_rollups_typed()
    assert isinstance(resp, PaginatedResponse)
    assert isinstance(resp.results[0], UsageRollup)


def test_list_customers_typed(monkeypatch):
    monkeypatch.setenv("AICM_API_KEY", "sk")
    client = CostManagerClient()

    data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "uuid": "u1",
                "customer_key": "c1",
                "name": "n",
                "phone": None,
                "email": None,
            }
        ],
    }

    def requester(self, method, url, **kwargs):
        return DummyResponse(data)

    monkeypatch.setattr("requests.Session.request", requester)

    resp = client.list_customers_typed()
    assert isinstance(resp, PaginatedResponse)
    assert isinstance(resp.results[0], CustomerOut)
