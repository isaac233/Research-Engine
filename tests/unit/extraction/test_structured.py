"""Unit tests for structured extraction."""

from __future__ import annotations

from research_engine.discovery.schema import Paper
from research_engine.extraction.structured import StructuredExtractor, extracted_source_to_dict


def test_extracts_sections_from_markdown() -> None:
    paper = Paper(
        title="Test Paper",
        source="test",
        source_id="id-1",
        abstract="A short abstract.",
    )
    content = """
# Test Paper

We find that the new method improves accuracy.

## Method

We used a controlled experiment.

## Data

We collected 1,000 samples.

## Results

Accuracy increased by 12%.
"""
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content)

    assert source.title == "Test Paper"
    assert "controlled experiment" in source.methodology
    assert "1,000 samples" in source.data_summary
    assert "12%" in source.results_summary
    assert len(source.claims) >= 1


def test_detects_conflict_with_project_data() -> None:
    paper = Paper(title="Conflict Paper", source="test")
    content = "We find that the accuracy is 95%."
    project_data = [{"text": "The accuracy is 95%"}]
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content, project_data=project_data)
    assert len(source.conflicts) >= 1


def test_extracted_source_to_dict_round_trip_shape() -> None:
    paper = Paper(title="Dict Paper", source="test")
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content="We find a result.")
    data = extracted_source_to_dict(source)
    assert data["title"] == "Dict Paper"
    assert "claims" in data
    assert "citations" in data
    assert "conflicts" in data


def test_no_content_uses_abstract() -> None:
    paper = Paper(title="Abstract Paper", source="test", abstract="This is the abstract.")
    extractor = StructuredExtractor()
    source = extractor.extract(paper)
    assert source.summary == "This is the abstract."
    assert source.extraction_tool == "abstract"
