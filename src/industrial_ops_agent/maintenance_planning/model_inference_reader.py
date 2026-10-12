"""Maintenance-policy disclosure for the Industrial Model Inference audit view."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.maintenance_planning.review_isolation import (
    diagnosis_for_agent,
    record_disclosure,
)
from industrial_ops_agent.model_gateway.governance import ModelGatewayGovernanceService
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    MaintenancePlanningContributionRecord,
    MaintenancePlanningCouncilRecord,
    ModelInferenceRecord,
)


class MaintenancePlanningInferenceReader:
    """Keep Maintenance Review disclosure atomic with the generic inference read."""

    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self._database = database
        self._gateway = ModelGatewayGovernanceService(database, authorizer)

    def list_inferences(
        self,
        identity: IdentityContext,
        *,
        request_id: str,
        limit: int = 50,
    ) -> Sequence[ModelInferenceRecord]:
        with self._database.transaction(identity.tenant_context) as session:
            records = self._gateway.list_inferences(
                identity,
                request_id=request_id,
                limit=limit,
                session=session,
            )
            diagnosis_ids: set[str] = set()
            for record in records:
                if record.diagnosis_run_id is not None:
                    diagnosis_ids.add(record.diagnosis_run_id)
                if record.agent_run_id is not None:
                    diagnosis_ids.add(
                        diagnosis_for_agent(session, identity.tenant_id, record.agent_run_id)
                    )
            diagnosis_ids.update(
                session.scalars(
                    select(MaintenancePlanningCouncilRecord.diagnosis_run_id)
                    .join(
                        MaintenancePlanningContributionRecord,
                        (
                            MaintenancePlanningContributionRecord.tenant_id
                            == MaintenancePlanningCouncilRecord.tenant_id
                        )
                        & (
                            MaintenancePlanningContributionRecord.council_id
                            == MaintenancePlanningCouncilRecord.council_id
                        ),
                    )
                    .where(
                        MaintenancePlanningCouncilRecord.tenant_id == identity.tenant_id,
                        MaintenancePlanningContributionRecord.inference_request_id.in_(
                            [record.inference_request_id for record in records]
                        ),
                    )
                )
            )
            record_disclosure(
                session,
                identity,
                diagnosis_ids,
                resource_kind="model-inference-list",
                resource_id="model-inferences",
                request_id=request_id,
            )
            return records
