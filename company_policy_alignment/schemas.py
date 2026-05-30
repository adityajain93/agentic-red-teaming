from dataclasses import dataclass
from typing import Any, Mapping


COMPASS_ROW_FIELDS = (
    "id",
    "query_type",
    "query",
    "category",
    "policy",
    "attack_variation",
    "company",
)


class PolicyValidationError(ValueError):
    """Raised when a company policy is not in the expected COMPASS shape."""


class QueryValidationError(ValueError):
    """Raised when a question or COMPASS row cannot be used as a query."""


@dataclass(frozen=True)
class CompassQuery:
    """Normalized representation of a COMPASS-style dataset row."""

    query: str
    id: str | None = None
    query_type: str | None = None
    category: str | None = None
    policy: str | None = None
    attack_variation: str | None = None
    company: str | None = None

    @classmethod
    def from_input(cls, question: str | Mapping[str, Any]) -> "CompassQuery":
        if isinstance(question, str):
            query = question.strip()
            if not query:
                raise QueryValidationError("Question must not be empty.")
            return cls(query=query)

        if not isinstance(question, Mapping):
            raise QueryValidationError("Question must be a string or COMPASS-style row mapping.")

        raw_query = question.get("query")
        if not isinstance(raw_query, str) or not raw_query.strip():
            raise QueryValidationError("COMPASS row must include a non-empty 'query' field.")

        return cls(
            id=_optional_str(question.get("id")),
            query_type=_optional_str(question.get("query_type")),
            query=raw_query.strip(),
            category=_optional_str(question.get("category")),
            policy=_optional_str(question.get("policy")),
            attack_variation=_optional_str(question.get("attack_variation")),
            company=_optional_str(question.get("company")),
        )

    def as_compass_row(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "query_type": self.query_type,
            "query": self.query,
            "category": self.category,
            "policy": self.policy,
            "attack_variation": self.attack_variation,
            "company": self.company,
        }


def validate_policy(policy: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    if not isinstance(policy, Mapping):
        raise PolicyValidationError("Policy must be a mapping.")

    normalized: dict[str, dict[str, str]] = {}
    for section in ("allowlist", "denylist"):
        value = policy.get(section)
        if not isinstance(value, Mapping):
            raise PolicyValidationError(f"Policy must include a '{section}' mapping.")

        normalized[section] = {}
        for name, description in value.items():
            if not isinstance(name, str) or not name.strip():
                raise PolicyValidationError(f"Policy '{section}' contains an invalid category name.")
            if not isinstance(description, str) or not description.strip():
                raise PolicyValidationError(
                    f"Policy '{section}.{name}' must have a non-empty string description."
                )
            normalized[section][name.strip()] = description.strip()

    return normalized


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    value = value.strip()
    return value or None
