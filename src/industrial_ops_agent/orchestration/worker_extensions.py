"""Generic composition values for optional Temporal worker registrations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

from industrial_ops_agent.config import Settings
from industrial_ops_agent.model_gateway.service import ModelGateway
from industrial_ops_agent.persistence.database import Database


@dataclass(frozen=True, slots=True)
class TemporalWorkerRuntime:
    settings: Settings
    database: Database
    model_gateway: ModelGateway


@dataclass(frozen=True, slots=True)
class TemporalWorkerRegistration:
    workflows: tuple[type[Any], ...]
    activities: tuple[Callable[..., Any], ...]


TemporalWorkerRegistrationFactory: TypeAlias = Callable[
    [TemporalWorkerRuntime], TemporalWorkerRegistration | None
]
