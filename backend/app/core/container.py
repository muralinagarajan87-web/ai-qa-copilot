from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from agents.base.registry import AgentRegistry
from backend.app.core.settings import Settings, get_settings
from backend.app.orchestrator.engine import OrchestratorEngine
from backend.app.orchestrator.workflow_config import load_workflow_config
from backend.app.repositories.sqlite_repository import SqliteWorkflowRunRepository
from events.event_bus import InProcessEventBus
from llm.router import LLMRouter
from services.artifact_manager import ArtifactManager
from services.file_service import FileService
from services.git_service import GitService


@dataclass
class Container:
    settings: Settings
    event_bus: InProcessEventBus
    file_service: FileService
    artifact_manager: ArtifactManager
    git_service: GitService
    llm_router: LLMRouter
    agent_registry: AgentRegistry
    orchestrator: OrchestratorEngine


def _load_agent_class(dotted: str):
    module_path, class_name = dotted.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_container(settings: Settings | None = None) -> Container:
    """Wires the whole system per docs/architecture/design.md. This is the
    only place that knows how everything is constructed -- every other
    module receives its dependencies through its constructor.
    """
    settings = settings or get_settings()

    event_bus = InProcessEventBus()
    file_service = FileService(root=settings.repo_root)
    artifact_manager = ArtifactManager(file_service)
    git_service = GitService()
    llm_router = LLMRouter(config_path=settings.models_config)

    registry = AgentRegistry()
    agents_config = yaml.safe_load(settings.agents_config.read_text()) or {}
    for agent_name, entry in (agents_config.get("agents") or {}).items():
        agent_cls = _load_agent_class(entry["module"])
        agent_dir = settings.repo_root / Path(entry["config"]).parent

        def factory(agent_cls=agent_cls, agent_dir=agent_dir, agent_name=agent_name):
            return agent_cls(
                agent_dir=agent_dir,
                llm=llm_router.get_provider(agent_name),
                event_bus=event_bus,
                artifact_manager=artifact_manager,
                max_retries=settings.max_agent_retries,
            )

        registry.register(agent_name, factory)

    run_repository = SqliteWorkflowRunRepository(settings.db_path)
    workflow_config = load_workflow_config(settings.workflow_config)
    orchestrator = OrchestratorEngine(
        registry=registry,
        artifact_manager=artifact_manager,
        event_bus=event_bus,
        config=workflow_config,
        run_repository=run_repository,
    )

    return Container(
        settings=settings,
        event_bus=event_bus,
        file_service=file_service,
        artifact_manager=artifact_manager,
        git_service=git_service,
        llm_router=llm_router,
        agent_registry=registry,
        orchestrator=orchestrator,
    )
