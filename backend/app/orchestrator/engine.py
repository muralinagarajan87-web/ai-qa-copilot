from __future__ import annotations

import json
from datetime import datetime, timezone

from agents.base.registry import AgentNotRegisteredError, AgentRegistry
from agents.base.schemas import ArtifactKind, WorkflowContext, WorkflowState
from backend.app.domain.workflow_run import WorkflowRun
from backend.app.orchestrator.workflow_config import Transition, WorkflowConfig
from backend.app.repositories.interfaces import WorkflowRunRepositoryProtocol
from events.event_bus import EventBusProtocol, WorkflowEvent
from services.artifact_manager import ArtifactManager


class OrchestratorError(RuntimeError):
    pass


class OrchestratorEngine:
    """Walks configuration/workflow.yaml's transition table. Holds no
    knowledge of what a "test case" or a "hard wait" is -- it only knows how
    to ask the registry for an agent, ask that agent to build its own input
    from the shared WorkflowContext, execute it, validate the result, save
    the output as a versioned artifact, and follow the configured next
    state. All per-agent knowledge (which artifact feeds which agent, how to
    branch on Reviewer's verdict) is either config-driven or delegated to
    the agent itself via `build_input` / `output_kind`.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifact_manager: ArtifactManager,
        event_bus: EventBusProtocol,
        config: WorkflowConfig,
        run_repository: WorkflowRunRepositoryProtocol,
    ):
        self.registry = registry
        self.artifact_manager = artifact_manager
        self.event_bus = event_bus
        self.config = config
        self.run_repository = run_repository

    def start_run(self, run_id: str, prd_content: str) -> WorkflowRun:
        prd_ref = self.artifact_manager.save(run_id, ArtifactKind.PRD, prd_content)
        run = WorkflowRun(run_id=run_id, state=WorkflowState.PRD_RECEIVED, artifacts={ArtifactKind.PRD: prd_ref})
        self.run_repository.create(run)
        self.event_bus.publish(WorkflowEvent(type="workflow.started", run_id=run_id, payload={}))
        return self._advance(run)

    def approve(self, run_id: str) -> WorkflowRun:
        run = self._require_run(run_id)
        if run.state is not WorkflowState.AWAITING_APPROVAL:
            raise OrchestratorError(f"Run {run_id} is not awaiting approval (state={run.state.value})")
        run.state = WorkflowState.APPROVED
        return self._advance(run)

    def reject(self, run_id: str, reason: str) -> WorkflowRun:
        run = self._require_run(run_id)
        run.state = WorkflowState.REJECTED
        self._save(run)
        self.event_bus.publish(WorkflowEvent(type="workflow.rejected", run_id=run_id, payload={"reason": reason}))
        return run

    def _advance(self, run: WorkflowRun) -> WorkflowRun:
        while True:
            transition = self.config.transition_for(run.state)
            if transition is None:
                self._save(run)
                return run

            try:
                agent = self.registry.get(transition.agent)
            except AgentNotRegisteredError as exc:
                raise OrchestratorError(str(exc)) from exc
            context = self._context_for(run)
            agent_input = agent.build_input(context)
            output = agent.execute(agent_input, context)

            validation = agent.validate(output)
            if not validation.is_valid:
                raise OrchestratorError(f"{transition.agent} produced invalid output: {validation.errors}")

            artifact_ref = self.artifact_manager.save(run.run_id, agent.output_kind, output.model_dump_json())
            run.artifacts[agent.output_kind] = artifact_ref

            run.state = self._resolve_next_state(transition, output, run)
            self._save(run)

            self.event_bus.publish(
                WorkflowEvent(
                    type=f"{transition.agent}.completed",
                    run_id=run.run_id,
                    payload={"state": run.state.value, "artifact": artifact_ref.path},
                )
            )

    def _resolve_next_state(self, transition: Transition, output, run: WorkflowRun) -> WorkflowState:
        if transition.on_approved is not None and transition.on_rejected is not None:
            # Branching transition (Reviewer today). By convention the
            # agent's output exposes a boolean `approved` field; if a second
            # branching agent is ever added, generalize via an
            # AgentProtocol.outcome(output) -> str hook instead.
            approved = bool(getattr(output, "approved", False))
            if approved:
                return transition.on_approved
            run.revision_count += 1
            if run.revision_count >= self.config.revision.max_attempts:
                return self.config.revision.on_limit_exceeded
            return transition.on_rejected

        assert transition.on_success is not None
        return transition.on_success

    def _context_for(self, run: WorkflowRun) -> WorkflowContext:
        review_comments: list = []
        review_ref = run.artifacts.get(ArtifactKind.REVIEW_COMMENTS)
        if review_ref is not None:
            review_comments = json.loads(self.artifact_manager.load(review_ref)).get("comments", [])
        return WorkflowContext(
            run_id=run.run_id,
            state=run.state,
            previous_outputs=dict(run.artifacts),
            review_comments=review_comments,
            revision_count=run.revision_count,
        )

    def _require_run(self, run_id: str) -> WorkflowRun:
        run = self.run_repository.get(run_id)
        if run is None:
            raise OrchestratorError(f"No such run: {run_id}")
        return run

    def _save(self, run: WorkflowRun) -> None:
        run.updated_at = datetime.now(timezone.utc)
        self.run_repository.update(run)
