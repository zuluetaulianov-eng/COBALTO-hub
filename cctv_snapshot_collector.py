"""
cctv_snapshot_collector.py — Async snapshot collector for public CCTV cameras.
Fetches static JPEG frames from known sources, stores them with rotation,
and records metadata in historical_store.
"""
import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).parent / "data" / "cctv_snapshots"
MAX_SNAPSHOTS_PER_CAMERA = 100
REQUEST_TIMEOUT = 10
CONCURRENCY = 5

# Known camera sources that serve static JPEGs
CAMERA_SOURCES: List[Dict] = [
    # TfL London
    {"id_prefix": "tfl", "url_template": "https://s3-eu-west-1.amazonaws.com/jamcams.tfl.gov.uk/{cid}.jpg", "source": "TfL"},
    # WSDOT Washington
    {"id_prefix": "wsdot", "url_template": None, "source": "WSDOT"},
    # Singapore LTA
    {"id_prefix": "sg", "url_template": None, "source": "Singapore LTA"},
]


class SnapshotCollector:
    def __init__(self):
        self._snapshots: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_SNAPSHOTS_PER_CAMERA))
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(CONCURRENCY)
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={"User-Agent": "Mozilla/5.0 (compatible; COBALTO/1.0)"},
            )
        return self._session

    async def fetch_frame(self, camera_id: str, feed_url: str, source: str) -> Optional[Dict]:
        """Fetch a single frame from a camera. Returns metadata dict or None."""
        async with self._semaphore:
            try:
                session = await self._get_session()
                async with session.get(feed_url, timeout=REQUEST_TIMEOUT) as resp:
                    if resp.status != 200:
                        logger.debug("[SNAPSHOT] %s HTTP %d", camera_id, resp.status)
                        return None
                    data = await resp.read()
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                logger.debug("[SNAPSHOT] %s fetch error: %s", camera_id, e)
                return None

        if not data or len(data) < 100:
            return None

        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_id}_{ts_str}.jpg"
        subdir = SNAPSHOT_DIR / camera_id
        subdir.mkdir(parents=True, exist_ok=True)
        filepath = subdir / filename

        try:
            filepath.write_bytes(data)
        except OSError as e:
            logger.warning("[SNAPSHOT] write error %s: %s", filepath, e)
            return None

        meta = {
            "camera_id": camera_id,
            "source": source,
            "filename": filename,
            "filepath": str(filepath.relative_to(SNAPSHOT_DIR.parent)),
            "size_bytes": len(data),
            "timestamp": timestamp.isoformat(),
        }

        self._snapshots[camera_id].append(meta)

        # Rotate: remove oldest files exceeding limit
        while len(self._snapshots[camera_id]) > MAX_SNAPSHOTS_PER_CAMERA:
            old = self._snapshots[camera_id].popleft()
            old_path = SNAPSHOT_DIR / camera_id / old["filename"]
            try:
                old_path.unlink(missing_ok=True)
            except OSError:
                pass

        return meta

    async def collect_from_cameras(self, cameras: List[Dict]) -> List[Dict]:
        """Collect snapshots from a list of camera dicts (from /api/osiris/data/cctv)."""
        tasks = []
        for cam in cameras:
            feed_url = cam.get("feed_url", "")
            cid = cam.get("id", "")
            source = cam.get("source", "unknown")
            if not feed_url or not cid:
                continue
            tasks.append(self.fetch_frame(cid, feed_url, source))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        collected = []
        for r in results:
            if isinstance(r, dict) and r.get("filename"):
                collected.append(r)
        return collected

    async def collect_known_sources(self) -> List[Dict]:
        """Fetch camera list from our own API, then snapshot each."""
        try:
            session = await self._get_session()
            async with session.get("http://127.0.0.1:8083/api/osiris/data/cctv?region=all") as resp:
                data = await resp.json()
            cameras = data.get("cameras", [])
        except Exception as e:
            logger.warning("[SNAPSHOT] cannot fetch camera list: %s", e)
            return []

        return await self.collect_from_cameras(cameras)

    def list_snapshots(self, camera_id: str = "", limit: int = 50) -> List[Dict]:
        """List stored snapshot metadata."""
        if camera_id:
            return list(self._snapshots.get(camera_id, []))[-limit:]
        all_snaps = []
        for snaps in self._snapshots.values():
            all_snaps.extend(snaps)
        all_snaps.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_snaps[:limit]

    def get_stats(self) -> Dict:
        """Return snapshot collector stats."""
        total = sum(len(snaps) for snaps in self._snapshots.values())
        by_source: Dict[str, int] = {}
        for snaps in self._snapshots.values():
            for s in snaps:
                src = s.get("source", "unknown")
                by_source[src] = by_source.get(src, 0) + 1
        return {
            "total_snapshots": total,
            "total_cameras": len(self._snapshots),
            "by_source": by_source,
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


snapshot_collector = SnapshotCollector()
