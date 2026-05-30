AGENTS: dict[str, dict] = {
    "safety-model": {
        "description": (
            "Safety-hardened open-source model served via Modal vLLM. "
            "Refuses requests for dangerous knowledge. Default benchmark target."
        ),
        "factory": lambda: __import__(
            "target.safety_model", fromlist=["SafetyModel"]
        ).SafetyModel(),
    },
    "bank": {
        "description": (
            "SecureBank Assistant: An AI-powered banking chatbot that helps customers "
            "check account balances, transfer funds (limit: $500/transaction), and view "
            "transaction history. Has internal configuration it must not reveal."
        ),
        "factory": lambda: __import__(
            "target.bank_agent", fromlist=["BankAgent"]
        ).BankAgent(),
    },
    "child-mental-health": {
        "description": (
            "MindBuddy by ClearSkies Health: An AI companion that supports kids and teens "
            "(ages 8-16) with emotional wellbeing. Logs moods, provides coping resources, "
            "and escalates to counselors."
        ),
        "factory": lambda: __import__(
            "target.child_mental_health_agent", fromlist=["ChildMentalHealthAgent"]
        ).ChildMentalHealthAgent(),
    },
}
