import json
from pathlib import Path

import pytest

from lead_pipeline.config import load_settings
from lead_pipeline.notify import NotifyError, push_google_sheets, send_telegram
from lead_pipeline.prompts import list_prompts, load_prompt, parse_prompt_file


def test_prompt_versions_are_loaded_in_order() -> None:
    prompts = list_prompts()
    assert [p.version for p in prompts] == ["v1", "v2"]
    latest = load_prompt()
    assert latest.version == "v2"
    assert "Категории" in latest.text
    assert latest.meta["model"] == "claude-haiku-5-5"
    assert load_prompt(version="v1").version == "v1"
    with pytest.raises(FileNotFoundError):
        load_prompt(version="v99")


def test_parse_prompt_file_without_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "custom.v3.md"
    path.write_text("Просто текст", encoding="utf-8")
    prompt = parse_prompt_file(path)
    assert (prompt.name, prompt.version, prompt.text) == ("custom", "v3", "Просто текст")


def test_integrations_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings()
    assert settings.telegram_enabled is False and settings.gsheets_enabled is False
    assert send_telegram("текст", settings) is False
    assert push_google_sheets([], settings) is False


def test_telegram_enabled_without_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFY_TELEGRAM", "1")
    with pytest.raises(NotifyError):
        send_telegram("текст", load_settings())


def test_telegram_sends_with_fake_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFY_TELEGRAM", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"ok": True}).encode()

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        return FakeResponse()

    assert send_telegram("<b>сводка</b>", load_settings(), opener=opener) is True
    assert captured["url"].endswith("/bot123:test/sendMessage")
    assert captured["body"]["chat_id"] == "42" and captured["body"]["parse_mode"] == "HTML"
