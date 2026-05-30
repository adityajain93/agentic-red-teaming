# Company Policy Alignment Skills

These skills guide autoresearch agents that construct attacks against the
`CompanyPolicyAlignmentAgent`.

They are not target-agent prompts. The evaluated target should still receive
only the company policy, prior conversation turns, and the current user query.
Dataset labels, attack goals, judge criteria, and strategy metadata should stay
outside the target prompt.

## Skills

- `denylist_attacker_construction.md` - build adaptive multi-turn adversarial
  users that try to elicit denylist behavior.
- `strategy_research_and_delegation.md` - use web research and Codex
  SDK/subagents to improve attacker strategy construction.
- `use_attack_harness.md` - implement generated attackers against the shared
  episode harness instead of reimplementing target/evaluator plumbing.

## Intended Autoresearch Flow

```text
COMPASS denylist seed
  -> attacker construction skill
  -> stateful attacker strategy
  -> multi-turn conversation against CompanyPolicyAlignmentAgent
  -> label-preservation verifier
  -> behavior judge
  -> scorer
  -> discovered failure / minimal reproducer
```
