"""Tests for the cleanup janitor."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.cleanup.janitor import CleanupJanitor, CleanupResult
from research_engine.state import CampaignStore, ResearchRequest


def test_janitor_vacuums_existing_db() -> None:
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "state.db"
    store = CampaignStore(db_path)
    store.create_campaign(ResearchRequest(query="cleanup test"))
    before_size = db_path.stat().st_size

    janitor = CleanupJanitor(db_path)
    result = janitor.clean()

    assert isinstance(result, CleanupResult)
    assert result.ok is True
    assert result.vacuumed_db == str(db_path)
    assert result.error is None
    assert db_path.exists()
    assert db_path.stat().st_size <= before_size


def test_janitor_returns_error_for_missing_db() -> None:
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "missing.db"
    janitor = CleanupJanitor(db_path)
    result = janitor.clean()

    assert result.ok is False
    assert result.vacuumed_db is None
    assert "not found" in (result.error or "")


def test_janitor_handles_no_db_path() -> None:
    janitor = CleanupJanitor(None)
    result = janitor.clean()

    assert result.ok is True
    assert result.vacuumed_db is None
    assert "No state DB" in (result.error or "")


def test_janitor_deduplicates_engine_data_dir() -> None:
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "state.db"
    data_dir = tmp / "data"
    data_dir.mkdir()
    store = CampaignStore(db_path)
    store.create_campaign(ResearchRequest(query="cleanup dedup test"))

    original = data_dir / "original.txt"
    duplicate = data_dir / "duplicate.txt"
    original.write_text("shared", encoding="utf-8")
    duplicate.write_text("shared", encoding="utf-8")

    janitor = CleanupJanitor(db_path, engine_data_dir=data_dir)
    result = janitor.clean()

    assert result.ok is True
    assert result.vacuumed_db == str(db_path)
    assert result.meta.get("dedup_removed") == 1
    assert result.meta.get("dedup_scanned") == 2
    remaining = [p for p in data_dir.iterdir() if p.is_file()]
    assert len(remaining) == 1
