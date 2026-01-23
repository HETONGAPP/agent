"""
Diagnostic Executor
Executes diagnostic tasks from TaskManager
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

from .task_manager import DiagnosticTaskManager, DiagnosticTask, TaskStatus
from .base import BaseDiagnosticAgent

logger = logging.getLogger(__name__)


class DiagnosticExecutor:
    """Diagnostic task execution engine"""

    def __init__(
        self,
        task_manager: DiagnosticTaskManager,
        agents: Dict[str, BaseDiagnosticAgent],
        context: Optional[Dict[str, Any]] = None,
        websocket_manager=None,
        diagnostic_id: Optional[str] = None,
    ):
        """
        Initialize diagnostic executor

        Args:
            task_manager: DiagnosticTaskManager instance
            agents: Dictionary of agents {"AgentName": agent_instance}
            context: Shared context (site_id, time_range, etc.)
            websocket_manager: Optional WebSocket manager for real-time updates
            diagnostic_id: Optional diagnostic session ID
        """
        self.task_manager = task_manager
        self.agents = agents
        self.context = context or {}
        self.websocket_manager = websocket_manager
        self.diagnostic_id = diagnostic_id or f"diagnostic_{id(self)}"
        logger.info(f"Diagnostic executor initialized with {len(agents)} agents")

    async def execute_ready_tasks(self) -> List[Dict[str, Any]]:
        """
        Execute all ready tasks (dependencies satisfied)

        Executes tasks in batches, with parallel execution within each batch.
        Continues until no more ready tasks are available.

        Returns:
            List of execution results
        """
        all_results = []

        # Broadcast initial task list
        await self._broadcast_task_list()

        # Loop until no more ready tasks
        while True:
            ready_tasks = self.task_manager.get_ready_tasks()

            if not ready_tasks:
                break

            logger.info(f"Executing batch of {len(ready_tasks)} ready tasks")

            # Broadcast batch start
            await self._broadcast_batch_start(ready_tasks)

            # Execute current batch in parallel
            results = await asyncio.gather(
                *[self._execute_task(task) for task in ready_tasks],
                return_exceptions=True
            )

            # Process results and exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task = ready_tasks[i]
                    result_dict = {
                        "task_id": task.task_id,
                        "description": task.description,
                        "agent": task.agent,
                        "error": str(result)
                    }
                    all_results.append(result_dict)
                    self.task_manager.mark_failed(task.task_id, str(result))
                    await self._broadcast_task_update(task)
                else:
                    all_results.append(result)
                    task = ready_tasks[i]
                    await self._broadcast_task_update(task)

        # Broadcast completion
        await self._broadcast_complete(all_results)

        return all_results

    async def execute_one_batch(self) -> tuple[List[DiagnosticTask], List[Dict[str, Any]]]:
        """
        Execute only the currently ready tasks (one batch)

        Returns:
            Tuple of (ready_tasks, results)
        """
        ready_tasks = self.task_manager.get_ready_tasks()

        if not ready_tasks:
            return [], []

        logger.info(f"Executing one batch of {len(ready_tasks)} ready tasks")

        # Execute current batch in parallel
        raw_results = await asyncio.gather(
            *[self._execute_task(task) for task in ready_tasks],
            return_exceptions=True
        )

        # Process results and exceptions
        results = []
        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                task = ready_tasks[i]
                result_dict = {
                    "task_id": task.task_id,
                    "description": task.description,
                    "agent": task.agent,
                    "error": str(result)
                }
                results.append(result_dict)
                self.task_manager.mark_failed(task.task_id, str(result))
            else:
                results.append(result)

        return ready_tasks, results

    async def _execute_task(self, task: DiagnosticTask) -> Dict[str, Any]:
        """
        Execute a single diagnostic task

        Args:
            task: Task to execute

        Returns:
            Execution result dictionary
        """
        # Mark as executing
        self.task_manager.mark_executing(task.task_id)
        await self._broadcast_task_update(task)
        await self._broadcast_agent_status(task.agent, "working", task.task_id)

        try:
            # Build task context
            task_context = self._build_task_context(task)

            # Get dependency results
            dependency_results = self._get_dependency_results(task)

            # Get agent
            agent = self.agents.get(task.agent)
            if not agent:
                raise ValueError(f"Unknown agent: {task.agent}")

            logger.info(f"Executing task {task.task_id} with agent {task.agent}")

            # Execute task through agent
            result = await agent.analyze(task_context, dependency_results)

            # Mark as completed
            self.task_manager.mark_completed(task.task_id, result)
            await self._broadcast_task_update(task)
            await self._broadcast_agent_status(task.agent, "complete", task.task_id)

            return {
                "task_id": task.task_id,
                "description": task.description,
                "agent": task.agent,
                "result": result
            }

        except Exception as e:
            # Mark as failed
            error_msg = str(e)
            logger.error(f"Task {task.task_id} failed: {error_msg}", exc_info=True)
            self.task_manager.mark_failed(task.task_id, error_msg)
            await self._broadcast_task_update(task)
            await self._broadcast_agent_status(task.agent, "error", task.task_id, error_msg)

            return {
                "task_id": task.task_id,
                "description": task.description,
                "agent": task.agent,
                "error": error_msg
            }

    def _build_task_context(self, task: DiagnosticTask) -> Dict[str, Any]:
        """Build context for task execution"""
        context = {
            **self.context,  # Include shared context (site_id, time_range, etc.)
            "task_id": task.task_id,
            "task_description": task.description,
        }
        return context

    def _get_dependency_results(self, task: DiagnosticTask) -> List[Dict[str, Any]]:
        """Get results from dependency tasks"""
        dependency_results = []
        for dep_id in task.dependencies:
            dep_task = self.task_manager.get_task(dep_id)
            if dep_task and dep_task.status == TaskStatus.COMPLETED:
                dependency_results.append({
                    "task_id": dep_task.task_id,
                    "description": dep_task.description,
                    "result": dep_task.result,
                })
            elif dep_task and dep_task.status == TaskStatus.FAILED:
                dependency_results.append({
                    "task_id": dep_task.task_id,
                    "description": dep_task.description,
                    "error": dep_task.error,
                })
        return dependency_results

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """Format execution results for logging"""
        if not results:
            return "No tasks were executed"

        lines = ["Diagnostic Task Execution Results:\n"]

        for result in results:
            task_id = result.get("task_id", "unknown")
            description = result.get("description", "")
            agent = result.get("agent", "")

            lines.append(f"### Task {task_id}")
            lines.append(f"Description: {description}")
            lines.append(f"Agent: {agent}")

            if "result" in result:
                result_data = result["result"]
                if isinstance(result_data, dict):
                    lines.append(f"Result: {result_data.get('status', 'success')}")
                    if "analysis" in result_data:
                        analysis = result_data["analysis"]
                        preview = analysis[:200] + "..." if len(str(analysis)) > 200 else analysis
                        lines.append(f"Analysis: {preview}")
                else:
                    lines.append(f"Result: {result_data}")
            elif "error" in result:
                lines.append(f"Failed: {result['error']}")

            lines.append("")  # Empty line separator

        return "\n".join(lines)

    async def _broadcast_task_list(self):
        """Broadcast initial task list"""
        if not self.websocket_manager:
            return

        try:
            from ...agent.websocket_manager import EventType

            tasks_data = []
            for task in self.task_manager.tasks:
                tasks_data.append({
                    "task_id": task.task_id,
                    "agent": task.agent,
                    "description": task.description,
                    "dependencies": task.dependencies,
                    "status": task.status.value,
                })

            await self.websocket_manager.broadcast(
                EventType.DIAGNOSTIC_TASK_CREATED,
                {
                    "diagnostic_id": self.diagnostic_id,
                    "site_id": self.context.get("site_id"),
                    "tasks": tasks_data,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting task list: {e}")

    async def _broadcast_batch_start(self, ready_tasks: List[DiagnosticTask]):
        """Broadcast batch execution start"""
        if not self.websocket_manager:
            return

        try:
            from ...agent.websocket_manager import EventType

            await self.websocket_manager.broadcast(
                EventType.DIAGNOSTIC_MESSAGE,
                {
                    "diagnostic_id": self.diagnostic_id,
                    "message": f"Starting batch execution: {len(ready_tasks)} tasks",
                    "level": "info",
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting batch start: {e}")

    async def _broadcast_task_update(self, task: DiagnosticTask):
        """Broadcast task status update"""
        if not self.websocket_manager:
            return

        try:
            from ...agent.websocket_manager import EventType

            await self.websocket_manager.broadcast(
                EventType.DIAGNOSTIC_TASK_UPDATED,
                {
                    "diagnostic_id": self.diagnostic_id,
                    "task_id": task.task_id,
                    "agent": task.agent,
                    "status": task.status.value,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "error": task.error,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting task update: {e}")

    async def _broadcast_agent_status(
        self, agent_name: str, status: str, task_id: Optional[str] = None, error: Optional[str] = None
    ):
        """Broadcast agent status update"""
        if not self.websocket_manager:
            return

        try:
            from ...agent.websocket_manager import EventType

            await self.websocket_manager.broadcast(
                EventType.DIAGNOSTIC_AGENT_STATUS,
                {
                    "diagnostic_id": self.diagnostic_id,
                    "agent": agent_name,
                    "status": status,
                    "task_id": task_id,
                    "error": error,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting agent status: {e}")

    async def _broadcast_complete(self, results: List[Dict[str, Any]]):
        """Broadcast diagnostic completion"""
        if not self.websocket_manager:
            return

        try:
            from ...agent.websocket_manager import EventType

            # Get final report
            final_task = None
            for task in reversed(self.task_manager.tasks):
                if task.status == TaskStatus.COMPLETED:
                    final_task = task
                    break

            await self.websocket_manager.broadcast(
                EventType.DIAGNOSTIC_COMPLETE,
                {
                    "diagnostic_id": self.diagnostic_id,
                    "site_id": self.context.get("site_id"),
                    "task_count": len(self.task_manager.tasks),
                    "completed_count": sum(1 for t in self.task_manager.tasks if t.status == TaskStatus.COMPLETED),
                    "failed_count": sum(1 for t in self.task_manager.tasks if t.status == TaskStatus.FAILED),
                    "final_result": final_task.result if final_task else None,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting completion: {e}")

