import sys
import types


# Provide a minimal requests.Session stub so CostManagerClient can be imported
class _DummyReqSession:
    def __init__(self):
        self.headers = {}

    def request(self, *a, **k):
        raise NotImplementedError


sys.modules.setdefault("requests", types.SimpleNamespace(Session=_DummyReqSession))
sys.modules.setdefault(
    "jwt",
    types.SimpleNamespace(decode=lambda *a, **k: {}, encode=lambda *a, **k: ""),
)


class _DummyAttempt:
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.parent._success = True
            return False
        self.failed = True
        self.exception = exc
        return True


class _DummyRetrying:
    def __init__(self, stop=None, wait=None, reraise=False):
        self.attempts = getattr(stop, "attempts", 1)
        self._success = False

    def __iter__(self):
        last_exc = None
        for _ in range(self.attempts):
            attempt = _DummyAttempt(self)
            yield attempt
            if self._success:
                last_exc = None
                break
            last_exc = getattr(attempt, "exception", None)
        if last_exc:
            raise last_exc


class _StopAfterAttempt:
    def __init__(self, attempts):
        self.attempts = attempts


def _wait_exponential_jitter(**kwargs):
    return None


sys.modules.setdefault(
    "tenacity",
    types.SimpleNamespace(
        Retrying=_DummyRetrying,
        stop_after_attempt=_StopAfterAttempt,
        wait_exponential_jitter=_wait_exponential_jitter,
    ),
)

from aicostmanager.client import CostManagerClient
from aicostmanager.delivery import ResilientDelivery, get_global_delivery


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class DummySession:
    def __init__(self, responses=None):
        self.calls = []
        self.headers = {}
        self._responses = responses or [DummyResponse()]

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        resp = self._responses.pop(0)
        return resp


class DummyAsyncResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return {}


class DummyAsyncSession:
    def __init__(self, responses=None):
        self.calls = []
        self.headers = {}
        self._responses = responses or [DummyAsyncResponse()]

    async def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        resp = self._responses.pop(0)
        return resp

    async def aclose(self):
        return None


def reset_global():
    # helper to clear global between tests
    from aicostmanager import delivery as mod

    mod._global_delivery = None


def test_delivery_batches(monkeypatch):
    reset_global()
    sess = DummySession()
    client = CostManagerClient(aicm_api_key="sk-test", session=sess)
    delivery = get_global_delivery(client, queue_size=10)

    delivery.deliver({"usage_records": [{"id": 1}]})
    delivery.deliver({"usage_records": [{"id": 2}]})

    # wait for processing
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 1
    assert sess.calls[0][1]["usage_records"] == [{"id": 1}, {"id": 2}]


def test_delivery_retries_success(monkeypatch):
    reset_global()
    responses = [DummyResponse(500), DummyResponse(500), DummyResponse(200)]
    sess = DummySession(responses)
    delivery = ResilientDelivery(sess, "http://x", timeout=0.01)
    delivery.start()
    delivery.deliver({"usage_records": [{}]})
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 3
    info = delivery.get_health_info()
    assert info["total_sent"] == 1
    assert info["total_failed"] == 0


def test_delivery_retries_failure(monkeypatch):
    reset_global()
    responses = [DummyResponse(500), DummyResponse(500)]
    sess = DummySession(responses)
    delivery = ResilientDelivery(sess, "http://x", max_retries=2, timeout=0.01)
    delivery.start()
    delivery.deliver({"usage_records": [{}]})
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 2
    info = delivery.get_health_info()
    assert info["total_sent"] == 0
    assert info["total_failed"] == 1


def test_async_delivery_retries_success(monkeypatch):
    reset_global()
    responses = [
        DummyAsyncResponse(500),
        DummyAsyncResponse(500),
        DummyAsyncResponse(200),
    ]
    sess = DummyAsyncSession(responses)
    delivery = ResilientDelivery(sess, "http://x", timeout=0.01, async_mode=True)
    delivery.start()
    delivery.deliver({"usage_records": [{}]})
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 3
    info = delivery.get_health_info()
    assert info["total_sent"] == 1
    assert info["total_failed"] == 0


def test_global_singleton(monkeypatch):
    reset_global()
    sess = DummySession()
    client1 = CostManagerClient(aicm_api_key="sk-test", session=sess)
    d1 = get_global_delivery(client1)
    d2 = get_global_delivery(client1)
    assert d1 is d2
    d1.stop()


def test_global_restart(monkeypatch):
    reset_global()
    sess = DummySession()
    client = CostManagerClient(aicm_api_key="sk-test", session=sess)
    delivery = get_global_delivery(client, queue_size=10)
    delivery.stop()

    # Stopped delivery should restart on subsequent retrieval
    restarted = get_global_delivery(client, queue_size=10)
    restarted.deliver({"usage_records": [{}]})
    restarted._queue.join()
    restarted.stop()

    assert len(sess.calls) == 1


def test_delivery_uses_api_root(monkeypatch):
    reset_global()
    sess = DummySession()
    client = CostManagerClient(
        aicm_api_key="sk-test",
        aicm_api_base="http://base",
        aicm_api_url="/api",
        session=sess,
    )
    delivery = get_global_delivery(client, queue_size=10)

    delivery.deliver({"usage_records": [{}]})
    delivery._queue.join()
    delivery.stop()

    assert sess.calls[0][0] == "http://base/api/track-usage"


def test_registers_after_fork(monkeypatch):
    reset_global()
    calls: list[tuple[object, object]] = []

    def fake_register(obj, fn):
        calls.append((obj, fn))

    monkeypatch.setattr("multiprocessing.util.register_after_fork", fake_register)

    sess = DummySession()
    client = CostManagerClient(aicm_api_key="sk-test", session=sess)

    get_global_delivery(client)
    # Subsequent calls shouldn't register again
    get_global_delivery(client)

    assert len(calls) == 1
