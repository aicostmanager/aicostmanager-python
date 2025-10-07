import importlib.util
import sys
import types
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "aicostmanager"

# ``test_llm_wrappers`` loads the ``wrappers`` module without importing the
# entire package and stubs out ``Tracker``.  Previously this test modified
# ``sys.modules`` globally which leaked into subsequent tests and caused
# ``ImportError: cannot import name 'Tracker'`` when other tests tried to import
# the real package.  We capture any existing modules and restore them once the
# wrappers have been imported so that later tests see the normal package
# structure.
_ORIGINAL_MODULES = {
    name: sys.modules.get(name)
    for name in [
        "aicostmanager",
        "aicostmanager.tracker",
        "aicostmanager.usage_utils",
        "aicostmanager.wrappers",
    ]
}

# Create a minimal package with a stub ``Tracker`` implementation so that the
# wrappers module can be imported in isolation.
pkg = types.ModuleType("aicostmanager")
pkg.__path__ = [str(PACKAGE_DIR)]
sys.modules["aicostmanager"] = pkg

tracker_stub = types.ModuleType("aicostmanager.tracker")


class Tracker:  # pragma: no cover - stub for tests
    def __init__(self, *args, **kwargs):
        pass

    def track(self, *args, **kwargs):
        pass

    async def track_async(self, *args, **kwargs):
        pass

    def close(self):
        pass


tracker_stub.Tracker = Tracker
sys.modules["aicostmanager.tracker"] = tracker_stub

# Load ``usage_utils`` and ``wrappers`` from the source tree
spec_usage = importlib.util.spec_from_file_location(
    "aicostmanager.usage_utils", PACKAGE_DIR / "usage_utils.py"
)
usage_utils = importlib.util.module_from_spec(spec_usage)
sys.modules["aicostmanager.usage_utils"] = usage_utils
spec_usage.loader.exec_module(usage_utils)

spec = importlib.util.spec_from_file_location(
    "aicostmanager.wrappers", PACKAGE_DIR / "wrappers.py"
)
wrappers = importlib.util.module_from_spec(spec)
sys.modules["aicostmanager.wrappers"] = wrappers
spec.loader.exec_module(wrappers)

OpenAIChatWrapper = wrappers.OpenAIChatWrapper
OpenAIResponsesWrapper = wrappers.OpenAIResponsesWrapper
AnthropicWrapper = wrappers.AnthropicWrapper
GeminiWrapper = wrappers.GeminiWrapper
BedrockWrapper = wrappers.BedrockWrapper
FireworksWrapper = wrappers.FireworksWrapper

# Restore any modules that were present before importing the stubs so that
# other tests importing :mod:`aicostmanager` are not affected by the temporary
# replacements above.
for name, module in _ORIGINAL_MODULES.items():
    if module is not None:
        sys.modules[name] = module
    else:
        sys.modules.pop(name, None)


class DummyIniManager:
    def get_option(self, section, option, fallback=None):
        return fallback


class DummyTracker:
    def __init__(self):
        self.calls = []
        self.ini_manager = DummyIniManager()

    def track(self, service_key, usage, **kwargs):
        self.calls.append((service_key, usage))

    async def track_async(self, service_key, usage, **kwargs):
        self.calls.append((service_key, usage))

    def close(self):
        pass


def _stream_chunk():
    yield types.SimpleNamespace(
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    )
    yield types.SimpleNamespace(data="done")


def make_openai_chat_client(base_url: str | None = None):
    class Completions:
        def create(self, *args, **kwargs):
            if kwargs.get("stream"):
                return _stream_chunk()
            return types.SimpleNamespace(
                id="resp-1",
                model=kwargs.get("model"),
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            )

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    client = Client()
    if base_url:
        client.base_url = base_url
    return client


def make_openai_responses_client():
    class Responses:
        def create(self, *args, **kwargs):
            return types.SimpleNamespace(
                id="resp-2",
                model=kwargs.get("model"),
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            )

    class Client:
        responses = Responses()

    return Client()


def make_anthropic_client():
    class Messages:
        def create(self, *args, **kwargs):
            return types.SimpleNamespace(
                id="resp-3",
                usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            )

    class Client:
        messages = Messages()

    return Client()


def make_gemini_client():
    class Models:
        def generate_content(self, *args, **kwargs):
            return types.SimpleNamespace(
                model=kwargs.get("model"),
                usage_metadata={
                    "promptTokenCount": 1,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 3,
                },
            )

    class Client:
        models = Models()

    return Client()


def make_bedrock_client():
    class Client:
        def invoke_model(self, *args, **kwargs):
            return {
                "usage": {
                    "inputTokens": 1,
                    "outputTokens": 2,
                    "totalTokens": 3,
                }
            }

    return Client()


def make_fireworks_client():
    class Completions:
        def create(self, *args, **kwargs):
            return types.SimpleNamespace(
                id="resp-6",
                model=kwargs.get("model"),
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            )

    class Client:
        completions = Completions()

    return Client()


def test_wrappers_track_non_streaming():
    tracker = DummyTracker()
    cases = [
        (
            OpenAIChatWrapper,
            make_openai_chat_client(),
            "chat.completions.create",
            {"model": "gpt-4"},
            "openai::gpt-4",
        ),
        (
            OpenAIResponsesWrapper,
            make_openai_responses_client(),
            "responses.create",
            {"model": "gpt-4"},
            "openai::gpt-4",
        ),
        (
            AnthropicWrapper,
            make_anthropic_client(),
            "messages.create",
            {"model": "claude-3"},
            "anthropic::claude-3",
        ),
        (
            GeminiWrapper,
            make_gemini_client(),
            "models.generate_content",
            {"model": "models/gemini"},
            "google::models/gemini",
        ),
        (
            BedrockWrapper,
            make_bedrock_client(),
            "invoke_model",
            {"modelId": "anthropic.claude-v2"},
            "amazon-bedrock::anthropic.claude-v2",
        ),
        (
            FireworksWrapper,
            make_fireworks_client(),
            "completions.create",
            {"model": "accounts/fireworks/models/deepseek-r1"},
            "fireworks-ai::accounts/fireworks/models/deepseek-r1",
        ),
    ]
    for wrapper_cls, client, call_path, kwargs, expected in cases:
        tracker.calls.clear()
        wrapper = wrapper_cls(client, tracker=tracker)
        obj = wrapper
        for attr in call_path.split("."):
            obj = getattr(obj, attr)
        obj(**kwargs)
        assert tracker.calls and tracker.calls[0][0] == expected


def test_openai_chat_wrapper_streaming_tracks_once():
    tracker = DummyTracker()
    client = make_openai_chat_client()
    wrapper = OpenAIChatWrapper(client, tracker=tracker)
    stream = wrapper.chat.completions.create(model="gpt-4", stream=True)
    list(stream)
    assert tracker.calls and tracker.calls[0][0] == "openai::gpt-4"


def test_openai_chat_vendor_detection():
    tracker = DummyTracker()
    fw_client = make_openai_chat_client("https://api.fireworks.ai")
    wrapper_fw = OpenAIChatWrapper(fw_client, tracker=tracker)
    wrapper_fw.chat.completions.create(model="m1")
    assert tracker.calls[0][0] == "fireworks-ai::m1"

    tracker.calls.clear()
    x_client = make_openai_chat_client("https://api.x.ai")
    wrapper_x = OpenAIChatWrapper(x_client, tracker=tracker)
    wrapper_x.chat.completions.create(model="m2")
    assert tracker.calls[0][0] == "xai::m2"
