import logging
import queue
import sys
import threading
import time
import types

import pytest


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
        self.parent._last_exc = exc
        return True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return self.__exit__(exc_type, exc, tb)


class _DummyRetrying:
    def __init__(self, stop=None, wait=None, reraise=False):
        self.attempts = getattr(stop, "attempts", 1)
        self._success = False
        self._last_exc = None
        self._counter = 0

    def __iter__(self):
        self._counter = 0
        self._success = False
        self._last_exc = None
        return self

    def __next__(self):
        if self._success:
            raise StopIteration
        if self._counter >= self.attempts:
            if self._last_exc:
                raise self._last_exc
            raise StopIteration
        self._counter += 1
        return _DummyAttempt(self)

    def __aiter__(self):
        self._counter = 0
        self._success = False
        self._last_exc = None
        return self

    async def __anext__(self):
        if self._success:
            raise StopAsyncIteration
        if self._counter >= self.attempts:
            if self._last_exc:
                raise self._last_exc
            raise StopAsyncIteration
        self._counter += 1
        return _DummyAttempt(self)


class _StopAfterAttempt:
    def __init__(self, attempts):
        self.attempts = attempts


def _wait_exponential_jitter(**kwargs):
    return None


sys.modules.setdefault(
    "tenacity",
    types.SimpleNamespace(
        Retrying=_DummyRetrying,
        AsyncRetrying=_DummyRetrying,
        stop_after_attempt=_StopAfterAttempt,
        wait_exponential_jitter=_wait_exponential_jitter,
    ),
)


class _DummyHttpxAsyncClient:
    def __init__(self, *a, **k):
        self.headers = {}

    async def post(self, *a, **k):
        return DummyAsyncResponse()

    async def aclose(self):
        return None


sys.modules.setdefault(
    "httpx", types.SimpleNamespace(AsyncClient=_DummyHttpxAsyncClient)
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
        if self._responses:
            resp = self._responses.pop(0)
        else:
            # Provide a default response if no more responses are available
            resp = DummyResponse()
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


def test_delivery_batches(monkeypatch, tmp_path):
    reset_global()
    sess = DummySession()
    ini_path = tmp_path / "AICM.INI"
    client = CostManagerClient(
        aicm_api_key="sk-test", session=sess, aicm_ini_path=str(ini_path)
    )
    delivery = get_global_delivery(
        client, queue_size=10, batch_interval=0.01, max_batch_size=10
    )

    delivery.deliver({"usage_records": [{"id": 1}]})
    delivery.deliver({"usage_records": [{"id": 2}]})

    # wait for processing
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 1
    assert sess.calls[0][1]["usage_records"] == [{"id": 1}, {"id": 2}]


def test_delivery_time_window():
    sess = DummySession()
    delivery = ResilientDelivery(
        sess, "http://x", batch_interval=0.01, max_batch_size=10
    )
    delivery.start()
    delivery.deliver({"usage_records": [{"id": 1}]})
    time.sleep(0.02)
    delivery.deliver({"usage_records": [{"id": 2}]})
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 2


def test_delivery_batch_size_limit():
    sess = DummySession()
    delivery = ResilientDelivery(
        sess, "http://x", batch_interval=0.01, max_batch_size=2
    )
    delivery.start()
    delivery.deliver({"usage_records": [{"id": 1}]})
    delivery.deliver({"usage_records": [{"id": 2}]})
    delivery.deliver({"usage_records": [{"id": 3}]})
    delivery._queue.join()
    delivery.stop()

    assert len(sess.calls) == 2
    assert len(sess.calls[0][1]["usage_records"]) == 2
    assert len(sess.calls[1][1]["usage_records"]) == 1


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


def test_global_singleton(monkeypatch, tmp_path):
    reset_global()
    sess = DummySession()
    client1 = CostManagerClient(
        aicm_api_key="sk-test", session=sess, aicm_ini_path=str(tmp_path / "AICM.INI")
    )
    d1 = get_global_delivery(client1)
    d2 = get_global_delivery(client1)
    assert d1 is d2
    d1.stop()


def test_global_restart(monkeypatch, tmp_path):
    reset_global()
    sess = DummySession()
    client = CostManagerClient(
        aicm_api_key="sk-test", session=sess, aicm_ini_path=str(tmp_path / "AICM.INI")
    )
    delivery = get_global_delivery(client, queue_size=10)
    delivery.stop()

    # Stopped delivery should restart on subsequent retrieval
    restarted = get_global_delivery(client, queue_size=10)
    restarted.deliver({"usage_records": [{}]})
    restarted._queue.join()
    restarted.stop()

    assert len(sess.calls) == 1


def test_delivery_uses_api_root(monkeypatch, tmp_path):
    reset_global()
    sess = DummySession()
    client = CostManagerClient(
        aicm_api_key="sk-test",
        aicm_api_base="http://base",
        aicm_api_url="/api",
        session=sess,
        aicm_ini_path=str(tmp_path / "AICM.INI"),
    )
    delivery = get_global_delivery(client, queue_size=10)

    delivery.deliver({"usage_records": [{}]})
    delivery._queue.join()
    delivery.stop()

    assert sess.calls[0][0] == "http://base/api/track-usage"


def test_registers_after_fork(monkeypatch, tmp_path):
    reset_global()
    calls: list[tuple[object, object]] = []

    def fake_register(obj, fn):
        calls.append((obj, fn))

    monkeypatch.setattr("multiprocessing.util.register_after_fork", fake_register)

    sess = DummySession()
    client = CostManagerClient(
        aicm_api_key="sk-test", session=sess, aicm_ini_path=str(tmp_path / "AICM.INI")
    )

    get_global_delivery(client)
    # Subsequent calls shouldn't register again
    get_global_delivery(client)

    assert len(calls) == 1


def test_queue_full_raise(caplog):
    caplog.set_level(logging.WARNING)
    sess = DummySession()
    delivery = ResilientDelivery(sess, "http://x", queue_size=1, on_full="raise")
    delivery.deliver({"usage_records": [{}]})
    with pytest.raises(queue.Full):
        delivery.deliver({"usage_records": [{}]})
    assert "Delivery queue full" in caplog.text


def test_queue_full_backpressure(caplog):
    caplog.set_level(logging.WARNING)
    sess = DummySession()
    delivery = ResilientDelivery(sess, "http://x", queue_size=1, on_full="backpressure")
    delivery.deliver({"usage_records": [{"id": 1}]})
    delivery.deliver({"usage_records": [{"id": 2}]})
    assert "Delivery queue full" in caplog.text
    assert delivery._queue.qsize() == 1
    item = delivery._queue.get_nowait()
    assert item["usage_records"][0]["id"] == 2
    delivery._queue.task_done()


def test_queue_full_block(caplog):
    caplog.set_level(logging.WARNING)
    sess = DummySession()
    delivery = ResilientDelivery(sess, "http://x", queue_size=1, on_full="block")
    delivery.deliver({"usage_records": [{"id": 1}]})
    done = threading.Event()

    def deliver_second():
        delivery.deliver({"usage_records": [{"id": 2}]})
        done.set()

    t = threading.Thread(target=deliver_second)
    t.start()
    time.sleep(0.1)
    assert not done.is_set()
    item = delivery._queue.get_nowait()
    delivery._queue.task_done()
    t.join(timeout=1)
    assert done.is_set()
    assert "Delivery queue full" in caplog.text
    item2 = delivery._queue.get_nowait()
    assert item2["usage_records"][0]["id"] == 2
    delivery._queue.task_done()
