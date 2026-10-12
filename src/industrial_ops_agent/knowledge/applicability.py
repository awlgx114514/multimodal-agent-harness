"""Minimal key/value applicability contract for reusable Knowledge retrieval."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicabilityFilter:
    """One exact-match filter; an absent document key is intentionally open."""

    key: str
    values: frozenset[str]

    def __post_init__(self) -> None:
        if (
            not self.key.strip()
            or not self.values
            or any(not value.strip() for value in self.values)
        ):
            raise ValueError("applicability filter is invalid")

    def matches(self, document: Mapping[str, Iterable[str]]) -> bool:
        values = frozenset(document.get(self.key, ()))
        return not values or bool(values.intersection(self.values))

    def as_dict(self) -> dict[str, object]:
        return {"key": self.key, "values": sorted(self.values)}


def matches_all(
    document: Mapping[str, Iterable[str]],
    filters: Iterable[ApplicabilityFilter],
) -> bool:
    return all(item.matches(document) for item in filters)


def normalize(value: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, values in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("applicability key is invalid")
        normalized = sorted({item for item in values if isinstance(item, str) and item.strip()})
        if normalized:
            result[key] = normalized
    return result
