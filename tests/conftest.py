import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def no_openai_key():
    """Prevent OpenAI() constructor from requiring OPENAI_API_KEY in all tests."""
    dummy = MagicMock()
    with patch("red_team.attacker.OpenAI", return_value=dummy), \
         patch("red_team.orchestrator.OpenAI", return_value=dummy), \
         patch("target.bank_agent.OpenAI", return_value=dummy):
        yield
