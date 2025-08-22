import os
import pytest

from aicostmanager.wrappers import (
    OpenAIChatWrapper,
    OpenAIResponsesWrapper,
    AnthropicWrapper,
    GeminiWrapper,
    BedrockWrapper,
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
    wrapper = OpenAIChatWrapper(client)
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
        )

    _call_or_skip(non_stream, "openai chat non-stream")
    assert calls and calls[-1]["api_id"] == "openai_chat"
    assert calls[-1]["service_key"] == f"openai::{model}"
    calls.clear()

    def stream():
        stream = wrapper.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "openai chat stream")
    assert calls and calls[-1]["api_id"] == "openai_chat"
    assert calls[-1]["service_key"] == f"openai::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_openai_responses_real():
    openai = pytest.importorskip("openai")
    _require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_TEST_MODEL", "gpt-3.5-turbo")
    client = openai.OpenAI()
    wrapper = OpenAIResponsesWrapper(client)
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.responses.create(
            model=model,
            input="hi",
        )

    _call_or_skip(non_stream, "openai responses non-stream")
    assert calls and calls[-1]["api_id"] == "openai_responses"
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
    assert calls and calls[-1]["api_id"] == "openai_responses"
    assert calls[-1]["service_key"] == f"openai::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_anthropic_real():
    anthropic = pytest.importorskip("anthropic")
    _require_env("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    client = anthropic.Anthropic()
    wrapper = AnthropicWrapper(client)
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.messages.create(
            model=model,
            max_tokens=32,
            messages=[{"role": "user", "content": "hi"}],
        )

    _call_or_skip(non_stream, "anthropic non-stream")
    assert calls and calls[-1]["api_id"] == "anthropic"
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
    assert calls and calls[-1]["api_id"] == "anthropic"
    assert calls[-1]["service_key"] == f"anthropic::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_gemini_real():
    genai = pytest.importorskip("google.generativeai")
    _require_env("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    wrapper = GeminiWrapper(client)
    calls = _setup_capture(wrapper)

    def non_stream():
        wrapper.models.generate_content(
            model=model,
            contents="hi",
        )

    _call_or_skip(non_stream, "gemini non-stream")
    assert calls and calls[-1]["api_id"] == "gemini"
    assert calls[-1]["service_key"] == f"google::{model}"
    calls.clear()

    def stream():
        stream = wrapper.models.generate_content(
            model=model,
            contents="hi",
            stream=True,
        )
        for _ in stream:
            pass

    _call_or_skip(stream, "gemini stream")
    assert calls and calls[-1]["api_id"] == "gemini"
    assert calls[-1]["service_key"] == f"google::{model}"


@pytest.mark.skipif("CI" in os.environ, reason="avoid real API calls in CI")
def test_bedrock_real():
    boto3 = pytest.importorskip("boto3")
    if not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
        pytest.skip("AWS credentials not set")
    client = boto3.client("bedrock-runtime")
    wrapper = BedrockWrapper(client)
    calls = _setup_capture(wrapper)
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-v2")
    payload = '{"prompt":"hi","max_tokens_to_sample":32}'

    def non_stream():
        wrapper.invoke_model(modelId=model_id, body=payload)

    _call_or_skip(non_stream, "bedrock non-stream")
    assert calls and calls[-1]["api_id"] == "bedrock"
    assert calls[-1]["service_key"] == f"amazon-bedrock::{model_id}"
    calls.clear()

    def stream():
        stream = wrapper.invoke_model_with_response_stream(modelId=model_id, body=payload)
        for _ in stream.get("body", []):
            pass

    _call_or_skip(stream, "bedrock stream")
    assert calls and calls[-1]["api_id"] == "bedrock"
    assert calls[-1]["service_key"] == f"amazon-bedrock::{model_id}"
