"""Behaviour tests for the SessionStart principles-loader hook.

These pin the contract the hook must honour: the *full text* of every
configured principle document is injected into the session context, and any
misconfiguration fails *loud* (a visible warning in context) rather than
silently dropping the principles.
"""

from __future__ import annotations

import io
import json

import pytest

import session_principles_loader as loader


def _write_sidecar(tmp_path, files):
    sidecar = tmp_path / "session-principles.json"
    sidecar.write_text(json.dumps({loader.SIDECAR_KEY: files}), encoding="utf-8")
    return sidecar


def _write_doc(tmp_path, name, body):
    doc = tmp_path / name
    doc.write_text(body, encoding="utf-8")
    return doc


# --- read_sidecar -----------------------------------------------------------


def test_read_sidecar_returns_configured_paths(tmp_path):
    sidecar = _write_sidecar(tmp_path, ["a.md", "b.md"])
    assert loader.read_sidecar(sidecar) == ["a.md", "b.md"]


def test_read_sidecar_missing_file_raises(tmp_path):
    with pytest.raises(loader.PrinciplesError):
        loader.read_sidecar(tmp_path / "absent.json")


def test_read_sidecar_malformed_json_raises(tmp_path):
    bad = tmp_path / "session-principles.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(loader.PrinciplesError):
        loader.read_sidecar(bad)


def test_read_sidecar_missing_key_raises(tmp_path):
    bad = tmp_path / "session-principles.json"
    bad.write_text(json.dumps({"somethingElse": []}), encoding="utf-8")
    with pytest.raises(loader.PrinciplesError):
        loader.read_sidecar(bad)


def test_read_sidecar_non_list_value_raises(tmp_path):
    bad = _write_sidecar(tmp_path, "not-a-list.md")
    with pytest.raises(loader.PrinciplesError):
        loader.read_sidecar(bad)


def test_read_sidecar_empty_list_raises(tmp_path):
    bad = _write_sidecar(tmp_path, [])
    with pytest.raises(loader.PrinciplesError):
        loader.read_sidecar(bad)


def test_read_sidecar_non_string_entry_raises(tmp_path):
    bad = _write_sidecar(tmp_path, ["ok.md", 123])
    with pytest.raises(loader.PrinciplesError):
        loader.read_sidecar(bad)


# --- load_documents ---------------------------------------------------------


def test_load_documents_reads_existing(tmp_path):
    doc = _write_doc(tmp_path, "p.md", "PRINCIPLE BODY")
    loaded, failures = loader.load_documents([str(doc)])
    assert failures == []
    assert loaded == [(str(doc), "PRINCIPLE BODY")]


def test_load_documents_reports_missing(tmp_path):
    missing = str(tmp_path / "gone.md")
    loaded, failures = loader.load_documents([missing])
    assert loaded == []
    assert [path for path, _ in failures] == [missing]


def test_load_documents_expands_user_and_env_vars(tmp_path, monkeypatch):
    _write_doc(tmp_path, "p.md", "EXPANDED BODY")
    monkeypatch.setenv("PRIN_DIR", str(tmp_path))
    loaded, failures = loader.load_documents(["$PRIN_DIR/p.md"])
    assert failures == []
    assert loaded[0][1] == "EXPANDED BODY"


# --- build_context ----------------------------------------------------------


def test_build_context_injects_full_text_of_all_docs(tmp_path):
    d1 = _write_doc(tmp_path, "eng.md", "ENGINEERING-RULES-CONTENT")
    d2 = _write_doc(tmp_path, "collab.md", "COLLAB-RULES-CONTENT")
    sidecar = _write_sidecar(tmp_path, [str(d1), str(d2)])
    ctx = loader.build_context(sidecar)
    assert loader.ADHERENCE_HEADER in ctx
    assert "ENGINEERING-RULES-CONTENT" in ctx
    assert "COLLAB-RULES-CONTENT" in ctx
    assert str(d1) in ctx
    assert str(d2) in ctx
    assert loader.FAILURE_MARKER not in ctx
    assert loader.PARTIAL_MARKER not in ctx


def test_build_context_missing_sidecar_is_loud_failure(tmp_path):
    absent = tmp_path / "absent.json"
    ctx = loader.build_context(absent)
    assert loader.FAILURE_MARKER in ctx
    assert str(absent) in ctx


def test_build_context_partial_failure_keeps_loaded_and_warns(tmp_path):
    good = _write_doc(tmp_path, "good.md", "GOOD-CONTENT")
    missing = str(tmp_path / "missing.md")
    sidecar = _write_sidecar(tmp_path, [str(good), missing])
    ctx = loader.build_context(sidecar)
    assert "GOOD-CONTENT" in ctx
    assert loader.PARTIAL_MARKER in ctx
    assert missing in ctx


def test_build_context_all_docs_unreadable_is_loud_failure(tmp_path):
    sidecar = _write_sidecar(tmp_path, [str(tmp_path / "a.md"), str(tmp_path / "b.md")])
    ctx = loader.build_context(sidecar)
    assert loader.FAILURE_MARKER in ctx


# --- build_output / main ----------------------------------------------------


def test_build_output_has_sessionstart_envelope():
    assert loader.HOOK_EVENT_NAME == "SessionStart"
    assert loader.build_output("CTX") == {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "CTX",
        }
    }


def test_main_emits_valid_sessionstart_json_with_principles(tmp_path):
    doc = _write_doc(tmp_path, "p.md", "INJECTED-PRINCIPLE")
    sidecar = _write_sidecar(tmp_path, [str(doc)])
    stdout = io.StringIO()
    loader.main(io.StringIO('{"source": "compact"}'), stdout, sidecar_path=sidecar)
    payload = json.loads(stdout.getvalue())
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "INJECTED-PRINCIPLE" in payload["hookSpecificOutput"]["additionalContext"]


def test_main_tolerates_empty_stdin(tmp_path):
    doc = _write_doc(tmp_path, "p.md", "BODY-VIA-MAIN")
    sidecar = _write_sidecar(tmp_path, [str(doc)])
    stdout = io.StringIO()
    loader.main(io.StringIO(""), stdout, sidecar_path=sidecar)
    payload = json.loads(stdout.getvalue())
    assert "BODY-VIA-MAIN" in payload["hookSpecificOutput"]["additionalContext"]
