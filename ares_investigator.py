"""
ares_investigator.py — ARES autonomous investigation agent.
Detects anomalies in the pipeline and runs OSIRIS RECON tools to investigate.
Generates mini-reports for the orchestrator.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from agent_tools import get_tool, init_registry

logger = logging.getLogger(__name__)


async def detect_and_investigate(
    dashboard_context: Dict,
    mode: str = "suggest",
) -> List[Dict]:
    """
    Main entry point. Scans dashboard context for anomalies and runs investigations.
    mode: 'suggest' = only generate suggestions, 'auto' = run tools automatically.
    Returns list of findings.
    """
    init_registry()
    findings = []

    # Sources of anomalies
    alerts = dashboard_context.get("alerts", [])
    composite_events = dashboard_context.get("composite_events", [])
    entries = dashboard_context.get("all_entries", [])
    asn_data = dashboard_context.get("asn_data", {})

    # 1. Check critical alerts
    critical = [a for a in alerts if a.get("level") in ("CRÍTICO", "CRITICAL")]
    for alert in critical[:3]:
        finding = await _investigate_alert(alert, entries, mode)
        if finding:
            findings.append(finding)

    # 2. Check composite events (geo-correlated)
    for event in composite_events[:3]:
        finding = await _investigate_composite(event, mode)
        if finding:
            findings.append(finding)

    # 3. Check network outages
    outages = asn_data.get("network_outages", [])
    for outage in outages[:2]:
        provider = outage.get("provider", "")
        drop = outage.get("drop_percentage", 0)
        if drop and drop > 50:
            finding = {
                "type": "network_outage",
                "severity": "ALTA",
                "title": f"Caída crítica de {provider} ({drop}%)",
                "summary": f"Se detectó una caída de red del {drop}% en {provider}. "
                           f"Se sugiere verificar estado de ASNs y correlacionar con eventos sísmicos o de protestas.",
                "suggested_tools": ["search_news"],
                "mode": mode,
                "timestamp": datetime.now().isoformat(),
                "auto_result": None,
            }
            findings.append(finding)

    logger.info(f"[ARES] Investigated {len(findings)} anomalies")
    return findings


async def _investigate_alert(alert: Dict, entries: List[Dict], mode: str) -> Optional[Dict]:
    title = alert.get("title", "")
    summary = alert.get("summary", "")
    text = f"{title} {summary}"

    # Extract entities from alert text for investigation
    import re
    ips = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)
    domains = re.findall(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", text)

    suggested_tools = []
    auto_result = None

    if ips:
        suggested_tools.append("recon_shodan")
        if mode == "auto":
            shodan = get_tool("recon_shodan")
            if shodan:
                auto_result = await shodan.execute(ip=ips[0])

    if domains and not suggested_tools:
        suggested_tools.extend(["recon_whois", "recon_dns"])
        if mode == "auto":
            whois = get_tool("recon_whois")
            if whois:
                auto_result = await whois.execute(domain=domains[0])

    return {
        "type": "alert_investigation",
        "severity": alert.get("level", "MEDIA"),
        "title": f"Investigación: {title[:100]}",
        "summary": f"Alerta crítica detectada. IPs: {ips[:3]}, Dominios: {domains[:3]}",
        "suggested_tools": suggested_tools,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "auto_result": auto_result,
    }


async def _investigate_composite(event: Dict, mode: str) -> Optional[Dict]:
    title = event.get("title", "")
    description = event.get("description", "")
    sources = event.get("sources", [])

    text = f"{title} {description}"

    import re
    locations = re.findall(r"\b[A-Z][a-záéíóú]+(?:\s+[A-Z][a-záéíóú]+)*\b", text)
    location = locations[0] if locations else "Venezuela"

    return {
        "type": "composite_investigation",
        "severity": event.get("severity", "MEDIA"),
        "title": f"Correlación: {title[:100]}",
        "summary": f"Eventos correlacionados: {', '.join(sources)}. "
                   f"Ubicación: {location}. "
                   f"Se sugiere buscar noticias relacionadas.",
        "suggested_tools": ["search_news", "search_entities"],
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "auto_result": None,
    }
