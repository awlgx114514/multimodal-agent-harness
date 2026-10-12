"""Temporal transport owned by the Maintenance Planning reference application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from temporalio.common import RetryPolicy
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from industrial_ops_agent.auth.identity import IdentityContext, Role
    from industrial_ops_agent.maintenance_planning.service import (
        MaintenancePlanningActivity,
        MaintenancePlanningActivityInput,
        MaintenancePlanningDispatchUnavailable,
    )
    from industrial_ops_agent.orchestration.worker_extensions import (
        TemporalWorkerRegistration,
        TemporalWorkerRuntime,
    )
    from industrial_ops_agent.orchestration.workflows import LazyTemporalClient


@dataclass(frozen=True, slots=True)
class MaintenancePlanningWorkflowInput:
    council_id: str
    workflow_id: str
    subject_id: str
    oidc_subject: str
    tenant_id: str
    roles: tuple[str, ...]
    asset_ids: tuple[str, ...]
    site_ids: tuple[str, ...]
    issued_at: str
    expires_at: str
    request_id: str


class TemporalMaintenancePlanningActivity:
    def __init__(self, delegate: MaintenancePlanningActivity) -> None:
        self._delegate = delegate

    @activity.defn(name="maintenance_planning_council_activity")
    async def execute(self, command: MaintenancePlanningWorkflowInput) -> dict[str, Any]:
        identity = IdentityContext(
            subject_id=command.subject_id,
            oidc_subject=command.oidc_subject,
            tenant_id=command.tenant_id,
            roles=frozenset(Role(value) for value in command.roles),
            asset_ids=frozenset(command.asset_ids),
            site_ids=frozenset(command.site_ids),
            issued_at=datetime.fromisoformat(command.issued_at),
            expires_at=datetime.fromisoformat(command.expires_at),
        )
        result = await self._delegate.execute(
            MaintenancePlanningActivityInput(
                council_id=command.council_id,
                workflow_id=command.workflow_id,
                identity=identity,
                request_id=command.request_id,
            )
        )
        return {
            "council_id": result.council_id,
            "status": result.status,
            "stage": result.stage,
            "failure_code": result.failure_code,
            "version": result.version,
        }


@workflow.defn(name="maintenance_planning_council_workflow")
class MaintenancePlanningWorkflow:
    @workflow.run
    async def run(self, command: MaintenancePlanningWorkflowInput) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await workflow.execute_activity(
                "maintenance_planning_council_activity",
                command,
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=3),
                    maximum_attempts=3,
                    maximum_interval=timedelta(seconds=30),
                ),
            ),
        )


@dataclass(slots=True)
class LazyTemporalMaintenancePlanningDispatcher:
    provider: LazyTemporalClient
    task_queue: str = "industrial-ops-m2"

    async def dispatch(self, command: MaintenancePlanningActivityInput) -> None:
        identity = command.identity
        payload = MaintenancePlanningWorkflowInput(
            council_id=command.council_id,
            workflow_id=command.workflow_id,
            subject_id=identity.subject_id,
            oidc_subject=identity.oidc_subject,
            tenant_id=identity.tenant_id,
            roles=tuple(sorted(role.value for role in identity.roles)),
            asset_ids=tuple(sorted(identity.asset_ids)),
            site_ids=tuple(sorted(identity.site_ids)),
            issued_at=identity.issued_at.isoformat(),
            expires_at=identity.expires_at.isoformat(),
            request_id=command.request_id,
        )
        try:
            client = await self.provider.get()
            await client.start_workflow(
                MaintenancePlanningWorkflow.run,
                payload,
                id=command.workflow_id,
                task_queue=self.task_queue,
            )
        except WorkflowAlreadyStartedError:
            return
        except Exception as exc:
            raise MaintenancePlanningDispatchUnavailable from exc


def build_maintenance_planning_worker_registration(
    runtime: TemporalWorkerRuntime,
) -> TemporalWorkerRegistration | None:
    if not runtime.settings.multi_agent_planning_enabled:
        return None
    activity_adapter = TemporalMaintenancePlanningActivity(
        MaintenancePlanningActivity(
            runtime.database,
            runtime.model_gateway,
            timeout_seconds=runtime.settings.maintenance_planning_timeout_seconds,
        )
    )
    return TemporalWorkerRegistration(
        workflows=(MaintenancePlanningWorkflow,),
        activities=(activity_adapter.execute,),
    )
