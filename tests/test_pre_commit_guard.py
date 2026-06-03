"""Tests for pre_commit_guard.py — the PreToolUse Bash guard + commit spec gate."""

import io
import json
import subprocess
import types

import pytest

import pre_commit_guard as g


def _set_stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def _decision(capsys):
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


def _completed(returncode, stdout="", stderr=""):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def globs():
    return [g.glob_to_regex("**/.claude/settings.json")]


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    p = tmp_path / "locked-paths.json"
    p.write_text(json.dumps({"lockedPaths": ["**/.claude/settings.json"]}))
    monkeypatch.setattr(g, "SIDECAR_PATH", p)
    return p


# ---- deny ----


def test_deny_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        g.deny("x")
    assert exc.value.code == 0
    assert _decision(capsys) == "deny"


# ---- glob_to_regex ----


def test_glob_forms():
    assert g.glob_to_regex("**/a").match("/x/a")
    assert g.glob_to_regex("/a/*").match("/a/b")
    assert not g.glob_to_regex("/a/*").match("/a/b/c")
    assert g.glob_to_regex("/a/?").match("/a/b")
    assert g.glob_to_regex("/a.b").match("/a.b")
    assert not g.glob_to_regex("/a.b").match("/axb")


# ---- load_locked_globs ----


def test_load_ok(sidecar):
    assert g.load_locked_globs()


def test_load_missing_denies(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(g, "SIDECAR_PATH", tmp_path / "no.json")
    with pytest.raises(SystemExit):
        g.load_locked_globs()
    assert _decision(capsys) == "deny"


def test_load_non_list_denies(tmp_path, monkeypatch, capsys):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"lockedPaths": 5}))
    monkeypatch.setattr(g, "SIDECAR_PATH", p)
    with pytest.raises(SystemExit):
        g.load_locked_globs()
    assert _decision(capsys) == "deny"


# ---- expanded / token_matches_locked ----


def test_token_matches_locked_true_false(globs):
    assert g.token_matches_locked("/h/.claude/settings.json", globs)
    assert not g.token_matches_locked("/h/x", globs)


# ---- check_locked_paths ----


def test_redirect_into_locked(globs):
    reason = g.check_locked_paths("echo x > /h/.claude/settings.json", globs)
    assert reason is not None
    assert "redirection" in reason


def test_nonreadonly_verb_targets_locked(globs):
    reason = g.check_locked_paths("rm /h/.claude/settings.json", globs)
    assert reason is not None
    assert "rm" in reason


def test_readonly_verb_allows(globs):
    assert g.check_locked_paths("cat /h/.claude/settings.json", globs) is None


def test_unrelated_command_allows(globs):
    assert g.check_locked_paths("rm /tmp/x", globs) is None


def test_redirect_to_unlocked_path_allows(globs):
    # Redirect target exists but isn't locked -> loop continues, overall None.
    assert g.check_locked_paths("echo x > /tmp/safe.log", globs) is None


def test_unbalanced_quotes_segment_skipped(globs):
    # shlex.split raises ValueError -> segment skipped -> overall None
    assert g.check_locked_paths("echo 'unterminated", globs) is None


def test_empty_segments_allow(globs):
    assert g.check_locked_paths("   ;  ;  ", globs) is None


# ---- is_git_commit ----


def test_is_git_commit_true():
    assert g.is_git_commit("git add . && git commit -m x")


def test_is_git_commit_false():
    assert not g.is_git_commit("git status")


# ---- run_spec_gate ----


def test_gate_pytest_missing_denies(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(SystemExit):
        g.run_spec_gate()
    assert _decision(capsys) == "deny"


def test_gate_timeout_denies(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(SystemExit):
        g.run_spec_gate()
    assert _decision(capsys) == "deny"


def test_gate_no_tests_collected_allows(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(5))
    g.run_spec_gate()  # returns, no SystemExit


def test_gate_failure_denies(monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(1, stdout="boom"))
    with pytest.raises(SystemExit):
        g.run_spec_gate()
    assert _decision(capsys) == "deny"


def test_gate_pass_allows(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(0))
    g.run_spec_gate()  # returns


# ---- main ----


def test_main_malformed_stdin_denies(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{nope"))
    with pytest.raises(SystemExit):
        g.main()
    assert _decision(capsys) == "deny"


def test_main_non_bash_returns(monkeypatch):
    _set_stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {}})
    g.main()


def test_main_locked_path_denies(monkeypatch, capsys, sidecar):
    _set_stdin(
        monkeypatch,
        {"tool_name": "Bash", "tool_input": {"command": "rm /h/.claude/settings.json"}},
    )
    with pytest.raises(SystemExit):
        g.main()
    assert _decision(capsys) == "deny"


def test_main_git_commit_runs_gate(monkeypatch, sidecar):
    called = {}
    monkeypatch.setattr(g, "run_spec_gate", lambda: called.setdefault("ran", True))
    _set_stdin(
        monkeypatch,
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}},
    )
    g.main()
    assert called.get("ran")


def test_main_non_commit_skips_gate(monkeypatch, sidecar):
    def fail():
        msg = "run_spec_gate should not be called for non-commit commands"
        raise AssertionError(msg)

    monkeypatch.setattr(g, "run_spec_gate", fail)
    _set_stdin(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    g.main()
