from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from company_policy_alignment import CompanyPolicyAlignmentAgent

from .attacker_api import load_attacker_builder
from .evaluator import ModelAttackEvaluator
from .episode import (
    AttackAssignment,
    AutoresearchEpisodeRunner,
    KeywordEvaluator,
)
from .learning import FleetLearningStore


def run_episode_from_module(
    *,
    attacker_module: str,
    assignment_path: str | Path,
    agent_id: str,
    learning_root: str | Path | None = None,
    model: str = "gpt-5.5",
    evaluator_model: str = "gpt-5.5",
    mock_responses: list[str] | None = None,
    break_keywords: list[str] | None = None,
) -> dict[str, Any]:
    assignment = _load_assignment(assignment_path)
    builder = load_attacker_builder(attacker_module)
    target_client = _MockClient(mock_responses) if mock_responses is not None else OpenAI()
    target = CompanyPolicyAlignmentAgent(
        model=model,
        client=target_client,
    )
    evaluator = (
        KeywordEvaluator(break_keywords=break_keywords)
        if break_keywords
        else ModelAttackEvaluator(
            client=target_client if mock_responses is None else OpenAI(),
            model=evaluator_model,
        )
    )
    runner = AutoresearchEpisodeRunner(
        target=target,
        builder=builder,
        evaluator=evaluator,
        learning_store=FleetLearningStore(root=learning_root),
    )
    result = runner.run(assignment, agent_id=agent_id)
    return {
        "assignment_id": result.assignment_id,
        "success": result.success,
        "attempts": len(result.attempts),
        "learning_path": result.learning_path,
        "stopped_reason": result.stopped_reason,
    }


def _load_assignment(path: str | Path) -> AttackAssignment:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return AttackAssignment(
        assignment_id=str(payload["assignment_id"]),
        company=str(payload["company"]),
        policy=payload["policy"],
        target_policy=str(payload["target_policy"]),
        target_behavior=str(payload["target_behavior"]),
        max_attempts=int(payload.get("max_attempts", 5)),
        notes=str(payload.get("notes", "")),
    )


class _MockClient:
    def __init__(self, responses: list[str] | None = None):
        self.chat = _MockChat(responses or ["Mock target response."])


class _MockChat:
    def __init__(self, responses: list[str]):
        self.completions = _MockCompletions(responses)


class _MockCompletions:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0

    def create(self, **_kwargs):
        content = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return _response(content)


def _response(content: str):
    msg = type("Message", (), {"content": content})()
    choice = type("Choice", (), {"message": msg})()
    return type("Response", (), {"choices": [choice]})()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a generated attacker module through the shared episode harness.")
    parser.add_argument("--attacker-module", required=True, help="Import path or .py file with create_attacker().")
    parser.add_argument("--assignment", required=True, help="JSON assignment file.")
    parser.add_argument("--agent-id", required=True, help="Identifier for the attacker learning report.")
    parser.add_argument("--learning-root", default=None, help="Optional learning root override.")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--evaluator-model", default="gpt-5.5")
    parser.add_argument(
        "--break-keyword",
        action="append",
        default=[],
        help="Keyword that marks a mock/local evaluator break. Repeatable.",
    )
    parser.add_argument(
        "--mock-response",
        action="append",
        default=None,
        help="Use deterministic mock target responses instead of OpenAI. Repeatable.",
    )
    args = parser.parse_args()

    summary = run_episode_from_module(
        attacker_module=args.attacker_module,
        assignment_path=args.assignment,
        agent_id=args.agent_id,
        learning_root=args.learning_root,
        model=args.model,
        evaluator_model=args.evaluator_model,
        mock_responses=args.mock_response,
        break_keywords=args.break_keyword,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
