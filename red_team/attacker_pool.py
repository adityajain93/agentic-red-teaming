import asyncio
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

    async def run_round(self, target, target_description: str) -> list[AttackResult]:
        """Run all active attackers concurrently for one round."""
        active = [a for a in self.attackers.values() if a.status != "done"]
        tasks = [self._run_one(a, target, target_description) for a in active]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, AttackResult)]

    async def _run_one(
        self, attacker: AttackerAgent, target, target_description: str
    ) -> AttackResult:
        attacker.status = "running"
        previous = [r.attack_prompt for r in attacker.results]

        attack_prompt = await asyncio.to_thread(
            attacker.generate_attack, target_description, previous
        )
        target_result = await asyncio.to_thread(target.chat, attack_prompt)
        result = await asyncio.to_thread(
            attacker.analyze_response,
            attack_prompt,
            target_result["response"],
            target_result["tool_calls"],
        )

        attacker.results.append(result)
        attacker.turns += 1
        attacker.status = "success" if result.success else "running"
        return result

    def delete_all(self):
        self.attackers.clear()
