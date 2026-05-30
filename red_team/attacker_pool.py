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

    async def run_round(self, target, target_description: str, interaction=None) -> list[AttackResult]:
        """Run all active attackers concurrently for one round."""
        active = [a for a in self.attackers.values() if a.status != "done"]
        tasks = [self._run_one(a, target, target_description, interaction) for a in active]
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
        self, attacker: AttackerAgent, target, target_description: str, interaction=None
    ) -> AttackResult:
        attacker.status = "running"
        previous = [r.attack_prompt for r in attacker.results]

        t0 = time.perf_counter()
        attack_prompt = await asyncio.to_thread(
            attacker.generate_attack, target_description, previous
        )
        if interaction:
            interaction.track_tool(
                name="generate_attack",
                input={"attack_type": attacker.attack_type, "target": target_description},
                output=attack_prompt,
                duration_ms=(time.perf_counter() - t0) * 1000,
                properties={"attacker": attacker.name, "attack_type": attacker.attack_type},
            )

        t1 = time.perf_counter()
        target_result = await asyncio.to_thread(target.chat, attack_prompt)
        if interaction:
            interaction.track_tool(
                name="target_chat",
                input=attack_prompt,
                output=target_result["response"],
                duration_ms=(time.perf_counter() - t1) * 1000,
                properties={
                    "attacker": attacker.name,
                    "bank_tool_calls": len(target_result["tool_calls"]),
                },
            )

        t2 = time.perf_counter()
        result = await asyncio.to_thread(
            attacker.analyze_response,
            attack_prompt,
            target_result["response"],
            target_result["tool_calls"],
        )
        if interaction:
            interaction.track_tool(
                name="analyze_response",
                input={"prompt": attack_prompt, "response": target_result["response"]},
                output={"success": result.success, "vulnerability": result.vulnerability_found, "severity": result.severity},
                duration_ms=(time.perf_counter() - t2) * 1000,
                properties={
                    "attacker": attacker.name,
                    "success": result.success,
                    "severity": result.severity,
                },
            )

        attacker.results.append(result)
        attacker.turns += 1
        attacker.status = "success" if result.success else "running"
        return result

    def delete_all(self):
        self.attackers.clear()
