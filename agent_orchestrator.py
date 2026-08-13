"""
agent_orchestrator.py — Task queue and scheduling for autonomous agents.
Manages task lifecycle: created → pending_approval → running → completed/failed.
Integrates with event_bus for real-time frontend updates.
"""
import asyncio
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from agent_tools import get_tool, init_registry
from ares_investigator import detect_and_investigate

logger = logging.getLogger(__name__)


class Task:
    def __init__(
        self,
        task_type: str,
        title: str,
        description: str,
        source: str = "ares",
        tool_name: str = "",
        tool_params: Optional[Dict] = None,
        requires_approval: bool = True,
        findings: Optional[List[Dict]] = None,
    ):
        self.id = uuid.uuid4().hex[:12]
        self.task_type = task_type
        self.title = title
        self.description = description
        self.source = source
        self.tool_name = tool_name
        self.tool_params = tool_params or {}
        self.status = "pending"  # pending → pending_approval → running → completed / failed / rejected
        self.requires_approval = requires_approval
        self.findings = findings or []
        self.result: Optional[Dict] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.approved_by: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "status": self.status,
            "requires_approval": self.requires_approval,
            "findings": self.findings,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class AgentOrchestrator:
    def __init__(self):
        self._lock = threading.RLock()
        self._tasks: Dict[str, Task] = {}
        self._max_tasks = 200
        self._auto_mode = "suggest"  # suggest | auto | approval
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_mode(self, mode: str):
        if mode in ("suggest", "auto", "approval"):
            self._auto_mode = mode

    def get_mode(self) -> str:
        return self._auto_mode

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    # ── Task CRUD ──

    def add_task(self, task: Task) -> str:
        with self._lock:
            if task.requires_approval and self._auto_mode != "auto":
                task.status = "pending_approval"
            else:
                task.status = "pending"
            self._tasks[task.id] = task
            if len(self._tasks) > self._max_tasks:
                # Remove oldest completed tasks
                old = sorted(
                    [t for t in self._tasks.values() if t.status in ("completed", "failed", "rejected")],
                    key=lambda x: x.created_at,
                )
                for t in old[:50]:
                    del self._tasks[t.id]
        self._emit_event("task_created", task)
        return task.id

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            return [t.to_dict() for t in tasks[:limit]]

    def approve_task(self, task_id: str, approved_by: str = "operator") -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != "pending_approval":
                return False
            task.status = "pending"
            task.approved_by = approved_by
        self._emit_event("task_approved", task)
        return True

    def reject_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != "pending_approval":
                return False
            task.status = "rejected"
            task.completed_at = datetime.now().isoformat()
        self._emit_event("task_rejected", task)
        return True

    # ── Execution ──

    async def run_pending(self):
        """Execute all pending tasks."""
        pending = []
        with self._lock:
            pending = [t for t in self._tasks.values() if t.status == "pending"]

        for task in pending:
            await self._execute_task(task)

    async def _execute_task(self, task: Task):
        task.status = "running"
        self._emit_event("task_running", task)

        try:
            tool = get_tool(task.tool_name)
            if tool:
                result = await tool.execute(**task.tool_params)
                task.result = result
                task.status = "completed" if result.get("success") else "failed"
                task.error = result.get("error")
            else:
                # No tool: just mark completed with findings
                task.result = {"findings": task.findings}
                task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error = str(e)

        task.completed_at = datetime.now().isoformat()
        self._emit_event("task_completed" if task.status == "completed" else "task_failed", task)

    # ── Investigation Cycle ──

    async def run_investigation_cycle(self, dashboard_context: Dict):
        """Called from Heavy cycle. Runs ARES investigator and creates tasks."""
        init_registry()

        findings = await detect_and_investigate(
            dashboard_context, mode=self._auto_mode
        )

        for finding in findings:
            suggested = finding.get("suggested_tools", [])
            requires_approval = self._auto_mode != "auto"

            if suggested:
                for tool_name in suggested[:2]:
                    task = Task(
                        task_type=finding["type"],
                        title=finding["title"],
                        description=finding["summary"],
                        source="ares",
                        tool_name=tool_name,
                        tool_params={},
                        requires_approval=requires_approval,
                        findings=[finding],
                    )
                    self.add_task(task)
            else:
                task = Task(
                    task_type=finding["type"],
                    title=finding["title"],
                    description=finding["summary"],
                    source="ares",
                    requires_approval=requires_approval,
                    findings=[finding],
                )
                self.add_task(task)

        # Auto-run if mode allows
        if self._auto_mode == "auto":
            await self.run_pending()

    def _emit_event(self, event_type: str, task: Task):
        try:
            from event_bus import bus
            bus.emit(event_type, "orchestrator", {
                "task_id": task.id,
                "task_type": task.task_type,
                "title": task.title,
                "status": task.status,
            })
        except Exception:
            pass


# Global singleton
orchestrator = AgentOrchestrator()
