import asyncio
import time
from .attacker import AttackerAgent, AttackResult


class AttackerPool:
    """Manages a pool of concurrent attacker agents — mirrors the subagent pool pattern."""

    def __init__(self):
        self.attackers: dict[str, AttackerAgent] = {}
        self._counter = 0

    def spawn(self, attack_type: str, skill_content: str = "") -> AttackerAgent:
        self._counter += 1
        name = f"attacker-{self._counter:02d}"
        attacker = AttackerAgent(name, attack_type, skill_content)
        self.attackers[name] = attacker
        return attacker

    async def run_round(
        self, target, target_description: str, interaction=None, max_turns: int = 1
    ) -> list[AttackResult]:
        """Run all active attackers concurrently for one round."""
        active = [a for a in self.attackers.values() if a.status != "done"]
        tasks = [self._run_one(a, target, target_description, interaction, max_turns) for a in active]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for r in raw:
            if isinstance(r, AttackResult):
                results.append(r)
            elif isinstance(r, Exception):
                import traceback
                print(f"[attacker error] {type(r).__name__}: {r}")
                traceback.print_exc()
        return results

    async def _run_one(
        self, attacker: AttackerAgent, target, target_description: str, interaction=None, max_turns: int = 1
    ) -> AttackResult:
        attacker.status = "running"
        previous = [r.attack_prompt for r in attacker.results]
        conversation_history: list[dict] = []
        all_tool_calls: list[dict] = []
        last_result: AttackResult | None = None

        for turn in range(max_turns):
            t0 = time.perf_counter()
            attack_prompt = await asyncio.to_thread(
                attacker.generate_attack, target_description, previous, conversation_history or None
            )
            if interaction:
                interaction.track_tool(
                    name="generate_attack",
                    input={"attack_type": attacker.attack_type, "target": target_description, "turn": turn + 1},
                    output=attack_prompt,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    properties={"attacker": attacker.name, "attack_type": attacker.attack_type, "turn": turn + 1},
                )

            t1 = time.perf_counter()
            target_result = await asyncio.to_thread(target.chat, attack_prompt, conversation_history or None)
            all_tool_calls.extend(target_result["tool_calls"])
            if interaction:
                interaction.track_tool(
                    name="target_chat",
                    input=attack_prompt,
                    output=target_result["response"],
                    duration_ms=(time.perf_counter() - t1) * 1000,
                    properties={
                        "attacker": attacker.name,
                        "bank_tool_calls": len(target_result["tool_calls"]),
                        "turn": turn + 1,
                    },
                )

            conversation_history.append({"role": "user", "content": attack_prompt})
            conversation_history.append({"role": "assistant", "content": target_result["response"]})

            t2 = time.perf_counter()
            last_result = await asyncio.to_thread(
                attacker.analyze_response,
                attack_prompt,
                target_result["response"],
                target_result["tool_calls"],
            )
            if interaction:
                interaction.track_tool(
                    name="analyze_response",
                    input={"prompt": attack_prompt, "response": target_result["response"]},
                    output={"success": last_result.success, "vulnerability": last_result.vulnerability_found, "severity": last_result.severity},
                    duration_ms=(time.perf_counter() - t2) * 1000,
                    properties={
                        "attacker": attacker.name,
                        "success": last_result.success,
                        "severity": last_result.severity,
                        "turn": turn + 1,
                    },
                )

            attacker.turns += 1
            if last_result.success:
                break

        # If no single turn flagged a success, run the LLM judge over the full conversation.
        if not last_result.success and max_turns > 1:
            t3 = time.perf_counter()
            conv_result = await asyncio.to_thread(
                attacker.analyze_conversation, conversation_history, all_tool_calls
            )
            if interaction:
                interaction.track_tool(
                    name="analyze_conversation",
                    input={"turns": len(conversation_history) // 2},
                    output={"success": conv_result.success, "vulnerability": conv_result.vulnerability_found, "severity": conv_result.severity},
                    duration_ms=(time.perf_counter() - t3) * 1000,
                    properties={"attacker": attacker.name, "success": conv_result.success},
                )
            if conv_result.success:
                last_result = conv_result

        attacker.results.append(last_result)
        attacker.status = "success" if last_result.success else "running"
        return last_result

    def delete_all(self):
        self.attackers.clear()
