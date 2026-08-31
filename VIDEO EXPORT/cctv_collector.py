"""
cctv_collector.py — Async snapshot collector & motion analyzer for CCTV feeds.
Fetches JPEG frames, manages local snapshot storage, calculates frame deltas,
maintains priority watchlists, and generates tactical motion alerts.
"""
import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import aiohttp

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
SNAPSHOT_DIR = BASE_DIR / "data" / "cctv_snapshots"
MAX_SNAPSHOTS_PER_CAMERA = 50
REQUEST_TIMEOUT = 8
CONCURRENCY = 25


class SnapshotCollector:
    def __init__(self):
        self._snapshots: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_SNAPSHOTS_PER_CAMERA))
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(CONCURRENCY)
        self._watchlist: Set[str] = set()
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={"User-Agent": "Mozilla/5.0 (compatible; COBALTO-VideoExport/1.0)"},
            )
        return self._session

    async def fetch_frame(self, camera_id: str, feed_url: str, source: str = "CCTV") -> Optional[Dict]:
        """Fetch a single frame from a camera feed URL. Returns metadata dict or None."""
        async with self._semaphore:
            try:
                session = await self._get_session()
                async with session.get(feed_url, timeout=REQUEST_TIMEOUT) as resp:
                    if resp.status != 200:
                        logger.debug(f"[SNAPSHOT] {camera_id} HTTP {resp.status}")
                        return None
                    data = await resp.read()
            except Exception as e:
                logger.debug(f"[SNAPSHOT] {camera_id} fetch error: {e}")
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
            logger.warning(f"[SNAPSHOT] Write error for {filepath}: {e}")
            return None

        meta = {
            "camera_id": camera_id,
            "source": source,
            "filename": filename,
            "filepath": str(filepath.relative_to(BASE_DIR)),
            "size_bytes": len(data),
            "timestamp": timestamp.isoformat(),
        }

        self._snapshots[camera_id].append(meta)

        # Rotate old snapshots exceeding limit
        while len(self._snapshots[camera_id]) > MAX_SNAPSHOTS_PER_CAMERA:
            old = self._snapshots[camera_id].popleft()
            old_path = SNAPSHOT_DIR / camera_id / old["filename"]
            try:
                old_path.unlink(missing_ok=True)
            except OSError:
                pass

        return meta

    async def collect_from_cameras(self, cameras: List[Dict]) -> List[Dict]:
        """Collect snapshots concurrently from a list of camera dicts."""
        tasks = []
        for cam in cameras:
            feed_url = cam.get("feed_url") or cam.get("url", "")
            cid = cam.get("id") or cam.get("camera_id", "")
            source = cam.get("source", "CCTV")
            if not feed_url or not cid:
                continue
            tasks.append(self.fetch_frame(cid, feed_url, source))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        collected = []
        for r in results:
            if isinstance(r, dict) and r.get("filename"):
                collected.append(r)
        return collected

    def list_snapshots(self, camera_id: str = "", limit: int = 50) -> List[Dict]:
        """List stored snapshot metadata."""
        if camera_id:
            return list(self._snapshots.get(camera_id, []))[-limit:]
        all_snaps = []
        for snaps in self._snapshots.values():
            all_snaps.extend(snaps)
        all_snaps.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_snaps[:limit]

    def analyze_frame_motion(self, camera_id: str) -> Dict:
        """Analyze motion/activity delta between the latest 2 snapshots of a camera."""
        snaps = list(self._snapshots.get(camera_id, []))
        if len(snaps) < 2:
            return {
                "camera_id": camera_id,
                "status": "INSUFFICIENT_FRAMES",
                "activity_score": 0.0,
                "frame_count": len(snaps),
            }

        prev_snap = snaps[-2]
        curr_snap = snaps[-1]

        prev_path = BASE_DIR / prev_snap["filepath"]
        curr_path = BASE_DIR / curr_snap["filepath"]

        if not prev_path.exists() or not curr_path.exists():
            return {
                "camera_id": camera_id,
                "status": "FILE_NOT_FOUND",
                "activity_score": 0.0,
            }

        delta_score = 0.0
        try:
            from PIL import Image
            img1 = Image.open(prev_path).convert("L").resize((32, 32))
            img2 = Image.open(curr_path).convert("L").resize((32, 32))

            bytes1 = list(img1.getdata())
            bytes2 = list(img2.getdata())

            diff_sum = sum(abs(b1 - b2) for b1, b2 in zip(bytes1, bytes2))
            max_possible = 255.0 * len(bytes1)
            delta_score = round((diff_sum / max_possible) * 100.0, 2)
        except Exception:
            try:
                b1 = prev_path.read_bytes()[:2048]
                b2 = curr_path.read_bytes()[:2048]
                min_len = min(len(b1), len(b2))
                if min_len > 0:
                    diff_sum = sum(abs(x - y) for x, y in zip(b1[:min_len], b2[:min_len]))
                    delta_score = round((diff_sum / (255.0 * min_len)) * 100.0, 2)
            except Exception as e:
                logger.debug(f"[ANALYSIS] Error reading frames: {e}")

        if delta_score > 15.0:
            status = "HIGH_ACTIVITY"
        elif delta_score >= 5.0:
            status = "MODERATE_ACTIVITY"
        elif delta_score >= 0.5:
            status = "NORMAL_STATIC"
        else:
            status = "UNCHANGED_FREEZE"

        return {
            "camera_id": camera_id,
            "status": status,
            "activity_score": delta_score,
            "source": curr_snap.get("source", "CCTV"),
            "last_timestamp": curr_snap.get("timestamp"),
            "prev_timestamp": prev_snap.get("timestamp"),
            "snapshots_analyzed": [prev_snap["filename"], curr_snap["filename"]],
        }

    def analyze_all_cameras(self) -> List[Dict]:
        """Analyze frame motion delta for all tracked cameras."""
        results = []
        for cid in self._snapshots.keys():
            res = self.analyze_frame_motion(cid)
            if res.get("status") != "INSUFFICIENT_FRAMES":
                results.append(res)
        results.sort(key=lambda x: x.get("activity_score", 0.0), reverse=True)
        return results

    def add_to_watchlist(self, camera_id: str) -> bool:
        """Add camera to priority monitoring watchlist."""
        self._watchlist.add(camera_id)
        return True

    def remove_from_watchlist(self, camera_id: str) -> bool:
        """Remove camera from priority monitoring watchlist."""
        if camera_id in self._watchlist:
            self._watchlist.remove(camera_id)
            return True
        return False

    def get_watchlist(self) -> List[str]:
        """Return list of watchlist camera IDs."""
        return list(self._watchlist)

    def generate_cctv_alerts(self) -> List[Dict]:
        """Generate tactical alert entries for high activity or watchlist cameras."""
        alerts = []
        analysis = self.analyze_all_cameras()

        for item in analysis:
            cid = item.get("camera_id", "")
            status = item.get("status", "")
            score = item.get("activity_score", 0.0)
            is_watchlist = cid in self._watchlist

            if status == "HIGH_ACTIVITY" or (is_watchlist and score > 8.0):
                level = "🔴 CRÍTICO" if score > 30.0 else "🟠 URGENTE"
                alerts.append({
                    "title": f"🎥 ALERTA MOVIMIENTO CCTV: Cámara {cid}",
                    "summary": f"Variación de fotogramas del {score}% ({status}). Fuente: {item.get('source')}.",
                    "source": f"CCTV-{item.get('source', 'OSIRIS')}",
                    "level": level,
                    "score": min(35.0 + score, 98.0),
                    "type": "cctv_motion_alert",
                    "camera_id": cid,
                    "published": item.get("last_timestamp", datetime.utcnow().isoformat()),
                    "link": f"/api/cctv/frame/{cid}",
                })
        return alerts

    def get_stats(self) -> Dict:
        """Return collector stats."""
        total = sum(len(snaps) for snaps in self._snapshots.values())
        analysis = self.analyze_all_cameras()
        high_act = [a for a in analysis if a.get("status") == "HIGH_ACTIVITY"]
        return {
            "total_snapshots": total,
            "total_cameras": len(self._snapshots),
            "high_activity_count": len(high_act),
            "watchlist_count": len(self._watchlist),
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


snapshot_collector = SnapshotCollector()
