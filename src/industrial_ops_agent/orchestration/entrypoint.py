"""Industrial Reference Application composition for the Temporal worker."""

from __future__ import annotations

from industrial_ops_agent.maintenance_planning.temporal import (
    build_maintenance_planning_worker_registration,
)
from industrial_ops_agent.orchestration.runner import main

if __name__ == "__main__":
    main(build_maintenance_planning_worker_registration)
