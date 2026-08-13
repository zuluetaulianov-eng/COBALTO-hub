"""
agent_tools.py — Tool registry for autonomous agents.
Each tool wraps an existing OSIRIS RECON endpoint or internal function
with a standard interface: name, description, parameters schema, and async callable.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    callback: Callable[..., Coroutine]
    rate_limit_max: int = 10
    rate_limit_window: float = 60.0
    timeout: float = 30.0
    _hits: List[float] = field(default_factory=list)

    def is_rate_limited(self) -> bool:
        now = time.time()
        self._hits = [t for t in self._hits if now - t < self.rate_limit_window]
        return len(self._hits) >= self.rate_limit_max

    def record_hit(self):
        self._hits.append(time.time())

    async def execute(self, **kwargs) -> Dict:
        if self.is_rate_limited():
            return {"error": f"Tool '{self.name}' rate limited", "tool": self.name}
        self.record_hit()
        try:
            result = await asyncio.wait_for(self.callback(**kwargs), timeout=self.timeout)
            return {"tool": self.name, "success": True, "result": result}
        except asyncio.TimeoutError:
            return {"tool": self.name, "success": False, "error": f"Timeout ({self.timeout}s)"}
        except Exception as e:
            logger.warning(f"[TOOL] {self.name} error: {e}")
            return {"tool": self.name, "success": False, "error": str(e)}


_registry: Dict[str, Tool] = {}


def register_tool(tool: Tool):
    _registry[tool.name] = tool
    logger.info(f"[TOOL REGISTRY] Registered: {tool.name}")


def get_tool(name: str) -> Optional[Tool]:
    return _registry.get(name)


def list_tools() -> Dict[str, Dict]:
    return {name: {"name": t.name, "description": t.description, "parameters": t.parameters} for name, t in _registry.items()}


# ── Tool Implementations ──────────────────────────────────────────

async def _recon_dns(domain: str = "") -> Dict:
    from osiris_recon import dns_lookup
    return await dns_lookup(domain)


async def _recon_whois(domain: str = "") -> Dict:
    from osiris_recon import whois_lookup
    return await whois_lookup(domain)


async def _recon_shodan(ip: str = "") -> Dict:
    from osiris_recon import shodan_lookup
    return await shodan_lookup(ip)


async def _recon_github(user: str = "") -> Dict:
    from osiris_recon import github_lookup
    return await github_lookup(user)


async def _search_entities(query: str = "") -> Dict:
    from entity_registry import search
    results = await asyncio.to_thread(search, query=query, limit=20)
    return {"entities": results}


async def _search_sanctions(query: str = "") -> Dict:
    from osiris_intel import ensure_sanctions_index, search_sanctions
    await ensure_sanctions_index()
    results = search_sanctions(query)
    return {"hits": results}


async def _get_entity_info(entity_id: str = "") -> Dict:
    from entity_registry import get_by_id
    entity = await asyncio.to_thread(get_by_id, entity_id)
    return entity or {"error": "not found"}


async def _graph_neighbors(node_id: str = "") -> Dict:
    from graph_database import get_latest_snapshot
    snap = await asyncio.to_thread(get_latest_snapshot)
    if not snap:
        return {"error": "no snapshot"}
    nodes = snap["graph_data"].get("nodes", [])
    edges = snap["graph_data"].get("edges", [])
    neighbors = []
    target = [n for n in nodes if n.get("id") == node_id]
    for e in edges:
        if e.get("from") == node_id:
            n = [n for n in nodes if n.get("id") == e.get("to")]
            if n:
                neighbors.append({"node": n[0], "edge": e})
        elif e.get("to") == node_id:
            n = [n for n in nodes if n.get("id") == e.get("from")]
            if n:
                neighbors.append({"node": n[0], "edge": e})
    return {"target": target[0] if target else None, "neighbors": neighbors, "count": len(neighbors)}


async def _search_news(keyword: str = "", limit: int = 10) -> Dict:
    from datetime import datetime, timedelta

    from historical_store import query_range
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=7)
    result = await asyncio.to_thread(
        query_range, from_dt=from_dt, to_dt=to_dt, search=keyword, limit=limit
    )
    return {"entries": result.get("entries", []), "total": result.get("total", 0)}


# ── Initialize Registry ───────────────────────────────────────────

def init_registry():
    if _registry:
        return

    register_tool(Tool(
        name="recon_dns",
        description="DNS resolution for a domain (A/AAAA/MX/NS/TXT/CNAME/SOA)",
        parameters={"domain": {"type": "string", "description": "Domain to resolve"}},
        callback=_recon_dns,
    ))
    register_tool(Tool(
        name="recon_whois",
        description="WHOIS lookup for a domain",
        parameters={"domain": {"type": "string", "description": "Domain to query"}},
        callback=_recon_whois,
    ))
    register_tool(Tool(
        name="recon_shodan",
        description="Shodan/InternetDB intelligence for an IP address",
        parameters={"ip": {"type": "string", "description": "IP address"}},
        callback=_recon_shodan,
    ))
    register_tool(Tool(
        name="recon_github",
        description="GitHub recon for a username",
        parameters={"user": {"type": "string", "description": "GitHub username"}},
        callback=_recon_github,
    ))
    register_tool(Tool(
        name="search_entities",
        description="Search canonical entity registry by name",
        parameters={"query": {"type": "string", "description": "Entity name to search"}},
        callback=_search_entities,
    ))
    register_tool(Tool(
        name="search_sanctions",
        description="Search OFAC SDN sanctions list by name",
        parameters={"query": {"type": "string", "description": "Name to check against OFAC SDN"}},
        callback=_search_sanctions,
    ))
    register_tool(Tool(
        name="get_entity_info",
        description="Get full entity details from registry by ID",
        parameters={"entity_id": {"type": "string", "description": "Entity registry ID"}},
        callback=_get_entity_info,
    ))
    register_tool(Tool(
        name="graph_neighbors",
        description="Get neighbor nodes of a graph node in the social graph",
        parameters={"node_id": {"type": "string", "description": "Graph node ID"}},
        callback=_graph_neighbors,
    ))
    register_tool(Tool(
        name="search_news",
        description="Search historical OSINT entries by keyword",
        parameters={
            "keyword": {"type": "string", "description": "Search keyword"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        callback=_search_news,
        rate_limit_max=30,
    ))

    logger.info(f"[TOOL REGISTRY] Initialized with {len(_registry)} tools")
