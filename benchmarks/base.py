from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BenchmarkQuestion:
    id: str
    question: str
    choices: list[str]
    answer: int  # index of correct choice

    def format(self) -> str:
        opts = "\n".join(f"{chr(65 + i)}. {c}" for i, c in enumerate(self.choices))
        return f"{self.question}\n\n{opts}"

    def correct_letter(self) -> str:
        return chr(65 + self.answer)

    def correct_text(self) -> str:
        return self.choices[self.answer]


class BenchmarkDataset(ABC):
    name: str
    description: str

    @abstractmethod
    def load(self, split: str = "test", limit: int | None = None) -> list[BenchmarkQuestion]:
        ...
