"""
video_engine.py — Core Video Processing Engine & Media Stream Generator.
Handles stream url resolution, MJPEG streaming generators, social video URL parsing,
and sample camera inventory for instant operational deployment.
"""
import asyncio
import io
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Pre-configured sample camera network for standalone testing and instant demonstration
DEFAULT_CAMERAS: List[Dict] = [
    {
        "id": "tfl_cam_01",
        "name": "London Piccadilly Circus",
        "city": "London",
        "country": "UK",
        "source": "TfL",
        "latitude": 51.5101,
        "longitude": -0.1342,
        "feed_url": "https://s3-eu-west-1.amazonaws.com/jamcams.tfl.gov.uk/00001.03751.jpg",
        "type": "JPEG_REFRESH",
        "status": "ONLINE",
        "fps": 5,
    },
    {
        "id": "tfl_cam_02",
        "name": "Trafalgar Square North",
        "city": "London",
        "country": "UK",
        "source": "TfL",
        "latitude": 51.5080,
        "longitude": -0.1281,
        "feed_url": "https://s3-eu-west-1.amazonaws.com/jamcams.tfl.gov.uk/00001.03752.jpg",
        "type": "JPEG_REFRESH",
        "status": "ONLINE",
        "fps": 5,
    },
    {
        "id": "nvr_ch_01",
        "name": "Entrada Principal NVR",
        "city": "Caracas",
        "country": "VE",
        "source": "Hikvision NVR",
        "latitude": 10.4806,
        "longitude": -66.9036,
        "feed_url": "http://192.168.1.163/ISAPI/Streaming/channels/101/picture",
        "type": "ISAPI_HTTP",
        "status": "ONLINE",
        "fps": 15,
    },
    {
        "id": "nvr_ch_02",
        "name": "Ascensor Oeste - Sótano",
        "city": "Caracas",
        "country": "VE",
        "source": "Hikvision NVR",
        "latitude": 10.4808,
        "longitude": -66.9038,
        "feed_url": "http://192.168.1.163/ISAPI/Streaming/channels/201/picture",
        "type": "ISAPI_HTTP",
        "status": "ONLINE",
        "fps": 15,
    },
    {
        "id": "wsdot_cam_01",
        "name": "I-5 Seattle Downtown",
        "city": "Seattle",
        "country": "US",
        "source": "WSDOT",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "feed_url": "https://images.wsdot.wa.gov/nw/005vc16550.jpg",
        "type": "JPEG_REFRESH",
        "status": "ONLINE",
        "fps": 2,
    },
    {
        "id": "sg_cam_01",
        "name": "CTE Singapore Flyover",
        "city": "Singapore",
        "country": "SG",
        "source": "LTA SG",
        "latitude": 1.3521,
        "longitude": 103.8198,
        "feed_url": "https://images.data.gov.sg/v2/cctv/cte.jpg",
        "type": "JPEG_REFRESH",
        "status": "ONLINE",
        "fps": 2,
    },
]


def generate_synthetic_frame(camera_id: str, label: str = "LIVE FEED") -> bytes:
    """Generate a clean 640x360 synthetic tactical frame with timestamp overlay when offline or testing."""
    img = Image.new("RGB", (640, 360), color=(10, 15, 25))
    draw = ImageDraw.Draw(img)

    # Draw grid background lines
    for x in range(0, 640, 40):
        draw.line([(x, 0), (x, 360)], fill=(20, 30, 45), width=1)
    for y in range(0, 360, 40):
        draw.line([(0, y), (640, y)], fill=(20, 30, 45), width=1)

    # Tactical corner brackets
    draw.rectangle([10, 10, 630, 350], outline=(0, 229, 255), width=1)
    draw.ellipse([300, 160, 340, 200], outline=(255, 215, 0), width=2)
    draw.line([(320, 150), (320, 210)], fill=(255, 215, 0), width=1)
    draw.line([(290, 180), (350, 180)], fill=(255, 215, 0), width=1)

    # Overlay Text Information
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.text((20, 20), f"CAM: {camera_id.upper()}", fill=(0, 229, 255))
    draw.text((20, 40), f"SRC: {label}", fill=(255, 215, 0))
    draw.text((20, 325), f"TIMESTAMP: {now_str}", fill=(200, 200, 200))
    draw.text((480, 20), "● REC [LIVE]", fill=(255, 68, 68))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def fetch_camera_frame_bytes(feed_url: str, camera_id: str = "CAM-01") -> bytes:
    """Fetch live JPEG bytes from camera URL with graceful synthetic fallback."""
    if not feed_url or feed_url.startswith("synthetic://"):
        return generate_synthetic_frame(camera_id, "SYNTHETIC TEST")

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(feed_url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 100:
                        return data
    except Exception as e:
        logger.debug(f"[VIDEO ENGINE] Fetch error for {camera_id}: {e}")

    return generate_synthetic_frame(camera_id, f"OFFLINE FALLBACK ({camera_id})")


async def generate_mjpeg_stream(camera_id: str, feed_url: str, interval_sec: float = 1.0):
    """Generator yielding multipart MJPEG stream frames continuously."""
    boundary = "frame"
    while True:
        frame_bytes = await fetch_camera_frame_bytes(feed_url, camera_id)
        yield (
            f"--{boundary}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(frame_bytes)}\r\n\r\n"
        ).encode("utf-8") + frame_bytes + b"\r\n"
        await asyncio.sleep(interval_sec)


def extract_media_info(url: str) -> Dict:
    """Extract direct embed media info from TikTok, Instagram, YouTube, Vimeo, or direct MP4/HLS links."""
    clean_url = url.strip()

    # Direct MP4 / HLS / WebM
    if re.search(r"\.(mp4|m3u8|webm|mov)(\?.*)?$", clean_url, re.IGNORECASE):
        return {
            "type": "DIRECT_VIDEO",
            "url": clean_url,
            "embed_url": clean_url,
            "provider": "DIRECT",
            "playable": True,
        }

    # YouTube
    yt_match = re.search(r"(?:v=|\/embed\/|\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})", clean_url)
    if yt_match:
        video_id = yt_match.group(1)
        return {
            "type": "EMBED",
            "url": clean_url,
            "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1",
            "provider": "YOUTUBE",
            "playable": True,
        }

    # Vimeo
    vimeo_match = re.search(r"vimeo\.com\/(?:video\/)?(\d+)", clean_url)
    if vimeo_match:
        video_id = vimeo_match.group(1)
        return {
            "type": "EMBED",
            "url": clean_url,
            "embed_url": f"https://player.vimeo.com/video/{video_id}?autoplay=1",
            "provider": "VIMEO",
            "playable": True,
        }

    # TikTok
    if "tiktok.com" in clean_url:
        return {
            "type": "SOCIAL",
            "url": clean_url,
            "embed_url": clean_url,
            "provider": "TIKTOK",
            "playable": True,
            "note": "Requiere embed player TikTok o SDK público",
        }

    # Default generic web video link fallback
    return {
        "type": "GENERIC_URL",
        "url": clean_url,
        "embed_url": clean_url,
        "provider": "WEB",
        "playable": True,
    }
