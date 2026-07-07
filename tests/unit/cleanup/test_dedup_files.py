"""Tests for file deduplication."""

from __future__ import annotations

from pathlib import Path

from research_engine.cleanup.dedup_files import FileDeduplicator


def test_dedup_removes_duplicates_keeps_one(tmp_path: Path) -> None:
    original = tmp_path / "a.txt"
    duplicate = tmp_path / "b.txt"
    original.write_text("shared content", encoding="utf-8")
    duplicate.write_text("shared content", encoding="utf-8")

    dedup = FileDeduplicator(tmp_path)
    result = dedup.dedup()

    assert result.ok is True
    assert result.scanned == 2
    assert result.duplicates_removed == 1
    assert result.bytes_saved == len("shared content")
    remaining = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(remaining) == 1


def test_dedup_keeps_different_files(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("content a", encoding="utf-8")
    b.write_text("content b", encoding="utf-8")

    dedup = FileDeduplicator(tmp_path)
    result = dedup.dedup()

    assert result.ok is True
    assert result.scanned == 2
    assert result.duplicates_removed == 0
    assert a.exists()
    assert b.exists()


def test_dedup_respects_min_size(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("x", encoding="utf-8")
    b.write_text("x", encoding="utf-8")

    dedup = FileDeduplicator(tmp_path, min_size_bytes=2)
    result = dedup.dedup()

    assert result.ok is True
    assert result.scanned == 2
    assert result.duplicates_removed == 0
    assert a.exists()
    assert b.exists()


def test_dedup_handles_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    dedup = FileDeduplicator(missing)
    result = dedup.dedup()

    assert result.ok is True
    assert missing.name in (result.error or "")


def test_dedup_recovers_from_unreadable_file(tmp_path: Path) -> None:
    readable = tmp_path / "readable.txt"
    unreadable = tmp_path / "unreadable.txt"
    readable.write_text("content", encoding="utf-8")
    unreadable.write_text("content", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        dedup = FileDeduplicator(tmp_path)
        result = dedup.dedup()
        # The unreadable file cannot be hashed, so it is skipped.
        assert result.ok is True
        assert result.scanned == 2
        assert result.duplicates_removed == 0
    finally:
        unreadable.chmod(0o644)
