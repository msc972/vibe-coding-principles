"""Tests for ai_edit_guard.py — the PreToolUse edit / spec-annotation lock."""

import io
import json
import pathlib

import pytest

import ai_edit_guard as g


def _set_stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def _decision(capsys):
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    """Point the guard at a temp locked-paths.json with one glob."""
    p = tmp_path / "locked-paths.json"
    p.write_text(json.dumps({"lockedPaths": ["**/.claude/settings.json"]}))
    monkeypatch.setattr(g, "SIDECAR_PATH", p)
    return p


# ---- deny ----


def test_deny_emits_deny_json_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        g.deny("nope")
    assert exc.value.code == 0
    assert _decision(capsys) == "deny"


# ---- glob_to_regex ----


def test_glob_double_star_crosses_slashes():
    assert g.glob_to_regex("**/x").match("/a/b/x")


def test_glob_single_star_stops_at_slash():
    assert g.glob_to_regex("/a/*").match("/a/b")
    assert not g.glob_to_regex("/a/*").match("/a/b/c")


def test_glob_question_matches_one_char():
    assert g.glob_to_regex("/a/?").match("/a/b")
    assert not g.glob_to_regex("/a/?").match("/a/bc")


def test_glob_literal_is_escaped():
    assert g.glob_to_regex("/a.b").match("/a.b")
    assert not g.glob_to_regex("/a.b").match("/axb")


# ---- load_locked_globs ----


def test_load_globs_ok(sidecar):
    globs = g.load_locked_globs()
    assert any(rx.match("/home/u/.claude/settings.json") for rx in globs)


def test_load_globs_missing_file_denies(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(g, "SIDECAR_PATH", tmp_path / "nope.json")
    with pytest.raises(SystemExit):
        g.load_locked_globs()
    assert _decision(capsys) == "deny"


def test_load_globs_non_list_denies(tmp_path, monkeypatch, capsys):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"lockedPaths": "oops"}))
    monkeypatch.setattr(g, "SIDECAR_PATH", p)
    with pytest.raises(SystemExit):
        g.load_locked_globs()
    assert _decision(capsys) == "deny"


def test_load_globs_skips_non_string_entries(tmp_path, monkeypatch):
    p = tmp_path / "mixed.json"
    p.write_text(json.dumps({"lockedPaths": ["**/x", 123, None]}))
    monkeypatch.setattr(g, "SIDECAR_PATH", p)
    assert len(g.load_locked_globs()) == 1


# ---- expanded / path_matches_any ----


def test_expanded_includes_home_expansion(monkeypatch):
    monkeypatch.setenv("HOME", "/home/u")
    assert "/home/u/x" in g.expanded("~/x")


def test_path_matches_any_true_and_false():
    globs = [g.glob_to_regex("**/.claude/settings.json")]
    assert g.path_matches_any("/h/.claude/settings.json", globs)
    assert not g.path_matches_any("/h/other.txt", globs)


# ---- main ----


def test_main_malformed_stdin_denies(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    with pytest.raises(SystemExit):
        g.main()
    assert _decision(capsys) == "deny"


def test_main_locked_path_denies(monkeypatch, capsys, sidecar):
    _set_stdin(
        monkeypatch,
        {"tool_name": "Edit", "tool_input": {"file_path": "/h/.claude/settings.json"}},
    )
    with pytest.raises(SystemExit):
        g.main()
    assert _decision(capsys) == "deny"


def test_main_notebook_path_locked_denies(monkeypatch, capsys, sidecar):
    _set_stdin(
        monkeypatch,
        {
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": "/h/.claude/settings.json"},
        },
    )
    with pytest.raises(SystemExit):
        g.main()
    assert _decision(capsys) == "deny"


def test_main_no_file_path_allows(monkeypatch, sidecar):
    _set_stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {}})
    g.main()  # returns without raising SystemExit


def test_main_spec_marker_denies(monkeypatch, capsys, sidecar, tmp_path):
    f = tmp_path / "contract.py"
    f.write_text("@spec\ndef test_x():\n    assert True\n")
    _set_stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    with pytest.raises(SystemExit):
        g.main()
    assert _decision(capsys) == "deny"


def test_main_non_code_extension_skips_spec_scan(monkeypatch, sidecar, tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("@spec mentioned here as prose\n")
    _set_stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    g.main()  # allowed: .md is skipped despite the marker text


def test_main_missing_file_allows(monkeypatch, sidecar, tmp_path):
    _set_stdin(
        monkeypatch,
        {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "ghost.py")}},
    )
    g.main()  # is_file() False -> no spec scan, no deny


def test_main_resolve_oserror_falls_back(monkeypatch, sidecar, tmp_path):
    f = tmp_path / "plain.py"
    f.write_text("x = 1\n")

    def boom(self, *args, **kwargs):
        raise OSError

    monkeypatch.setattr(pathlib.Path, "resolve", boom)
    _set_stdin(monkeypatch, {"tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    g.main()  # falls back to Path(file_path); no marker -> allowed
