"""Handoff documents written when the pipeline switches models between steps.

Model switches lose the previous model's working memory, so a handoff doc
carries intent forward: the goal, what the previous step produced, open
questions, and what the next model must do. This keeps a multi-lane,
many-handoff (all-quality) run focused.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HandoffDoc:
    campaign_id: str
    from_stage: str
    to_stage: str
    from_model: str
    to_model: str
    goal: str
    produced: str
    open_questions: str
    next_task: str

    def render(self) -> str:
        ts = datetime.now(UTC).isoformat()
        return "\n".join(
            [
                f"# Handoff: {self.from_stage} -> {self.to_stage}",
                f"- when: {ts}",
                f"- from_model: {self.from_model}",
                f"- to_model: {self.to_model}",
                "",
                "## Goal",
                self.goal,
                "",
                "## Produced by previous step",
                self.produced,
                "",
                "## Open questions",
                self.open_questions or "(none)",
                "",
                "## Next step must do",
                self.next_task,
                "",
            ]
        )

    def write(self, base_dir: Path | str) -> Path:
        out_dir = Path(base_dir) / "handoffs" / self.campaign_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.from_stage}__{self.to_stage}.md"
        path.write_text(self.render(), encoding="utf-8")
        return path


def _demo() -> None:
    import tempfile

    doc = HandoffDoc(
        campaign_id="c1", from_stage="extract", to_stage="evaluate",
        from_model="gemma4:12b", to_model="synth_a", goal="find X",
        produced="3 sources extracted", open_questions="", next_task="synthesize",
    )
    with tempfile.TemporaryDirectory() as tmp:
        p = doc.write(tmp)
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "extract -> evaluate" in text and "gemma4:12b" in text
    print("handoff demo ok")


if __name__ == "__main__":
    _demo()
