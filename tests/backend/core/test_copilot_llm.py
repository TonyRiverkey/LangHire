from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ValidationError
from browser_use.llm.messages import UserMessage
from core import copilot_llm


@pytest.fixture
def client(monkeypatch):
    session = AsyncMock()
    session.send_and_wait.return_value = SimpleNamespace(data=SimpleNamespace(content='{"answer":"hello"}'))
    context = AsyncMock()
    context.__aenter__.return_value = session
    client = AsyncMock()
    client.get_auth_status.return_value = SimpleNamespace(is_authenticated=True)
    client.create_session.return_value = context
    manager = AsyncMock()
    manager.__aenter__.return_value = client
    monkeypatch.setattr(copilot_llm, "CopilotClient", MagicMock(return_value=manager))
    monkeypatch.setattr(copilot_llm.shutil, "which", lambda _: "copilot")
    return client, session


class Answer(BaseModel):
    answer: str


async def test_structured_response_and_screenshot(client):
    sdk, session = client
    message = UserMessage(content=[{"type": "text", "text": "Read page"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}}])
    response = await copilot_llm.ChatCopilot().ainvoke([message], output_format=Answer)
    assert response.completion.answer == "hello"
    assert sdk.create_session.call_args.kwargs["tools"] == {"available_tools": []}
    options = sdk.create_session.call_args.kwargs
    assert options["enable_config_discovery"] is False
    assert options["hooks"]["enable_repository_hooks"] is False
    assert options["skills"]["enabled"] is False
    assert options["state"]["memory"]["enabled"] is False
    assert options["state"]["enable_cross_session_store"] is False
    assert options["instructions"]["skip_custom_instructions"] is True
    assert options["mcp"] == {"servers": {}, "enable_apps": False}
    sent = session.send_and_wait.call_args.kwargs
    assert sent["response_schema"]["additionalProperties"] is False
    assert sent["attachments"] == [{"type": "blob", "mimeType": "image/png", "data": "aGVsbG8="}]


async def test_invalid_json_is_rejected(client):
    client[1].send_and_wait.return_value.data.content = "not JSON"
    with pytest.raises(ValidationError):
        await copilot_llm.ChatCopilot().ainvoke([], output_format=Answer)


async def test_sign_in_required(client):
    client[0].get_auth_status.return_value.is_authenticated = False
    with pytest.raises(RuntimeError, match="copilot login"):
        await copilot_llm.ChatCopilot().ainvoke([])
    client[0].create_session.assert_not_called()
