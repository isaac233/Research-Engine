"""Data model for predicted vs actually-touched file sets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set


@dataclass
class Outcome:
    task: str
    predicted: Set[str] = field(default_factory=set)
    actual: Set[str] = field(default_factory=set)

    def misses(self) -> Set[str]:
        return self.actual - self.predicted

    def over_fetch(self) -> Set[str]:
        return self.predicted - self.actual

    def precision(self) -> float:
        if not self.predicted:
            return 0.0
        return len(self.predicted & self.actual) / len(self.predicted)

    def recall(self) -> float:
        if not self.actual:
            return 0.0
        return len(self.predicted & self.actual) / len(self.actual)

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


def main() -> None:
    o = Outcome("test", predicted={"a.py", "b.py"}, actual={"b.py", "c.py"})
    assert o.misses() == {"c.py"}
    assert o.over_fetch() == {"a.py"}
    assert 0.0 < o.f1() < 1.0
    print("outcome_record self-check: OK")


if __name__ == "__main__":
    main()
