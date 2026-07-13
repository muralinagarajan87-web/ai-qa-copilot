from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from agents.base.schemas import ArtifactKind
from backend.app.api.deps import get_container
from backend.app.core.container import Container
from backend.app.domain.revision_history import RevisionHistory, RevisionHistoryBuilder
from backend.app.domain.traceability import TraceabilityMatrix, TraceabilityMatrixBuilder
from backend.app.domain.workflow_run import WorkflowRun
from backend.app.orchestrator.engine import OrchestratorError
from services.interfaces import DiffResult

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowRun)
def create_workflow(prd: UploadFile, container: Container = Depends(get_container)) -> WorkflowRun:
    content = prd.file.read().decode("utf-8")
    run_id = uuid.uuid4().hex[:12]
    try:
        return container.orchestrator.start_run(run_id, content)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[WorkflowRun])
def list_workflows(container: Container = Depends(get_container)) -> list[WorkflowRun]:
    return container.orchestrator.run_repository.list()


@router.get("/{run_id}", response_model=WorkflowRun)
def get_workflow(run_id: str, container: Container = Depends(get_container)) -> WorkflowRun:
    run = container.orchestrator.run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")
    return run


@router.post("/{run_id}/approve", response_model=WorkflowRun)
def approve_workflow(run_id: str, container: Container = Depends(get_container)) -> WorkflowRun:
    try:
        return container.orchestrator.approve(run_id)
    except OrchestratorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/reject", response_model=WorkflowRun)
def reject_workflow(run_id: str, reason: str = "", container: Container = Depends(get_container)) -> WorkflowRun:
    try:
        return container.orchestrator.reject(run_id, reason)
    except OrchestratorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/artifacts/{kind}/versions")
def list_artifact_versions(run_id: str, kind: ArtifactKind, container: Container = Depends(get_container)):
    return container.artifact_manager.list_versions(run_id, kind)


@router.get("/{run_id}/artifacts/{kind}/latest")
def get_latest_artifact(run_id: str, kind: ArtifactKind, container: Container = Depends(get_container)) -> dict:
    versions = container.artifact_manager.list_versions(run_id, kind)
    if not versions:
        raise HTTPException(status_code=404, detail=f"No '{kind.value}' artifact yet for run {run_id}")
    return json.loads(container.artifact_manager.load(versions[-1]))


@router.get("/{run_id}/artifacts/{kind}/diff", response_model=DiffResult)
def diff_artifact_versions(
    run_id: str, kind: ArtifactKind, a: int, b: int, container: Container = Depends(get_container)
) -> DiffResult:
    versions = {ref.version: ref for ref in container.artifact_manager.list_versions(run_id, kind)}
    if a not in versions or b not in versions:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    return container.artifact_manager.compare(versions[a], versions[b])


@router.get("/{run_id}/history", response_model=RevisionHistory)
def get_revision_history(run_id: str, container: Container = Depends(get_container)) -> RevisionHistory:
    run = container.orchestrator.run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")
    builder = RevisionHistoryBuilder(container.artifact_manager)
    return builder.build(
        run_id,
        max_attempts=container.orchestrator.config.revision.max_attempts,
        run_state=run.state,
    )


@router.get("/{run_id}/traceability", response_model=TraceabilityMatrix)
def get_traceability_matrix(run_id: str, container: Container = Depends(get_container)) -> TraceabilityMatrix:
    run = container.orchestrator.run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")
    builder = TraceabilityMatrixBuilder(container.artifact_manager)
    return builder.build(run_id, run_state=run.state)


@router.get("/{run_id}/test-cases/report")
def get_test_cases_report(run_id: str, container: Container = Depends(get_container)) -> PlainTextResponse:
    path = f"artifacts/runs/{run_id}/test_cases/Manual_TestCases.md"
    try:
        content = container.file_service.read(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No manual test case report yet for this run") from exc
    return PlainTextResponse(content, media_type="text/markdown")


@router.get("/{run_id}/llm-calls")
def get_llm_calls(run_id: str, container: Container = Depends(get_container)) -> list[dict]:
    calls: list[dict] = []
    for agent_name in container.agent_registry.list_agents():
        agent = container.agent_registry.get(agent_name)
        calls.extend(agent.read_llm_calls(run_id))
    calls.sort(key=lambda call: call.get("timestamp", ""))
    return calls
