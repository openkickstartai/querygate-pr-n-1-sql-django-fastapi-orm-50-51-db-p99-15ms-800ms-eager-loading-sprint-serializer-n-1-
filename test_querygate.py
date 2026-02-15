"""Tests for QueryGate core engine and CLI."""
import json
import argparse
from querygate import Gate, fingerprint, check_regression, load_baseline
from querygate import save_baseline, track, BudgetExceeded
import pytest


def test_fingerprint_normalizes_integers():
    assert fingerprint("SELECT * FROM users WHERE id = 1") == \
           fingerprint("SELECT * FROM users WHERE id = 9999")


def test_fingerprint_normalizes_strings():
    assert fingerprint("SELECT * FROM orders WHERE name = 'alice'") == \
           fingerprint("SELECT * FROM orders WHERE name = 'bob'")


def test_fingerprint_different_tables():
    assert fingerprint("SELECT * FROM users") != fingerprint("SELECT * FROM orders")


def test_nplus1_detection_critical():
    g = Gate()
    g.record("SELECT * FROM orders")
    for i in range(50):
        g.record(f"SELECT * FROM products WHERE id = {i}")
    violations = g.detect_nplus1(threshold=2)
    assert len(violations) == 1
    assert violations[0]["count"] == 50
    assert violations[0]["severity"] == "critical"


def test_nplus1_no_false_positive():
    g = Gate()
    g.record("SELECT * FROM users")
    g.record("SELECT * FROM orders")
    g.record("SELECT * FROM products")
    assert g.detect_nplus1(threshold=2) == []


def test_regression_pass():
    bl = {"test_list": 3}
    assert check_regression(bl, "test_list", 3)["status"] == "pass"


def test_regression_fail():
    bl = {"test_list": 3}
    r = check_regression(bl, "test_list", 10)
    assert r["status"] == "fail"
    assert r["delta"] == 7


def test_regression_new():
    assert check_regression({}, "test_new", 5)["status"] == "new"


def test_regression_improved():
    bl = {"test_list": 10}
    assert check_regression(bl, "test_list", 4)["status"] == "improved"


def test_tolerance():
    bl = {"test_x": 5}
    assert check_regression(bl, "test_x", 7, tolerance=3)["status"] == "pass"
    assert check_regression(bl, "test_x", 9, tolerance=3)["status"] == "fail"


def test_baseline_roundtrip(tmp_path):
    path = str(tmp_path / "bl.json")
    data = {"test_a": 3, "test_b": 7}
    save_baseline(data, path)
    loaded = load_baseline(path)
    assert loaded == data


def test_budget_exceeded():
    with pytest.raises(BudgetExceeded):
        with track(budget=2) as g:
            g.record("SELECT 1")
            g.record("SELECT 2")
            g.record("SELECT 3")


def test_budget_ok():
    with track(budget=5) as g:
        g.record("SELECT 1")
        g.record("SELECT 2")
    assert g.count == 2


def test_cli_check_regression(tmp_path, capsys):
    from cli import cmd_check
    bl_path = str(tmp_path / ".querygate.json")
    save_baseline({"test_users": 3, "test_orders": 5}, bl_path)
    results_path = str(tmp_path / "results.json")
    (tmp_path / "results.json").write_text(json.dumps({"test_users": 10, "test_orders": 5}))
    args = argparse.Namespace(results=results_path, baseline=bl_path, tolerance=0)
    exit_code = cmd_check(args)
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "regression" in out.lower() or "BLOCKED" in out


def test_cli_check_pass(tmp_path, capsys):
    from cli import cmd_check
    bl_path = str(tmp_path / ".querygate.json")
    save_baseline({"test_a": 3}, bl_path)
    results_path = str(tmp_path / "results.json")
    (tmp_path / "results.json").write_text(json.dumps({"test_a": 3}))
    args = argparse.Namespace(results=results_path, baseline=bl_path, tolerance=0)
    assert cmd_check(args) == 0
