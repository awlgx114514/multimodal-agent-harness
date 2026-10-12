"""Industrial Diagnosis mapping into the generic knowledge applicability contract."""

from __future__ import annotations

from industrial_ops_agent.knowledge.applicability import ApplicabilityFilter

INDUSTRIAL_FAMILY_KEY = "equipment.family"
INDUSTRIAL_MODEL_KEY = "equipment.model"
_UNSPECIFIED_FAMILY = "__industrial_family_unspecified__"


def industrial_applicability(
    device_family: str | None,
    device_model: str | None,
) -> tuple[ApplicabilityFilter, ...]:
    result: list[ApplicabilityFilter] = []
    result.append(
        ApplicabilityFilter(
            INDUSTRIAL_FAMILY_KEY,
            frozenset({device_family} if device_family else {_UNSPECIFIED_FAMILY}),
        )
    )
    if device_model:
        result.append(ApplicabilityFilter(INDUSTRIAL_MODEL_KEY, frozenset({device_model})))
    return tuple(result)


def industrial_applicability_from_legacy(
    device_families: tuple[str, ...],
    device_models: tuple[str, ...],
) -> tuple[ApplicabilityFilter, ...]:
    result: list[ApplicabilityFilter] = []
    if device_families:
        result.append(ApplicabilityFilter(INDUSTRIAL_FAMILY_KEY, frozenset(device_families)))
    if device_models:
        result.append(ApplicabilityFilter(INDUSTRIAL_MODEL_KEY, frozenset(device_models)))
    return tuple(result)


__all__ = [
    "INDUSTRIAL_FAMILY_KEY",
    "INDUSTRIAL_MODEL_KEY",
    "industrial_applicability",
    "industrial_applicability_from_legacy",
]
