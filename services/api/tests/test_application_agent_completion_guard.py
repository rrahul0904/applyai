import uuid

import pytest
from fastapi import HTTPException

from app.api import application_agent_completion_guard as guard
from app.api.application_agent import BrowserCompletionWrite, complete_browser_execution
from app.main import app


def _body(status: str, *, verified: bool | None = None) -> BrowserCompletionWrite:
    validation = {} if verified is None else {"pre_submit_verified": verified}
    return BrowserCompletionWrite(status=status, validation=validation)


def test_terminal_browser_completion_requires_verification_receipt(monkeypatch) -> None:
    called = False

    def delegate(**_kwargs):
        nonlocal called
        called = True
        return {"state": "CONFIRMED"}

    monkeypatch.setattr(guard, "complete_browser_execution_unchecked", delegate)

    for browser_status in ("SUBMITTED", "CONFIRMED"):
        with pytest.raises(HTTPException) as exc:
            guard.complete_verified_browser_execution(
                uuid.uuid4(),
                _body(browser_status),
                session=object(),
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "PRE_SUBMIT_VERIFICATION_REQUIRED"

    assert called is False


def test_verified_terminal_browser_completion_delegates(monkeypatch) -> None:
    captured = {}

    def delegate(**kwargs):
        captured.update(kwargs)
        return {"state": "CONFIRMED"}

    monkeypatch.setattr(guard, "complete_browser_execution_unchecked", delegate)
    execution_id = uuid.uuid4()
    body = _body("CONFIRMED", verified=True)

    result = guard.complete_verified_browser_execution(execution_id, body, session=object())

    assert result == {"state": "CONFIRMED"}
    assert captured["execution_id"] == execution_id
    assert captured["body"] is body


@pytest.mark.parametrize("browser_status", ["FAILED", "HUMAN_ACTION_REQUIRED"])
def test_non_terminal_outcomes_do_not_require_verification_receipt(monkeypatch, browser_status: str) -> None:
    calls = []

    def delegate(**kwargs):
        calls.append(kwargs)
        return {"state": browser_status}

    monkeypatch.setattr(guard, "complete_browser_execution_unchecked", delegate)

    result = guard.complete_verified_browser_execution(
        uuid.uuid4(),
        _body(browser_status),
        session=object(),
    )

    assert result == {"state": browser_status}
    assert len(calls) == 1


def test_guarded_completion_endpoint_is_registered_before_legacy_endpoint() -> None:
    endpoints = [getattr(route, "endpoint", None) for route in app.routes]

    guard_index = endpoints.index(guard.complete_verified_browser_execution)
    legacy_index = endpoints.index(complete_browser_execution)

    assert guard_index < legacy_index
