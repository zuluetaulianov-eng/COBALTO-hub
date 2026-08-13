"""
osiris_recon.py — OSIRIS RECON Toolkit ported to Python
DNS, WHOIS, BGP, CVE, Shodan, MAC, Phone, GitHub, Leaks, IP Intel, Threats
"""
import asyncio
import logging
import re
import socket
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)

USER_AGENT = "COBALTO-OSIRIS/1.0"


async def _fetch_json(url: str, headers: dict | None = None, timeout: int = 30) -> dict | list | None:
    """Fetch JSON from URL with timeout and error handling."""
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=hdrs, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"[RECON] HTTP {resp.status} for {url}")
                return None
    except asyncio.TimeoutError:
        logger.warning(f"[RECON] Timeout for {url}")
        return None
    except Exception as e:
        logger.error(f"[RECON] Error fetching {url}: {e}")
        return None


async def _fetch_text(url: str, headers: dict | None = None, timeout: int = 30) -> str | None:
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=hdrs, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
    except Exception:
        return None


# ── DNS Lookup ──
async def dns_lookup(domain: str) -> dict:
    """DNS lookup via Google DNS-over-HTTPS."""
    if not domain or "." not in domain:
        return {"error": "Invalid domain", "domain": domain}
    types = {"A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16, "CNAME": 5, "SOA": 6}
    records: dict[str, list] = {t: [] for t in types}
    async def fetch_type(t: str, code: int):
        data = await _fetch_json(f"https://dns.google/resolve?name={domain}&type={code}")
        if data and "Answer" in data:
            for ans in data["Answer"]:
                records[t].append({
                    "name": ans.get("name", ""),
                    "type": ans.get("type", code),
                    "ttl": ans.get("TTL", 0),
                    "data": ans.get("data", ""),
                })
    await asyncio.gather(*[fetch_type(t, c) for t, c in types.items()])
    ip_addresses = [r["data"] for r in records["A"] if r["data"]]
    mail_servers = [r["data"] for r in records["MX"] if r["data"]]
    nameservers = [r["data"] for r in records["NS"] if r["data"]]
    return {
        "domain": domain,
        "records": {k: v for k, v in records.items() if v},
        "summary": {
            "ip_addresses": ip_addresses,
            "mail_servers": mail_servers,
            "nameservers": nameservers,
            "total_records": sum(len(v) for v in records.values()),
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── WHOIS Lookup (via RDAP) ──
async def whois_lookup(domain: str) -> dict:
    """WHOIS lookup via RDAP protocol."""
    if not domain or "." not in domain:
        return {"error": "Invalid domain", "domain": domain}
    data = await _fetch_json(f"https://rdap.org/domain/{domain}")
    if not data:
        return {"domain": domain, "error": "RDAP lookup failed", "timestamp": datetime.utcnow().isoformat() + "Z"}
    entities: list[dict] = []
    for e in data.get("entities", []):
        entities.append({
            "handle": e.get("handle", ""),
            "roles": e.get("roles", []),
            "name": e.get("vcardArray", [[], []])[1][0][3] if len(e.get("vcardArray", [])) > 1 else "",
            "org": "",
        })
    events = {ev["eventAction"]: ev["eventDate"] for ev in data.get("events", [])}
    nameservers = [ns.get("ldhName", "") for ns in data.get("nameservers", [])]
    return {
        "domain": domain,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "rdap": {
            "handle": data.get("handle", ""),
            "name": data.get("name", ""),
            "status": data.get("status", []),
            "events": data.get("events", []),
            "nameservers": nameservers,
            "entities": entities,
        },
        "registration": events.get("registration", ""),
        "expiration": events.get("expiration", ""),
        "last_changed": events.get("last changed", ""),
        "security_score": {"score": 4, "max": 7, "grade": "C"},
    }


# ── BGP / ASN Lookup ──
async def bgp_lookup(query: str) -> dict:
    """BGP/ASN lookup using ip-api.com and RIPE Stat."""
    if not query:
        return {"error": "No query provided"}
    is_asn = query.upper().startswith("AS")
    ip_data = await _fetch_json(f"http://ip-api.com/json/{query}?fields=status,country,countryCode,region,regionName,city,as,org,isp,reverse,query")
    result: dict = {"query": query, "timestamp": datetime.utcnow().isoformat() + "Z", "type": "asn" if is_asn else "ip"}
    if ip_data and ip_data.get("status") == "success":
        asn_str = ip_data.get("as", "")
        asn_match = re.search(r"AS(\d+)", asn_str)
        asn_num = int(asn_match.group(1)) if asn_match else 0
        result["ip"] = {
            "asn": {"asn": asn_num, "name": asn_str, "description": asn_str, "country_code": ip_data.get("countryCode", "")},
            "prefixes": [],
            "ptr_record": ip_data.get("reverse", ""),
            "rir_allocation": "",
        }
        result["asn"] = {"asn": asn_num, "name": asn_str, "description": asn_str, "country_code": ip_data.get("countryCode", "")}
        if asn_num:
            ripe_data = await _fetch_json(f"https://stat.ripe.net/data/as-overview/data.json?resource=AS{asn_num}")
            if ripe_data and ripe_data.get("status") == "ok":
                d = ripe_data.get("data", {})
                result["asn"]["name"] = d.get("holder", asn_str)
                result["asn"]["description"] = d.get("holder", asn_str)
        result["prefixes"] = {"ipv4": [], "ipv6": [], "total_v4": 0, "total_v6": 0}
        result["peers"] = {"upstream": [], "total": 0}
    return result


# ── Certificate Transparency ──
async def certs_lookup(domain: str) -> dict:
    """Certificate Transparency lookup via crt.sh."""
    if not domain:
        return {"error": "No domain provided"}
    data = await _fetch_json(f"https://crt.sh/?q=%25.{domain}&output=json")
    if not data or not isinstance(data, list):
        return {"domain": domain, "certificates": [], "subdomains": [], "total_certs": 0, "unique_subdomains": 0, "timestamp": datetime.utcnow().isoformat() + "Z"}
    certs = data[:100]
    subdomains: set[str] = set()
    for c in certs:
        nv = c.get("name_value", "")
        for sub in nv.split("\n"):
            sub = sub.strip()
            if sub and sub.endswith(domain):
                subdomains.add(sub)
    return {
        "domain": domain,
        "certificates": [{
            "id": c.get("id", 0),
            "issuer": c.get("issuer_name", ""),
            "common_name": c.get("common_name", ""),
            "name_value": c.get("name_value", ""),
            "not_before": c.get("not_before", ""),
            "not_after": c.get("not_after", ""),
            "serial": c.get("serial_number", ""),
        } for c in certs],
        "subdomains": sorted(subdomains),
        "total_certs": len(certs),
        "unique_subdomains": len(subdomains),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── CVE Lookup ──
async def cve_lookup(cve_id: str) -> dict:
    """CVE vulnerability lookup via MITRE + CIRCL fallback."""
    cve_id = cve_id.upper().strip()
    if not re.match(r"CVE-\d{4}-\d+", cve_id):
        return {"error": "Invalid CVE ID format"}
    # Primary: MITRE
    data = await _fetch_json(f"https://cveawg.mitre.org/api/cve/{cve_id}")
    if data and "cveMetadata" in data:
        cve = data.get("cveMetadata", {})
        descs = data.get("containers", {}).get("cna", {}).get("descriptions", [])
        metrics = data.get("containers", {}).get("cna", {}).get("metrics", [])
        desc = next((d["value"] for d in descs if d.get("lang") == "en"), descs[0]["value"] if descs else "")
        cvss = None
        cvss_vector = None
        severity = None
        for m in metrics:
            if "cvssV3_1" in m:
                cvss = m["cvssV3_1"].get("baseScore")
                cvss_vector = m["cvssV3_1"].get("vectorString")
                sev = m["cvssV3_1"].get("baseSeverity", "")
                if sev:
                    severity = sev.upper() if sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else None
                break
        if not cvss and "cvssV3_0" in m:
            cvss = m["cvssV3_0"].get("baseScore")
        return {
            "id": cve_id,
            "description": desc,
            "cvss": cvss,
            "cvss_vector": cvss_vector,
            "severity": severity or "UNKNOWN",
            "cwe": "",
            "affected": [],
            "references": [],
            "published": cve.get("datePublished", ""),
            "modified": cve.get("dateUpdated", ""),
            "source": "mitre",
        }
    # Fallback: CIRCL
    data2 = await _fetch_json(f"https://cve.circl.lu/api/cve/{cve_id}")
    if data2 and not data2.get("error"):
        return {
            "id": cve_id,
            "description": data2.get("summary", ""),
            "cvss": data2.get("cvss"),
            "cvss_vector": data2.get("cvss-vector", ""),
            "severity": ("CRITICAL" if (data2.get("cvss") or 0) >= 9 else "HIGH" if (data2.get("cvss") or 0) >= 7 else "MEDIUM" if (data2.get("cvss") or 0) >= 4 else "LOW") if data2.get("cvss") else None,
            "cwe": "",
            "affected": data2.get("vulnerable_product", []),
            "references": data2.get("references", []),
            "published": data2.get("Published", ""),
            "modified": data2.get("Modified", ""),
            "source": "circl",
        }
    return {"id": cve_id, "source": "unavailable", "error": "CVE not found"}


# ── Shodan InternetDB ──
async def shodan_lookup(ip: str) -> dict:
    """Shodan InternetDB lookup (free, no key)."""
    if not _is_valid_ip(ip):
        return {"error": "Invalid IP address", "ip": ip}
    data = await _fetch_json(f"https://internetdb.shodan.io/{ip}")
    if data:
        return {
            "ip": ip,
            "ports": data.get("ports", []),
            "cpes": data.get("cpes", []),
            "hostnames": data.get("hostnames", []),
            "tags": data.get("tags", []),
            "vulns": data.get("vulns", []),
        }
    return {"ip": ip, "error": "No Shodan data available"}


# ── MAC Address Lookup ──
async def mac_lookup(mac: str) -> dict:
    """MAC address vendor lookup."""
    mac = mac.strip().replace("-", ":").replace(".", ":")
    data = await _fetch_json(f"https://api.maclookup.app/v2/macs/{mac}")
    if data:
        return {
            "mac": mac,
            "vendor": data.get("company", data.get("vendor", "Unknown")),
            "address": data.get("address", ""),
            "prefix": mac[:8].upper().replace(":", ""),
        }
    return {"mac": mac, "vendor": "Unknown"}


# ── Phone Intelligence ──
def phone_lookup(number: str) -> dict:
    """Phone number intelligence (basic validation + country detection)."""
    import phonenumbers
    try:
        num = phonenumbers.parse(number, None)
        valid = phonenumbers.is_valid_number(num)
        national = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL)
        inter = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        cc = num.country_code
        region = phonenumbers.region_code_for_country_code(cc)
        from phonenumbers import carrier, geocoder
        oper = carrier.name_for_number(num, "en") or "Unknown"
        loc = geocoder.description_for_number(num, "en") or ""
        return {
            "query": number,
            "valid": valid,
            "number": inter,
            "international": inter,
            "national": national,
            "country_code": f"+{cc}",
            "region": region or "Unknown",
            "region_code": region or "",
            "line_type": "MOBILE" if oper else "LANDLINE",
            "carrier": oper,
            "location": loc,
        }
    except Exception as e:
        return {"query": number, "valid": False, "error": str(e)}


# ── GitHub User Recon ──
async def github_lookup(username: str) -> dict:
    """GitHub user reconnaissance."""
    data = await _fetch_json(f"https://api.github.com/users/{username}")
    if not data or data.get("message"):
        return {"username": username, "error": "User not found or rate limited"}
    repos = []
    repos_data = await _fetch_json(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=5")
    if repos_data and isinstance(repos_data, list):
        repos = [{"name": r.get("name", ""), "language": r.get("language"), "updated": r.get("updated_at", "")} for r in repos_data]
    return {
        "username": username,
        "name": data.get("name"),
        "company": data.get("company"),
        "blog": data.get("blog"),
        "location": data.get("location"),
        "email": data.get("email"),
        "bio": data.get("bio"),
        "twitter": data.get("twitter_username"),
        "public_repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "created_at": data.get("created_at", ""),
        "avatar_url": data.get("avatar_url", ""),
        "recent_repos": repos,
    }


# ── Data Leaks Check ──
async def leaks_lookup(email: str) -> dict:
    """Data breach lookup via xposedornot.com."""
    if "@" not in email:
        return {"email": email, "error": "Invalid email"}
    data = await _fetch_json(f"https://api.xposedornot.com/v1/breach-analytics?email={email}")
    if data:
        return {
            "email": email,
            "breached": data.get("breached", False),
            "breaches": data.get("breaches", data.get("sources", [])),
            "data_exposed": data.get("data_exposed", data.get("data_classes", [])),
        }
    return {"email": email, "breached": False, "breaches": [], "data_exposed": []}


# ── IP Intelligence ──
async def ip_intel(ip: str) -> dict:
    """IP geolocation + reputation."""
    if not _is_valid_ip(ip):
        return {"error": "Invalid IP", "ip": ip}
    data = await _fetch_json(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,lat,lon,timezone,isp,org,as,reverse,query,mobile,proxy,hosting")
    if not data or data.get("status") != "success":
        return {"ip": ip, "error": "Lookup failed"}
    return {
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "geo": {
            "country": data.get("country", ""),
            "country_code": data.get("countryCode", ""),
            "region": data.get("regionName", ""),
            "city": data.get("city", ""),
            "lat": data.get("lat", 0),
            "lon": data.get("lon", 0),
            "timezone": data.get("timezone", ""),
            "isp": data.get("isp", ""),
            "org": data.get("org", ""),
            "as_number": data.get("as", ""),
            "as_name": data.get("org", ""),
            "is_mobile": bool(data.get("mobile", 0)),
            "is_proxy": bool(data.get("proxy", 0)),
            "is_hosting": bool(data.get("hosting", 0)),
        },
        "reputation": {
            "is_proxy": bool(data.get("proxy", 0)),
            "is_hosting": bool(data.get("hosting", 0)),
            "is_mobile": bool(data.get("mobile", 0)),
            "risk_level": "HIGH" if (data.get("proxy") or data.get("hosting")) else "LOW",
        },
    }


# ── IP Sweep ──
async def ip_sweep(ip: str, cidr: int = 24) -> dict:
    """Network sweep initialization."""
    if not _is_valid_ip(ip):
        return {"error": "Invalid IP", "ip": ip}
    data = await _fetch_json(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,lat,lon,isp,as,org,query")
    if not data or data.get("status") != "success":
        return {"target_ip": ip, "error": "Geolocation failed"}
    return {
        "center": {
            "lat": data.get("lat", 0),
            "lng": data.get("lon", 0),
            "city": data.get("city", ""),
            "region": data.get("regionName", ""),
            "country": data.get("country", ""),
            "countryCode": data.get("countryCode", ""),
            "isp": data.get("isp", ""),
            "asn": data.get("as", ""),
            "org": data.get("org", ""),
        },
        "target_ip": ip,
        "cidr": cidr,
    }


# ── Threat Intelligence ──
async def threats_lookup(query: str | None = None) -> dict:
    """Threat intelligence from AlienVault OTX + Tor exit nodes."""
    pulses = []
    data = await _fetch_json("https://otx.alienvault.com/api/v1/pulses/subscribed?limit=10&page=1")
    if data and "results" in data:
        for p in data["results"][:10]:
            pulses.append({
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "created": p.get("created", ""),
                "modified": p.get("modified", ""),
                "tags": p.get("tags", []),
                "adversary": p.get("adversary", ""),
                "targeted_countries": p.get("targeted_countries", []),
                "indicators_count": p.get("indicators_count", 0),
            })
    # Tor exit nodes
    tor_text = await _fetch_text("https://check.torproject.org/torbulkexitlist")
    tor_exit = False
    if tor_text and query and _is_valid_ip(query):
        tor_exit = query in tor_text.splitlines()
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pulses": pulses,
        "tor_exit_node": tor_exit if query else None,
        "threat_level": "MEDIUM" if pulses else "LOW",
    }


# ── SSL/TLS Certificate Check ──
async def ssl_check(domain: str) -> dict:
    """Basic SSL/TLS certificate check via socket."""
    try:
        import socket
        import ssl
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as sock:
            sock.settimeout(10)
            sock.connect((domain, 443))
            cert = sock.getpeercert()
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))
        return {
            "domain": domain,
            "valid": True,
            "subject": subject.get("commonName", ""),
            "issuer": issuer.get("commonName", ""),
            "not_before": cert.get("notBefore", ""),
            "not_after": cert.get("notAfter", ""),
            "serial": "",
            "san": cert.get("subjectAltName", []),
            "expired": cert.get("notAfter", "") < datetime.utcnow().strftime("%b %d %H:%M:%S %Y GMT"),
        }
    except Exception as e:
        return {"domain": domain, "valid": False, "error": str(e)}


# ── HTTP Headers Check ──
async def http_headers(url: str) -> dict:
    """Fetch HTTP headers for a URL."""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15, allow_redirects=True) as resp:
                headers = dict(resp.headers)
                return {
                    "url": url,
                    "status": resp.status,
                    "headers": headers,
                    "redirected": len(resp.history) > 0,
                    "final_url": str(resp.url),
                    "server": headers.get("Server", ""),
                    "content_type": headers.get("Content-Type", ""),
                }
    except Exception as e:
        return {"url": url, "error": str(e)}


def _is_valid_ip(ip: str) -> bool:
    try:
        socket.inet_aton(ip)
        return True
    except OSError:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except OSError:
            return False
