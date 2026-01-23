"""
Diagnostic Task Manager
Task list data structures and management for diagnostic agents
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DiagnosticTask:
    """Single diagnostic task data structure"""
    task_id: str
    agent: str  # Agent name to execute this task
    description: str  # Task description (will be used as agent prompt)
    dependencies: List[str] = field(default_factory=list)  # List of task_ids this task depends on
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class DiagnosticTaskManager:
    """Diagnostic task list management class"""

    def __init__(self):
        self.tasks: List[DiagnosticTask] = []
        self.completed: bool = False

    def create_tasks(self, tasks: List[Dict]) -> str:
        """Create initial task list

        Args:
            tasks: List of task dicts, each containing:
                - task_id: str (unique identifier)
                - agent: str (agent name)
                - description: str (task description)
                - dependencies: List[str] (optional, list of task_ids)

        Returns:
            Creation result message
        """
        if self.tasks:
            return "Error: Task list already exists, use add_task to add new tasks"

        # Validate and collect task IDs
        task_ids = set()
        for task_data in tasks:
            task_id = task_data.get("task_id")
            if not task_id:
                return "Error: Task missing task_id"
            if task_id in task_ids:
                return f"Error: Duplicate task_id: {task_id}"
            task_ids.add(task_id)

        # Validate dependencies
        for task_data in tasks:
            deps = task_data.get("dependencies", [])
            for dep_id in deps:
                if dep_id not in task_ids:
                    return f"Error: Task {task_data['task_id']} depends on non-existent task {dep_id}"

        # Create task objects
        for task_data in tasks:
            task = DiagnosticTask(
                task_id=task_data["task_id"],
                agent=task_data.get("agent", "DefaultAgent"),
                description=task_data["description"],
                dependencies=task_data.get("dependencies", [])
            )
            self.tasks.append(task)

        logger.info(f"Created {len(self.tasks)} diagnostic tasks")
        return f"Created {len(self.tasks)} tasks"

    def get_task(self, task_id: str) -> Optional[DiagnosticTask]:
        """Get task by ID"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_ready_tasks(self) -> List[DiagnosticTask]:
        """Get all ready tasks (dependencies satisfied and status is pending)

        Returns:
            List of ready tasks
        """
        ready = []
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_satisfied = True
            for dep_id in task.dependencies:
                dep_task = self.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    deps_satisfied = False
                    break

            if deps_satisfied:
                ready.append(task)

        return ready

    def mark_executing(self, task_id: str) -> None:
        """Mark task as executing"""
        import time
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.EXECUTING
            task.started_at = time.time()
            logger.debug(f"Task {task_id} marked as executing")

    def mark_completed(self, task_id: str, result: Dict[str, Any]) -> None:
        """Mark task as completed"""
        import time
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            logger.info(f"Task {task_id} completed")

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark task as failed"""
        import time
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = error
            task.completed_at = time.time()
            logger.error(f"Task {task_id} failed: {error}")

    def has_pending_tasks(self) -> bool:
        """Check if there are any pending tasks"""
        return any(t.status == TaskStatus.PENDING for t in self.tasks)

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "agent": t.agent,
                    "description": t.description,
                    "dependencies": t.dependencies,
                    "status": t.status.value,
                    "result": t.result,
                    "error": t.error,
                    "started_at": t.started_at,
                    "completed_at": t.completed_at,
                }
                for t in self.tasks
            ],
            "completed": self.completed
        }

    def get_summary(self) -> str:
        """Get task list summary"""
        lines = ["Diagnostic Task List Status:"]

        for task in self.tasks:
            status_icon = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.EXECUTING: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌"
            }.get(task.status, "?")

            deps_str = f" (deps: {', '.join(task.dependencies)})" if task.dependencies else ""
            lines.append(
                f"  {status_icon} {task.task_id}: [{task.agent}] {task.description[:50]}...{deps_str}"
            )

            if task.result:
                result_preview = str(task.result)[:100] + "..." if len(str(task.result)) > 100 else str(task.result)
                lines.append(f"      Result: {result_preview}")
            if task.error:
                lines.append(f"      Error: {task.error}")

        pending_count = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
        completed_count = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        executing_count = sum(1 for t in self.tasks if t.status == TaskStatus.EXECUTING)

        lines.append(
            f"\nStats: Pending {pending_count}, Executing {executing_count}, "
            f"Completed {completed_count}, Failed {failed_count}"
        )

        return "\n".join(lines)

