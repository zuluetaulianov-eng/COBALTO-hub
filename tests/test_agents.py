"""Tests for agent system modules: agent_tools, ares_investigator, agent_orchestrator, agent_memory."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_agent_tools_imports():
    from agent_tools import init_registry, list_tools, get_tool
    assert callable(init_registry)
    assert callable(list_tools)
    assert callable(get_tool)


def test_agent_tools_registry():
    from agent_tools import init_registry, list_tools, get_tool
    init_registry()
    tools_dict = list_tools()
    assert len(tools_dict) > 0

    tool_names = list(tools_dict.keys())
    assert "recon_dns" in tool_names
    assert "recon_whois" in tool_names
    assert "search_entities" in tool_names
    assert "search_sanctions" in tool_names
    assert "search_news" in tool_names

    for name, t in tools_dict.items():
        assert "name" in t
        assert "description" in t
        assert "parameters" in t

    dns_tool = get_tool("recon_dns")
    assert dns_tool is not None
    assert dns_tool.name == "recon_dns"

    nonexistent = get_tool("nonexistent_tool")
    assert nonexistent is None


def test_ares_investigator_imports():
    from ares_investigator import detect_and_investigate
    assert callable(detect_and_investigate)


async def test_ares_investigator_suggest_mode():
    from ares_investigator import detect_and_investigate
    ctx = {"alerts": [{"title": "Test critical alert", "summary": "IP 8.8.8.8 detected in attack", "level": "CRÍTICO"}], "composite_events": [], "network_outages": []}
    findings = await detect_and_investigate(ctx, mode="suggest")
    assert isinstance(findings, list)


async def test_ares_investigator_empty_context():
    from ares_investigator import detect_and_investigate
    findings = await detect_and_investigate({}, mode="auto")
    assert isinstance(findings, list)


def test_agent_orchestrator_imports():
    from agent_orchestrator import orchestrator, Task
    assert orchestrator is not None
    assert hasattr(orchestrator, "add_task")
    assert callable(orchestrator.list_tasks)
    assert callable(orchestrator.get_mode)
    assert callable(orchestrator.set_mode)
    assert callable(orchestrator.approve_task)
    assert callable(orchestrator.reject_task)


def test_agent_orchestrator_add_task():
    from agent_orchestrator import orchestrator, Task

    task = Task(task_type="recon", title="Test task", description="DNS lookup", tool_name="recon_dns", tool_params={"domain": "example.com"})
    task_id = orchestrator.add_task(task)
    assert task_id is not None
    assert len(task_id) > 0

    tasks = orchestrator.list_tasks()
    assert len(tasks) >= 1
    found = any(t["id"] == task_id for t in tasks)
    assert found


def test_agent_orchestrator_modes():
    from agent_orchestrator import orchestrator
    original = orchestrator.get_mode()
    orchestrator.set_mode("auto")
    assert orchestrator.get_mode() == "auto"
    orchestrator.set_mode("suggest")
    assert orchestrator.get_mode() == "suggest"
    orchestrator.set_mode("approval")
    assert orchestrator.get_mode() == "approval"
    orchestrator.set_mode(original)


def test_agent_orchestrator_approve_reject():
    from agent_orchestrator import orchestrator, Task

    original_mode = orchestrator.get_mode()
    orchestrator.set_mode("approval")
    task = Task(task_type="search", title="Approval test", description="test", tool_name="search_entities", tool_params={"query": "test"}, requires_approval=True)
    tid = orchestrator.add_task(task)
    assert task.status == "pending_approval"

    ok = orchestrator.approve_task(tid)
    assert ok

    task2 = Task(task_type="search", title="Reject test", description="test", tool_name="search_news", tool_params={"query": "test"}, requires_approval=True)
    tid2 = orchestrator.add_task(task2)
    ok = orchestrator.reject_task(tid2)
    assert ok

    tasks = orchestrator.list_tasks(status="rejected")
    found = any(t["id"] == tid2 for t in tasks)
    assert found

    orchestrator.set_mode(original_mode)


def test_agent_memory_imports():
    from agent_memory import create_session, get_context, get_session, list_sessions, cleanup
    assert callable(create_session)
    assert callable(get_context)
    assert callable(get_session)
    assert callable(list_sessions)
    assert callable(cleanup)


def test_agent_memory_session_lifecycle():
    from agent_memory import create_session, get_session, append_context, get_context, list_sessions, cleanup

    session_id = create_session("test_agent")
    assert session_id is not None
    assert len(session_id) > 0

    session = get_session(session_id)
    assert session is not None
    assert session["agent_name"] == "test_agent"
    assert session["session_id"] == session_id

    append_context(session_id, "user", "test query", tool_name="search", tool_result='{"found": true}')
    ctx = get_context(session_id)
    assert len(ctx) >= 1
    assert ctx[0]["role"] == "user"
    assert ctx[0]["tool_name"] == "search"

    sessions = list_sessions()
    assert len(sessions) >= 1

    cleanup()


def test_agent_memory_context_trimming():
    from agent_memory import create_session, append_context, get_context
    session_id = create_session("stress_test")
    for i in range(60):
        append_context(session_id, "system", f"message {i}")
    ctx = get_context(session_id, limit=100)
    assert len(ctx) <= 50
