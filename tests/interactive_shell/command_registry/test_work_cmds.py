"""Regression tests for interactive work-item commands."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from surfaces.interactive_shell.command_registry import dispatch_slash, work_cmds
from surfaces.interactive_shell.session import Session


@pytest.mark.parametrize(
    "command",
    [
        "/work add rotate API key --remind 2026-09-12T09:00",
        "/work add rotate API key --remind=2026-09-12T09:00",
        "/work add rotate API key --remind-at 2026-09-12T09:00",
    ],
)
def test_work_add_rejects_unscheduled_reminder_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    confirm_calls: list[str] = []

    def _confirm(prompt: str) -> str:
        confirm_calls.append(prompt)
        return "y"

    def _unexpected_add_work_item(**_kwargs: object) -> object:
        raise AssertionError("an unsupported reminder must not be persisted")

    monkeypatch.setattr(work_cmds, "add_work_item", _unexpected_add_work_item)
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, highlight=False)
    session = Session()

    assert (
        dispatch_slash(
            command,
            session,
            console,
            confirm_fn=_confirm,
            is_tty=True,
        )
        is True
    )

    rendered = output.getvalue()
    assert "reminder not scheduled:" in rendered
    assert "/work has no delivery target" in rendered
    assert "opensre work add" in rendered
    assert "--target <provider>:<chat-id>" in rendered
    assert confirm_calls == []
    assert session.history[-1]["ok"] is False


def test_work_help_explains_how_to_schedule_reminders() -> None:
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, highlight=False)

    assert dispatch_slash("/help /work", Session(), console) is True

    rendered = output.getvalue()
    assert "To schedule a reminder" in rendered
    assert "--remind-at <datetime>" in rendered
    assert "--target <provider>:<chat-id>" in rendered


@pytest.mark.parametrize(
    ("command", "expected_error"),
    [
        (
            "/work add Audit --project --priority urgent",
            "--project requires a value",
        ),
        (
            "/work add Audit --priority --project backend",
            "--priority requires a value",
        ),
        (
            "/work add Audit --owner --due 2026-10-10",
            "--owner requires a value",
        ),
    ],
)
def test_work_add_rejects_missing_option_value_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected_error: str,
) -> None:
    confirm_calls: list[str] = []

    def _confirm(prompt: str) -> str:
        confirm_calls.append(prompt)
        return "y"

    def _unexpected_add_work_item(**_kwargs: object) -> object:
        raise AssertionError("invalid input must not call add_work_item")

    monkeypatch.setattr(work_cmds, "add_work_item", _unexpected_add_work_item)
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, highlight=False)
    session = Session()

    assert (
        dispatch_slash(
            command,
            session,
            console,
            confirm_fn=_confirm,
            is_tty=True,
        )
        is True
    )

    rendered = output.getvalue()
    assert expected_error in rendered
    assert confirm_calls == []
    assert session.history[-1]["ok"] is False


def test_work_add_valid_command_creates_work_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def _build_fake_item(title: str) -> object:
        return type("FakeWorkItem", (), {"display_id": "item-1234", "title": title})()

    def _fake_add_work_item(**kwargs: object) -> object:
        calls.append(kwargs)
        return _build_fake_item(str(kwargs.get("title", "")))

    monkeypatch.setattr(work_cmds, "add_work_item", _fake_add_work_item)
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, highlight=False)
    session = Session()

    assert (
        dispatch_slash(
            "/work add Audit --project backend --priority urgent",
            session,
            console,
            is_tty=True,
        )
        is True
    )

    assert len(calls) == 1
    assert calls[0]["title"] == "Audit"
    assert calls[0]["project"] == "backend"
    assert calls[0]["priority"] == "urgent"
    assert session.history[-1]["ok"] is True
    assert "added item-1234 Audit" in output.getvalue()


def test_split_options_does_not_consume_subsequent_option() -> None:
    words, options = work_cmds._split_options(["Audit", "--project", "--priority", "urgent"])
    assert words == ["Audit"]
    assert options.get("project") == ""
    assert options.get("priority") == "urgent"
