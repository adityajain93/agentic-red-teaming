from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from .episode import AttackAssignment, AttackCandidate, AttackAttempt, EvaluationResult


class AttackerModuleError(ValueError):
    """Raised when a generated attacker module does not satisfy the API."""


class GeneratedAttacker(Protocol):
    """Small API implemented by Codex-produced attacker modules."""

    def next_user_message(
        self,
        *,
        assignment: AttackAssignment,
        attacker_context: dict[str, Any],
        history: list[dict[str, str]],
        previous_evaluations: list[EvaluationResult],
        attempt_index: int,
    ) -> AttackCandidate | dict[str, Any] | str:
        """Return the next attack artifact for the shared harness to execute."""


class StatefulAttackerBuilder:
    """Adapter that lets generated attacker modules plug into the episode runner."""

    def __init__(self, attacker: GeneratedAttacker):
        if not hasattr(attacker, "next_user_message"):
            raise AttackerModuleError("Attacker object must implement next_user_message(...).")
        self.attacker = attacker
        self.history: list[dict[str, str]] = []
        self.previous_evaluations: list[EvaluationResult] = []
        self._started = False

    def build_candidate(
        self,
        *,
        assignment: AttackAssignment,
        attacker_context: dict[str, Any],
        previous_attempts: list[AttackAttempt],
    ) -> AttackCandidate:
        self._start_if_needed(assignment=assignment, attacker_context=attacker_context)
        raw = self.attacker.next_user_message(
            assignment=assignment,
            attacker_context=attacker_context,
            history=self.history,
            previous_evaluations=self.previous_evaluations,
            attempt_index=len(previous_attempts) + 1,
        )
        return normalize_attack_candidate(raw)

    def observe_attempt(
        self,
        *,
        assignment: AttackAssignment,
        attacker_context: dict[str, Any],
        candidate: AttackCandidate,
        transcript: list[dict[str, str]],
        evaluation: EvaluationResult,
        attempt: AttackAttempt,
    ) -> None:
        self.history = [dict(message) for message in transcript]
        self.previous_evaluations.append(evaluation)
        observer = getattr(self.attacker, "observe", None)
        if callable(observer):
            observer(
                assignment=assignment,
                attacker_context=attacker_context,
                candidate=candidate,
                transcript=transcript,
                evaluation=evaluation,
                attempt=attempt,
            )

    def finish_episode(
        self,
        *,
        assignment: AttackAssignment,
        attacker_context: dict[str, Any],
        attempts: list[AttackAttempt],
    ) -> dict[str, list[str]]:
        finisher = getattr(self.attacker, "finish", None)
        if not callable(finisher):
            return {}
        raw = finisher(
            assignment=assignment,
            attacker_context=attacker_context,
            attempts=attempts,
            previous_evaluations=self.previous_evaluations,
        )
        if not isinstance(raw, dict):
            return {}
        return {
            "conclusions": [str(item) for item in raw.get("conclusions", [])],
            "next_ideas": [str(item) for item in raw.get("next_ideas", [])],
        }

    def _start_if_needed(
        self,
        *,
        assignment: AttackAssignment,
        attacker_context: dict[str, Any],
    ) -> None:
        if self._started:
            return
        starter = getattr(self.attacker, "start", None)
        if callable(starter):
            starter(assignment=assignment, attacker_context=attacker_context)
        self._started = True


def normalize_attack_candidate(raw: AttackCandidate | dict[str, Any] | str) -> AttackCandidate:
    if isinstance(raw, AttackCandidate):
        _validate_candidate(raw)
        return raw
    if isinstance(raw, str):
        candidate = AttackCandidate(
            artifact_kind="string",
            strategy="generated_attacker",
            user_messages=[raw],
            attacks_tried=["generated string"],
        )
        _validate_candidate(candidate)
        return candidate
    if isinstance(raw, dict):
        candidate = AttackCandidate(
            artifact_kind=str(raw.get("artifact_kind", "stateful_agent")),
            strategy=str(raw.get("strategy", "generated_attacker")),
            user_messages=[str(item) for item in raw.get("user_messages", [])],
            attacks_tried=[str(item) for item in raw.get("attacks_tried", [])],
            rationale=str(raw.get("rationale", "")),
            next_ideas=[str(item) for item in raw.get("next_ideas", [])],
        )
        _validate_candidate(candidate)
        return candidate
    raise AttackerModuleError(
        "next_user_message(...) must return AttackCandidate, dict, or string."
    )


def load_attacker_builder(module: str) -> StatefulAttackerBuilder:
    loaded = _load_module(module)
    factory = getattr(loaded, "create_attacker", None)
    if not callable(factory):
        raise AttackerModuleError(
            f"Attacker module {module!r} must define create_attacker()."
        )
    return StatefulAttackerBuilder(factory())


def _load_module(module: str) -> ModuleType:
    path = Path(module)
    if path.exists() or module.endswith(".py"):
        if not path.exists():
            raise AttackerModuleError(f"Attacker module path does not exist: {module}")
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise AttackerModuleError(f"Could not import attacker module from {module}")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        return loaded
    return importlib.import_module(module)


def _validate_candidate(candidate: AttackCandidate) -> None:
    if not candidate.user_messages:
        raise AttackerModuleError("AttackCandidate.user_messages must not be empty.")
    if any(not isinstance(message, str) or not message.strip() for message in candidate.user_messages):
        raise AttackerModuleError("AttackCandidate.user_messages must contain non-empty strings.")
    if not candidate.strategy.strip():
        raise AttackerModuleError("AttackCandidate.strategy must not be empty.")
