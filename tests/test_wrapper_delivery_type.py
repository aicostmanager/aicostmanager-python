import types

from aicostmanager import OpenAIChatWrapper


def test_wrapper_forwards_delivery_type(monkeypatch):
    captured = {}

    class DummyIniManager:
        def get_option(self, section, option, fallback=None):
            return fallback

    class StubTracker:
        def __init__(self, *args, **kwargs):
            captured["delivery_type"] = kwargs.get("delivery_type")
            self.ini_manager = DummyIniManager()

        def track(self, *args, **kwargs):
            pass

        async def track_async(self, *args, **kwargs):
            pass

        def close(self):
            pass

    monkeypatch.setattr("aicostmanager.wrappers.Tracker", StubTracker)

    client = types.SimpleNamespace()
    wrapper = OpenAIChatWrapper(client, delivery_type="PERSISTENT_QUEUE")
    assert captured["delivery_type"] == "PERSISTENT_QUEUE"
    wrapper.close()
