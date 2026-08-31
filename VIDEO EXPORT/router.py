"""
router.py — FastAPI APIRouter providing REST & Streaming endpoints for Video & CCTV.
Can be imported directly into any external FastAPI application or run via main.py.
"""
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cctv_collector import snapshot_collector
from cctv_vision import analyze_cctv_frame
from news_video_collector import news_video_collector
from video_engine import (
    DEFAULT_CAMERAS,
    extract_media_info,
    fetch_camera_frame_bytes,
    generate_mjpeg_stream,
)

video_router = APIRouter(tags=["Video & CCTV Subsystem"])


class VideoExtractRequest(BaseModel):
    url: str = Field(..., description="URL of video to extract (TikTok, YouTube, MP4, HLS)")


class WatchlistRequest(BaseModel):
    camera_id: str = Field(..., description="ID of camera to add/remove from watchlist")


class NewsVideoPushRequest(BaseModel):
    title: str = Field(..., description="Title of news article")
    summary: str = Field(..., description="Summary text of news article")
    source: str = Field(..., description="Media source name")
    video_url: str = Field(..., description="Video embed or direct URL")
    link: Optional[str] = Field(None, description="Original article link")
    image_url: Optional[str] = Field(None, description="Thumbnail image URL")
    country: Optional[str] = Field("GLOBAL", description="Country code (VEN, COL, GLOBAL)")
    category: Optional[str] = Field("GENERAL", description="News category")


@video_router.get("/api/news/videos")
async def get_news_videos(
    country: str = Query("ALL", description="Filter by country tag"),
    category: str = Query("ALL", description="Filter by category"),
    provider: str = Query("ALL", description="Filter by provider"),
    limit: int = Query(50, ge=1, le=100),
):
    """Retrieve list of news articles specifically containing video feeds/embeds."""
    items = news_video_collector.get_news_videos(country=country, category=category, provider=provider, limit=limit)
    stats = news_video_collector.get_stats()
    return {
        "status": "success",
        "total_items": len(items),
        "news_videos": items,
        "stats": stats,
    }


@video_router.post("/api/news/videos/push")
async def push_news_video(req: NewsVideoPushRequest):
    """Push a new news article with video into the video subsystem inbox."""
    item = await news_video_collector.add_news_video(
        title=req.title,
        summary=req.summary,
        source=req.source,
        video_url=req.video_url,
        link=req.link or "",
        image_url=req.image_url or "",
        country=req.country or "GLOBAL",
        category=req.category or "GENERAL",
    )
    return {"status": "success", "message": "News item with video added successfully", "item": item}


@video_router.get("/api/cctv/cameras", response_model=Dict)
async def get_cctv_cameras():
    """Get complete catalog of registered CCTV cameras and total count."""
    stats = snapshot_collector.get_stats()
    return {
        "status": "success",
        "total_cameras": len(DEFAULT_CAMERAS),
        "cameras": DEFAULT_CAMERAS,
        "collector_stats": stats,
    }


@video_router.get("/api/cctv/frame/{camera_id}")
async def get_cctv_frame(camera_id: str):
    """Retrieve current JPEG frame bytes for a specified camera ID."""
    cam = next((c for c in DEFAULT_CAMERAS if c["id"] == camera_id), None)
    feed_url = cam["feed_url"] if cam else f"synthetic://{camera_id}"

    frame_bytes = await fetch_camera_frame_bytes(feed_url, camera_id)
    return Response(content=frame_bytes, media_type="image/jpeg")


@video_router.get("/api/cctv/stream/{camera_id}")
async def get_cctv_mjpeg_stream(camera_id: str, fps: float = Query(1.0, ge=0.2, le=10.0)):
    """Stream continuous MJPEG video frames for a specified camera."""
    cam = next((c for c in DEFAULT_CAMERAS if c["id"] == camera_id), None)
    feed_url = cam["feed_url"] if cam else f"synthetic://{camera_id}"
    interval = max(0.1, 1.0 / fps)

    return StreamingResponse(
        generate_mjpeg_stream(camera_id, feed_url, interval_sec=interval),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@video_router.post("/api/cctv/analyze/{camera_id}")
async def analyze_camera_vision(camera_id: str):
    """Execute OpenCV computer vision analytics on current frame of specified camera."""
    cam = next((c for c in DEFAULT_CAMERAS if c["id"] == camera_id), None)
    feed_url = cam["feed_url"] if cam else f"synthetic://{camera_id}"

    frame_bytes = await fetch_camera_frame_bytes(feed_url, camera_id)
    analysis = analyze_cctv_frame(camera_id, frame_bytes)

    if cam:
        analysis["camera_name"] = cam.get("name")
        analysis["city"] = cam.get("city")
        analysis["country"] = cam.get("country")

    return {"status": "success", "analysis": analysis}


@video_router.get("/api/cctv/alerts")
async def get_cctv_alerts():
    """Retrieve tactical motion alerts generated from camera analysis."""
    alerts = snapshot_collector.generate_cctv_alerts()
    return {
        "status": "success",
        "total_alerts": len(alerts),
        "alerts": alerts,
    }


@video_router.get("/api/cctv/watchlist")
async def get_watchlist():
    """Get current camera IDs on priority monitoring watchlist."""
    return {
        "status": "success",
        "watchlist": snapshot_collector.get_watchlist(),
    }


@video_router.post("/api/cctv/watchlist/add")
async def add_watchlist(req: WatchlistRequest):
    """Add camera ID to priority monitoring watchlist."""
    snapshot_collector.add_to_watchlist(req.camera_id)
    return {"status": "success", "message": f"Camera {req.camera_id} added to watchlist"}


@video_router.post("/api/cctv/watchlist/remove")
async def remove_watchlist(req: WatchlistRequest):
    """Remove camera ID from priority monitoring watchlist."""
    snapshot_collector.remove_from_watchlist(req.camera_id)
    return {"status": "success", "message": f"Camera {req.camera_id} removed from watchlist"}


@video_router.post("/api/video/extract")
async def extract_video(req: VideoExtractRequest):
    """Extract direct embed media info from TikTok, Instagram, YouTube, Vimeo, or MP4 link."""
    if not req.url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    info = extract_media_info(req.url)
    return {"status": "success", "media": info}
