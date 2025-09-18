import os

import pytest

from aicostmanager.wrappers import (
    AnthropicWrapper,
    BedrockWrapper,
    GeminiWrapper,
    OpenAIChatWrapper,
    OpenAIResponsesWrapper,
)


def _require_env(var: str) -> None:
    if not os.getenv(var):
        pytest.skip(f"{var} not set")


def _call_or_skip(fn, msg: str) -> None:
    try:
        fn()
    except Exception as exc:  # pragma: no cover - best effort
        pytest.skip(f"{msg} failed: {exc}")


def _setup_capture(wrapper):
    calls = []
    orig = wrapper._tracker.delivery.enqueue

    def capture(payload):
        calls.append(payload)
        return orig(payload)

    wrapper._tracker.delivery.enqueue = capture
    return calls


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_openai_chat_real():
    openai = pytest.importorskip("openai")
    _require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_TEST_MODEL", "gpt-3.5-turbo")
    client = openai.OpenAI()
    wrapper = OpenAIChatWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
        )

    _call_or_skip(non_stream, "openai chat non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"openai::{model}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "openai chat non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"openai::{model}"
    calls.clear()

    def stream():
        stream = wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            stream_options={"include_usage": True},
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "openai chat stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"openai::{model}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "openai chat stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"openai::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_openai_responses_real():
    openai = pytest.importorskip("openai")
    _require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_TEST_MODEL", "gpt-3.5-turbo")
    client = openai.OpenAI()
    wrapper = OpenAIResponsesWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.responses.create(
            model=model,
            input="hi",
        )

    _call_or_skip(non_stream, "openai responses non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"openai::{model}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "openai responses non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"openai::{model}"
    calls.clear()

    def stream():
        stream = wrapper.responses.create(
            model=model,
            input="hi",
            stream=True,
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "openai responses stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"openai::{model}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "openai responses stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"openai::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_anthropic_real():
    anthropic = pytest.importorskip("anthropic")
    _require_env("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    client = anthropic.Anthropic()
    wrapper = AnthropicWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.messages.create(
            model=model,
            max_tokens=32,
            messages=[{"role": "user", "content": "hi"}],
        )

    _call_or_skip(non_stream, "anthropic non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"anthropic::{model}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "anthropic non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"anthropic::{model}"
    calls.clear()

    def stream():
        stream = wrapper.messages.create(
            model=model,
            max_tokens=32,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "anthropic stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"anthropic::{model}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "anthropic stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"anthropic::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_gemini_real():
    genai = pytest.importorskip("google.genai")
    _require_env("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    wrapper = GeminiWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.models.generate_content(
            model=model,
            contents="hi",
        )

    _call_or_skip(non_stream, "gemini non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"google::{model}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "gemini non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"google::{model}"
    calls.clear()

    def stream():
        stream = wrapper.models.generate_content_stream(
            model=model,
            contents=["hi"],
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "gemini stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"google::{model}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "gemini stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"google::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_bedrock_real():
    boto3 = pytest.importorskip("boto3")
    if not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
        pytest.skip("AWS credentials not set")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=aws_region)
    wrapper = BedrockWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

    def non_stream():
        wrapper.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            inferenceConfig={"maxTokens": 32},
        )

    _call_or_skip(non_stream, "bedrock non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"amazon-bedrock::{model_id}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "bedrock non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"amazon-bedrock::{model_id}"
    calls.clear()

    def stream():
        response = wrapper.converse_stream(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            inferenceConfig={"maxTokens": 32},
        )
        for _ in response["stream"]:
            pass

    _call_or_skip(stream, "bedrock stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"amazon-bedrock::{model_id}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "bedrock stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"amazon-bedrock::{model_id}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_xai_real():
    openai = pytest.importorskip("openai")
    _require_env("GROK_API_KEY")
    model = os.getenv("XAI_MODEL", "grok-3-mini")
    client = openai.OpenAI(
        api_key=os.environ["GROK_API_KEY"], base_url="https://api.x.ai/v1"
    )
    wrapper = OpenAIChatWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
        )

    _call_or_skip(non_stream, "xai non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"xai::{model}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "xai non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"xai::{model}"
    calls.clear()

    def stream():
        stream = wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            stream_options={"include_usage": True},
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "xai stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"xai::{model}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "xai stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"xai::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_fireworks_real():
    openai = pytest.importorskip("openai")
    _require_env("FIREWORKS_API_KEY")
    model = os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/deepseek-r1")
    client = openai.OpenAI(
        api_key=os.environ["FIREWORKS_API_KEY"],
        base_url="https://api.fireworks.ai/inference/v1",
    )
    wrapper = OpenAIChatWrapper(
        client,
        customer_key="cck1",
        context={"ctx": "v1"},
    )
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
        )

    _call_or_skip(non_stream, "fireworks non-stream")
    assert calls
    assert calls[-1]["service_key"] == f"fireworks-ai::{model}"
    assert calls[-1]["customer_key"] == "cck1"
    assert calls[-1]["context"] == {"ctx": "v1"}
    calls.clear()

    wrapper.customer_key = "cck2"
    _call_or_skip(non_stream, "fireworks non-stream updated")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"fireworks-ai::{model}"
    calls.clear()

    def stream():
        stream = wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            stream_options={"include_usage": True},
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "fireworks stream")
    assert calls and calls[-1]["customer_key"] == "cck2"
    assert calls[-1]["context"] == {"ctx": "v1"}
    assert calls[-1]["service_key"] == f"fireworks-ai::{model}"
    calls.clear()

    wrapper.customer_key = "cck3"
    wrapper.context = {"ctx": "v2"}
    _call_or_skip(stream, "fireworks stream updated")
    assert calls and calls[-1]["customer_key"] == "cck3"
    assert calls[-1]["context"] == {"ctx": "v2"}
    assert calls[-1]["service_key"] == f"fireworks-ai::{model}"
