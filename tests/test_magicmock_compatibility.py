"""Test MagicMock compatibility with LLM wrappers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from aicostmanager.wrappers import OpenAIChatWrapper


class DummyIniManager:
    def get_option(self, section, option, fallback=None):
        return fallback


class DummyTracker:
    calls: list

    def __init__(self):
        self.calls = []
        self.ini_manager = DummyIniManager()

    def track(self, api_id, service_key, usage, response_id=None):
        self.calls.append((api_id, service_key, usage, response_id))
        return {"result": {"ok": True}}

    async def track_async(self, api_id, service_key, usage, response_id=None):
        self.calls.append((api_id, service_key, usage, response_id))
        return {"result": {"ok": True}}

    def close(self):
        pass


class TestMagicMockCompatibility:
    """Test that wrappers work correctly with MagicMock objects."""

    def test_openai_chat_wrapper_magicmock_attribute_access(self):
        """Test that OpenAIChatWrapper preserves attribute access with MagicMock."""
        # Create a MagicMock like users would in tests
        mock_client = MagicMock()

        # Set up the mock structure like in typical OpenAI client tests
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Test response"

        def mock_stream():
            yield mock_chunk

        mock_client.chat.completions.create.return_value = mock_stream()

        # This should work without AttributeError
        wrapper = OpenAIChatWrapper(mock_client, tracker=DummyTracker())

        # Test nested attribute access that was previously failing
        assert hasattr(wrapper, "chat"), "wrapper.chat should be accessible"
        assert hasattr(wrapper.chat, "completions"), (
            "wrapper.chat.completions should be accessible"
        )
        assert hasattr(wrapper.chat.completions, "create"), (
            "wrapper.chat.completions.create should be accessible"
        )

        # Test that the method is callable
        result = wrapper.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": "test"}]
        )
        assert result is not None, (
            "wrapper.chat.completions.create() should be callable"
        )

    def test_openai_chat_wrapper_magicmock_non_streaming(self):
        """Test that OpenAIChatWrapper works with MagicMock for non-streaming responses."""
        mock_client = MagicMock()

        # Set up non-streaming mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_response.id = "test-response-123"
        mock_response.model = "gpt-4"

        mock_client.chat.completions.create.return_value = mock_response

        wrapper = OpenAIChatWrapper(mock_client, tracker=DummyTracker())

        # Test non-streaming call
        response = wrapper.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Say hello"}],
        )

        # Verify the response
        assert response.choices[0].message.content == "Hello world"
        assert response.id == "test-response-123"
        assert response.model == "gpt-4"

    def test_openai_chat_wrapper_regular_mock_still_works(self):
        """Test that the MagicMock fix doesn't break regular mock structures."""

        # Create a proper mock structure like in existing tests
        class Completions:
            def create(self, *args, **kwargs):
                return {
                    "id": "test-123",
                    "model": kwargs.get("model"),
                    "usage": {"total_tokens": 10},
                }

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        client = Client()
        wrapper = OpenAIChatWrapper(client, tracker=DummyTracker())

        # This should still work as before
        result = wrapper.chat.completions.create(model="gpt-4", messages=[])
        assert result["model"] == "gpt-4"
        assert result["id"] == "test-123"
        assert "usage" in result

    def test_openai_chat_wrapper_mock_vs_magicmock(self):
        """Test that both Mock and MagicMock work correctly."""
        # Test with regular Mock
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = {"id": "mock-test"}

        wrapper_mock = OpenAIChatWrapper(mock_client, tracker=DummyTracker())
        result_mock = wrapper_mock.chat.completions.create(model="gpt-3.5-turbo")
        assert result_mock["id"] == "mock-test"

        # Test with MagicMock
        magicmock_client = MagicMock()
        magicmock_client.chat.completions.create.return_value = {"id": "magicmock-test"}

        wrapper_magicmock = OpenAIChatWrapper(magicmock_client, tracker=DummyTracker())
        result_magicmock = wrapper_magicmock.chat.completions.create(
            model="gpt-3.5-turbo"
        )
        assert result_magicmock["id"] == "magicmock-test"

    def test_openai_chat_wrapper_magicmock_deep_nesting(self):
        """Test deeply nested attribute access with MagicMock."""
        mock_client = MagicMock()

        # Set up deeply nested mock structure
        mock_client.some.deep.nested.attribute.method.return_value = "deep_result"

        wrapper = OpenAIChatWrapper(mock_client, tracker=DummyTracker())

        # Test that deep nesting still works
        result = wrapper.some.deep.nested.attribute.method()
        assert result == "deep_result"

    def test_openai_chat_wrapper_magicmock_streaming(self):
        """Streaming test using a small fake client (avoid MagicMock streaming quirks)."""

        chunk1 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))]
        )
        chunk2 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))]
        )

        def gen():
            yield chunk1
            yield chunk2

        class Completions:
            def create(self, *args, **kwargs):
                if kwargs.get("stream"):
                    return gen()
                return SimpleNamespace(
                    id="resp-1",
                    model=kwargs.get("model"),
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                )

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        wrapper = OpenAIChatWrapper(Client(), tracker=DummyTracker())

        stream = wrapper.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Say hello"}],
            stream=True,
        )
        parts = list(stream)
        assert len(parts) == 2
        assert parts[0].choices[0].delta.content == "Hello"
        assert parts[1].choices[0].delta.content == " world"

    def test_openai_chat_wrapper_magicmock_callable_with_attributes(self):
        """Test that callable objects with attributes are handled correctly."""
        mock_client = MagicMock()

        # Create a callable mock that also has attributes
        callable_mock = MagicMock()
        callable_mock.some_attribute = "attribute_value"
        callable_mock.return_value = "callable_result"

        mock_client.callable_with_attrs = callable_mock

        wrapper = OpenAIChatWrapper(mock_client)

        # Test that we can access both the attribute and call the object
        assert wrapper.callable_with_attrs.some_attribute == "attribute_value"
        assert wrapper.callable_with_attrs() == "callable_result"
