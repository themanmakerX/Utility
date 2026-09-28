import os
import tempfile
import io
import pytest

from grepper import fmt_size, fmt_time, is_binary_quick, load_gitignore_rules, gitignore_ignored


def test_fmt_size():
    assert fmt_size(500) == "500 B"
    assert "KB" in fmt_size(2048)


def test_fmt_time():
    s = fmt_time(0)
    assert isinstance(s, str)


def test_is_binary_quick(tmp_path):
    p = tmp_path / "text.txt"
    p.write_text("hello world", encoding="utf-8")
    assert not is_binary_quick(str(p))
    b = tmp_path / "bin.dat"
    b.write_bytes(b"\x00\x01\x02")
    assert is_binary_quick(str(b))


def test_gitignore_rules(tmp_path):
    base = tmp_path
    gi = base / ".gitignore"
    gi.write_text("node_modules/\n!important.txt\n*.log\n")
    rules = load_gitignore_rules(str(base))
    assert any("node_modules" in r[0] for r in rules)


def test_gitignore_ignored(tmp_path):
    base = tmp_path
    gi = base / ".gitignore"
    gi.write_text("*.log\n")
    rules = load_gitignore_rules(str(base))
    assert gitignore_ignored("error.log", False, rules)
    assert not gitignore_ignored("README.md", False, rules)
