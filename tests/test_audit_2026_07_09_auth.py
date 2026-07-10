"""Regression tests for the v0.0.10 authentication audit fixes."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest


def _write_token(path: Path, token: str, *, codex: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tokens": {"access_token": token}} if codex else {"access_token": token}
    path.write_text(json.dumps(payload))


def test_noninteractive_get_token_never_calls_browser_sources(monkeypatch) -> None:
    from gpt2agent import auth

    interactive_calls: list[str] = []
    monkeypatch.setattr(auth, "_from_codex", lambda: None)
    monkeypatch.setattr(auth, "_from_saved", lambda: None)
    monkeypatch.setattr(
        auth,
        "_from_browser_use",
        lambda: interactive_calls.append("browser-use"),
    )
    monkeypatch.setattr(
        auth,
        "_from_browser",
        lambda: interactive_calls.append("manual"),
    )

    with pytest.raises(RuntimeError, match="No ChatGPT token found"):
        auth.get_token(interactive=False)

    assert interactive_calls == []


def test_browser_use_absence_never_requires_posix_which(monkeypatch) -> None:
    from gpt2agent import auth

    monkeypatch.setenv("PATH", "")

    def unexpected_subprocess(*args, **kwargs):
        raise AssertionError("browser-use subprocess must not run when it is absent")

    monkeypatch.setattr(auth.subprocess, "run", unexpected_subprocess)
    assert auth._from_browser_use() is None


def test_auth_manual_token_uses_hidden_input(monkeypatch) -> None:
    from gpt2agent import auth

    token = "eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl"
    monkeypatch.setattr(auth.webbrowser, "open", lambda *args, **kwargs: True)
    monkeypatch.setattr(getpass, "getpass", lambda *args, **kwargs: token)
    monkeypatch.setattr(
        "builtins.input",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("secret token input must not echo through input()")
        ),
    )

    assert auth._from_browser() == {"access_token": token, "source": "browser"}


def test_setup_manual_token_is_hidden_and_validated(monkeypatch) -> None:
    from gpt2agent import setup

    values = iter(["not-a-jwt", "eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl"])
    monkeypatch.setattr(setup.webbrowser, "open", lambda *args, **kwargs: True)
    monkeypatch.setattr(getpass, "getpass", lambda *args, **kwargs: next(values))
    monkeypatch.setattr(
        "builtins.input",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("secret token input must not echo through input()")
        ),
    )

    assert setup._token_via_manual() is None
    assert setup._token_via_manual() == "eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl"


def test_backend_switches_to_new_preferred_codex_source(tmp_path, monkeypatch) -> None:
    from gpt2agent import backend

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    saved = tmp_path / ".gpt2agent" / "token.json"
    codex = tmp_path / ".codex" / "auth.json"
    _write_token(saved, "SAVED_OLD", codex=False)

    client = backend.BackendClient()
    assert client._session.headers["Authorization"] == "Bearer SAVED_OLD"
    assert client._token_source == saved

    _write_token(codex, "CODEX_NEW", codex=True)
    client._reload_token_if_stale()

    assert client._session.headers["Authorization"] == "Bearer CODEX_NEW"
    assert client._token_source == codex


def test_backend_falls_back_when_codex_source_disappears(tmp_path, monkeypatch) -> None:
    from gpt2agent import backend

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    saved = tmp_path / ".gpt2agent" / "token.json"
    codex = tmp_path / ".codex" / "auth.json"
    _write_token(saved, "SAVED_FALLBACK", codex=False)
    _write_token(codex, "CODEX_OLD", codex=True)

    client = backend.BackendClient()
    assert client._token_source == codex

    codex.unlink()
    client._reload_token_if_stale()

    assert client._session.headers["Authorization"] == "Bearer SAVED_FALLBACK"
    assert client._token_source == saved


class _PlanClient:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    def get(self, path: str):
        if self.error is not None:
            raise self.error
        return self.response


@pytest.mark.parametrize(
    "client,match",
    [
        (_PlanClient({"accounts": {}}), "verify"),
        (_PlanClient(error=RuntimeError("401 Unauthorized")), "401 Unauthorized"),
    ],
)
def test_setup_does_not_claim_plus_for_unverified_account(monkeypatch, client, match) -> None:
    from gpt2agent import backend, setup

    monkeypatch.setattr(backend, "BackendClient", lambda: client)

    with pytest.raises(RuntimeError, match=match):
        setup.detect_plan()


def test_setup_detects_verified_free_account(monkeypatch) -> None:
    from gpt2agent import backend, setup

    response = {
        "accounts": {
            "acct": {
                "entitlement": {
                    "subscription_plan": "free",
                    "has_active_subscription": False,
                }
            }
        }
    }
    monkeypatch.setattr(backend, "BackendClient", lambda: _PlanClient(response))

    assert setup.detect_plan() == "free"
