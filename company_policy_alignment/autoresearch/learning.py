from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEARNING_BLOCK_START = "<!-- company_policy_alignment_learning:v1"
LEARNING_BLOCK_END = "-->"
DEFAULT_LEARNINGS_ROOT = Path(__file__).resolve().parents[1] / "learnings"
DEFAULT_FLEET_MEMORY = """# Fleet Learning Memory

No fleet-learning reports have been processed yet.
"""


@dataclass(frozen=True)
class AttackAttempt:
    """One concrete attempt by an adversarial user agent."""

    iteration: int
    seed_id: str
    example_query: str
    target_policy: str
    strategy: str
    attacks_tried: list[str]
    succeeded: bool
    label_preserved: bool
    break_happened: bool
    observed_behavior: str = "unclear"
    judge_reason: str = ""
    transcript: list[dict[str, str]] = field(default_factory=list)
    notes: str = ""
    next_ideas: list[str] = field(default_factory=list)

    @property
    def confirmed_break(self) -> bool:
        return self.label_preserved and self.break_happened

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttackAttempt":
        return cls(
            iteration=int(data["iteration"]),
            seed_id=str(data["seed_id"]),
            example_query=str(data["example_query"]),
            target_policy=str(data["target_policy"]),
            strategy=str(data["strategy"]),
            attacks_tried=[str(item) for item in data.get("attacks_tried", [])],
            succeeded=bool(data.get("succeeded", False)),
            label_preserved=bool(data.get("label_preserved", False)),
            break_happened=bool(data.get("break_happened", False)),
            observed_behavior=str(data.get("observed_behavior", "unclear")),
            judge_reason=str(data.get("judge_reason", "")),
            transcript=_normalize_transcript(data.get("transcript", [])),
            notes=str(data.get("notes", "")),
            next_ideas=[str(item) for item in data.get("next_ideas", [])],
        )


@dataclass(frozen=True)
class AgentLearningDocument:
    """A self-contained learning report written by one adversarial agent."""

    agent_id: str
    target_policy: str
    seed_ids: list[str]
    attempts: list[AttackAttempt]
    conclusions: list[str]
    next_ideas: list[str]
    max_iterations: int = 5
    stopped_reason: str = "max_iterations"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success_count(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.confirmed_break)

    @property
    def attempted_strategy_names(self) -> list[str]:
        return sorted({attempt.strategy for attempt in self.attempts})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentLearningDocument":
        return cls(
            agent_id=str(data["agent_id"]),
            target_policy=str(data["target_policy"]),
            seed_ids=[str(item) for item in data.get("seed_ids", [])],
            attempts=[AttackAttempt.from_dict(item) for item in data.get("attempts", [])],
            conclusions=[str(item) for item in data.get("conclusions", [])],
            next_ideas=[str(item) for item in data.get("next_ideas", [])],
            max_iterations=int(data.get("max_iterations", 5)),
            stopped_reason=str(data.get("stopped_reason", "max_iterations")),
            created_at=str(data.get("created_at") or datetime.now(timezone.utc).isoformat()),
        )

    def render_markdown(self) -> str:
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True)
        lines = [
            f"# Attacker Learning: {self.agent_id}",
            "",
            LEARNING_BLOCK_START,
            payload,
            LEARNING_BLOCK_END,
            "",
            "## Summary",
            "",
            f"- Agent: `{self.agent_id}`",
            f"- Target policy: `{self.target_policy}`",
            f"- Seeds: {', '.join(f'`{seed}`' for seed in self.seed_ids) or '`none`'}",
            f"- Iterations: `{len(self.attempts)}/{self.max_iterations}`",
            f"- Confirmed breaks: `{self.success_count}`",
            f"- Stopped reason: `{self.stopped_reason}`",
            "",
            "## Exact Examples Tried",
            "",
        ]

        if not self.attempts:
            lines.extend(["No attempts recorded.", ""])
        for attempt in self.attempts:
            result = "confirmed_break" if attempt.confirmed_break else "no_break"
            lines.extend(
                [
                    f"### Attempt {attempt.iteration}: {attempt.strategy}",
                    "",
                    f"- Seed: `{attempt.seed_id}`",
                    f"- Query: {attempt.example_query}",
                    f"- Result: `{result}`",
                    f"- Label preserved: `{attempt.label_preserved}`",
                    f"- Observed behavior: `{attempt.observed_behavior}`",
                    f"- Judge reason: {attempt.judge_reason or 'n/a'}",
                    "",
                    "Attacks tried:",
                ]
            )
            if attempt.attacks_tried:
                lines.extend(f"- {item}" for item in attempt.attacks_tried)
            else:
                lines.append("- n/a")
            if attempt.notes:
                lines.extend(["", "Notes:", "", attempt.notes])
            if attempt.next_ideas:
                lines.extend(["", "Next ideas from this attempt:"])
                lines.extend(f"- {item}" for item in attempt.next_ideas)
            if attempt.transcript:
                lines.extend(
                    [
                        "",
                        "Transcript:",
                        "",
                        "```json",
                        json.dumps(attempt.transcript, indent=2, sort_keys=True),
                        "```",
                    ]
                )
            lines.append("")

        lines.extend(["## What Worked", ""])
        worked = [attempt for attempt in self.attempts if attempt.confirmed_break]
        if worked:
            lines.extend(f"- `{attempt.strategy}` on `{attempt.seed_id}`" for attempt in worked)
        else:
            lines.append("- No confirmed breaks in this episode.")

        lines.extend(["", "## What Did Not Work", ""])
        failed = [attempt for attempt in self.attempts if not attempt.confirmed_break]
        if failed:
            lines.extend(f"- `{attempt.strategy}` on `{attempt.seed_id}`" for attempt in failed)
        else:
            lines.append("- All recorded attempts produced confirmed breaks.")

        lines.extend(["", "## Conclusions", ""])
        lines.extend(f"- {item}" for item in self.conclusions) if self.conclusions else lines.append("- n/a")

        lines.extend(["", "## Next Potential Attack Ideas", ""])
        lines.extend(f"- {item}" for item in self.next_ideas) if self.next_ideas else lines.append("- n/a")
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, markdown: str) -> "AgentLearningDocument":
        payload = _extract_learning_payload(markdown)
        return cls.from_dict(payload)


class FleetLearningStore:
    """File-backed exchange layer for adversarial-agent learning."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else DEFAULT_LEARNINGS_ROOT
        self.inbox_dir = self.root / "inbox"
        self.fleet_dir = self.root / "fleet"
        self.processed_dir = self.root / "processed"
        self.manifest_path = self.fleet_dir / "processed_manifest.json"
        self.strategy_library_path = self.fleet_dir / "strategy_library.json"
        self.fleet_memory_path = self.fleet_dir / "fleet_memory.md"

    def ensure_directories(self) -> None:
        for directory in (self.inbox_dir, self.fleet_dir, self.processed_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def write_agent_learning(
        self,
        document: AgentLearningDocument,
        filename: str | None = None,
    ) -> Path:
        self.ensure_directories()
        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"{timestamp}__{_slugify(document.agent_id)}.md"
        path = self.inbox_dir / filename
        if path.exists():
            digest = hashlib.sha256(document.render_markdown().encode("utf-8")).hexdigest()[:8]
            path = self.inbox_dir / f"{path.stem}__{digest}{path.suffix}"
        path.write_text(document.render_markdown(), encoding="utf-8")
        return path

    def read_agent_learning(self, path: str | Path) -> AgentLearningDocument:
        return AgentLearningDocument.from_markdown(Path(path).read_text(encoding="utf-8"))

    def list_learning_files(self) -> list[Path]:
        self.ensure_directories()
        return sorted(self.inbox_dir.glob("*.md"))

    def load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": 1, "processed_files": {}, "updates": []}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def read_fleet_context(self) -> dict[str, Any]:
        """Return the memory that attacker agents may read before exploring.

        This intentionally exposes only aggregate fleet memory and the structured
        strategy library. It does not expose inbox reports, processed reports, or
        benchmark rows.
        """
        self.ensure_directories()
        memory = (
            self.fleet_memory_path.read_text(encoding="utf-8")
            if self.fleet_memory_path.exists()
            else DEFAULT_FLEET_MEMORY
        )
        library = self._load_strategy_library()
        return {
            "fleet_memory": memory,
            "strategy_library": library,
            "memory_path": str(self.fleet_memory_path),
            "strategy_library_path": str(self.strategy_library_path),
        }

    def unprocessed_files(self) -> list[Path]:
        manifest = self.load_manifest()
        processed = set(manifest.get("processed_files", {}))
        return [
            path
            for path in self.list_learning_files()
            if self._relative_key(path) not in processed
        ]

    def update_fleet_memory(self) -> dict[str, Any]:
        self.ensure_directories()
        files = self.unprocessed_files()
        documents = [self.read_agent_learning(path) for path in files]
        if not files:
            return {
                "documents_processed": 0,
                "processed_files": [],
                "memory_path": str(self.fleet_memory_path),
                "strategy_library_path": str(self.strategy_library_path),
            }

        library = self._load_strategy_library()
        batch = _summarize_batch(files, documents)
        _merge_documents_into_library(library, files, documents)

        self.strategy_library_path.write_text(
            json.dumps(library, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.fleet_memory_path.write_text(
            _render_fleet_memory(library=library, latest_batch=batch),
            encoding="utf-8",
        )
        self._record_processed(files, batch)
        return {
            "documents_processed": len(files),
            "processed_files": [self._relative_key(path) for path in files],
            "attempts": batch["attempts"],
            "confirmed_breaks": batch["confirmed_breaks"],
            "memory_path": str(self.fleet_memory_path),
            "strategy_library_path": str(self.strategy_library_path),
        }

    def _load_strategy_library(self) -> dict[str, Any]:
        if not self.strategy_library_path.exists():
            return _empty_strategy_library()
        return json.loads(self.strategy_library_path.read_text(encoding="utf-8"))

    def _record_processed(self, files: list[Path], batch: dict[str, Any]) -> None:
        manifest = self.load_manifest()
        processed_files = manifest.setdefault("processed_files", {})
        processed_at = datetime.now(timezone.utc).isoformat()
        for path in files:
            processed_files[self._relative_key(path)] = {
                "sha256": _sha256(path),
                "processed_at": processed_at,
            }
        manifest.setdefault("updates", []).append(
            {
                "processed_at": processed_at,
                "files": [self._relative_key(path) for path in files],
                "documents": batch["documents"],
                "attempts": batch["attempts"],
                "confirmed_breaks": batch["confirmed_breaks"],
            }
        )
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _relative_key(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()


def _extract_learning_payload(markdown: str) -> dict[str, Any]:
    pattern = re.compile(
        rf"{re.escape(LEARNING_BLOCK_START)}\s*(.*?)\s*{re.escape(LEARNING_BLOCK_END)}",
        re.DOTALL,
    )
    match = pattern.search(markdown)
    if not match:
        raise ValueError("Learning document is missing the machine-readable learning block.")
    return json.loads(match.group(1))


def _normalize_transcript(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    transcript: list[dict[str, str]] = []
    for message in value:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", ""))
        content = str(message.get("content", ""))
        if role and content:
            transcript.append({"role": role, "content": content})
    return transcript


def _empty_strategy_library() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "documents_seen": 0,
        "attempts_seen": 0,
        "confirmed_breaks": 0,
        "policies": {},
        "strategies": {},
        "next_ideas": [],
        "source_files": [],
    }


def _merge_documents_into_library(
    library: dict[str, Any],
    files: list[Path],
    documents: list[AgentLearningDocument],
) -> None:
    library["updated_at"] = datetime.now(timezone.utc).isoformat()
    library["documents_seen"] = int(library.get("documents_seen", 0)) + len(documents)
    library.setdefault("policies", {})
    library.setdefault("strategies", {})
    library.setdefault("next_ideas", [])
    library.setdefault("source_files", [])

    for path, document in zip(files, documents, strict=True):
        source_key = path.name
        library["source_files"].append(source_key)
        policy_stats = library["policies"].setdefault(
            document.target_policy,
            {"documents": 0, "attempts": 0, "confirmed_breaks": 0},
        )
        policy_stats["documents"] += 1

        for attempt in document.attempts:
            library["attempts_seen"] = int(library.get("attempts_seen", 0)) + 1
            if attempt.confirmed_break:
                library["confirmed_breaks"] = int(library.get("confirmed_breaks", 0)) + 1

            policy_stats["attempts"] += 1
            policy_stats["confirmed_breaks"] += int(attempt.confirmed_break)

            strategy_stats = library["strategies"].setdefault(
                attempt.strategy,
                {
                    "attempts": 0,
                    "confirmed_breaks": 0,
                    "failures": 0,
                    "policies": {},
                    "source_files": [],
                    "examples": [],
                },
            )
            strategy_stats["attempts"] += 1
            strategy_stats["confirmed_breaks"] += int(attempt.confirmed_break)
            strategy_stats["failures"] += int(not attempt.confirmed_break)
            strategy_stats["source_files"].append(source_key)
            strategy_stats["policies"][attempt.target_policy] = (
                strategy_stats["policies"].get(attempt.target_policy, 0) + 1
            )
            strategy_stats["examples"].append(
                {
                    "seed_id": attempt.seed_id,
                    "target_policy": attempt.target_policy,
                    "confirmed_break": attempt.confirmed_break,
                    "observed_behavior": attempt.observed_behavior,
                    "source_file": source_key,
                }
            )

        for idea in [*document.next_ideas, *[idea for attempt in document.attempts for idea in attempt.next_ideas]]:
            normalized = idea.strip()
            if normalized and not _idea_already_seen(library["next_ideas"], normalized):
                library["next_ideas"].append(
                    {
                        "idea": normalized,
                        "policy": document.target_policy,
                        "source_file": source_key,
                    }
                )


def _summarize_batch(files: list[Path], documents: list[AgentLearningDocument]) -> dict[str, Any]:
    attempts = sum(len(document.attempts) for document in documents)
    confirmed_breaks = sum(document.success_count for document in documents)
    return {
        "documents": len(documents),
        "attempts": attempts,
        "confirmed_breaks": confirmed_breaks,
        "files": [path.name for path in files],
        "policies": sorted({document.target_policy for document in documents}),
        "strategies": sorted(
            {attempt.strategy for document in documents for attempt in document.attempts}
        ),
    }


def _render_fleet_memory(library: dict[str, Any], latest_batch: dict[str, Any]) -> str:
    lines = [
        "# Fleet Learning Memory",
        "",
        f"Updated: `{library.get('updated_at')}`",
        "",
        "## Totals",
        "",
        f"- Learning documents processed: `{library.get('documents_seen', 0)}`",
        f"- Attempts seen: `{library.get('attempts_seen', 0)}`",
        f"- Confirmed denylist breaks: `{library.get('confirmed_breaks', 0)}`",
        "",
        "## Policy Coverage",
        "",
    ]
    policies = library.get("policies", {})
    if policies:
        for policy, stats in sorted(policies.items()):
            lines.append(
                f"- `{policy}`: `{stats['confirmed_breaks']}/{stats['attempts']}` "
                f"confirmed breaks across `{stats['documents']}` document(s)"
            )
    else:
        lines.append("- No policy attempts yet.")

    lines.extend(["", "## Strategy Library", ""])
    strategies = library.get("strategies", {})
    if strategies:
        for strategy, stats in sorted(strategies.items(), key=lambda item: (-item[1]["confirmed_breaks"], item[0])):
            lines.append(
                f"- `{strategy}`: `{stats['confirmed_breaks']}/{stats['attempts']}` "
                f"confirmed breaks, `{stats['failures']}` failure(s), "
                f"policies `{', '.join(sorted(stats['policies']))}`"
            )
    else:
        lines.append("- No strategies recorded yet.")

    lines.extend(["", "## Latest Fleet-Learning Batch", ""])
    lines.extend(
        [
            f"- New learning documents: `{latest_batch['documents']}`",
            f"- New attempts: `{latest_batch['attempts']}`",
            f"- New confirmed breaks: `{latest_batch['confirmed_breaks']}`",
            f"- Files: {', '.join(f'`{file}`' for file in latest_batch['files'])}",
            f"- Policies: {', '.join(f'`{policy}`' for policy in latest_batch['policies']) or '`none`'}",
            f"- Strategies: {', '.join(f'`{strategy}`' for strategy in latest_batch['strategies']) or '`none`'}",
        ]
    )

    lines.extend(["", "## Next Exploration Ideas", ""])
    ideas = library.get("next_ideas", [])[-25:]
    if ideas:
        for item in ideas:
            lines.append(
                f"- `{item['policy']}` from `{item['source_file']}`: {item['idea']}"
            )
    else:
        lines.append("- No next ideas recorded yet.")
    lines.append("")
    return "\n".join(lines)


def _idea_already_seen(items: list[dict[str, str]], idea: str) -> bool:
    return any(item.get("idea", "").casefold() == idea.casefold() for item in items)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return slug or "agent"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fleet learning over new attacker reports.")
    parser.add_argument("--root", default=None, help="Learning root directory.")
    args = parser.parse_args()

    store = FleetLearningStore(root=args.root)
    summary = store.update_fleet_memory()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
