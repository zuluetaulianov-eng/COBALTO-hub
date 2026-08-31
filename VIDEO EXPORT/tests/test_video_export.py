"""
test_video_export.py — Automated test suite for Video & CCTV Export Subsystem.
Validates Computer Vision, Snapshot Collector, Video Engine, and FastAPI REST endpoints.
"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure VIDEO EXPORT root is in sys.path per AGENTS.md rules
EXPORT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(EXPORT_DIR))

from main import app
from cctv_vision import analyze_cctv_frame
from cctv_collector import snapshot_collector
from video_engine import generate_synthetic_frame, extract_media_info

client = TestClient(app)


def test_synthetic_frame_generator():
    """Test generating synthetic frame bytes."""
    frame_bytes = generate_synthetic_frame("cam_test", "TEST")
    assert isinstance(frame_bytes, bytes)
    assert len(frame_bytes) > 500


def test_cctv_vision_analysis():
    """Test OpenCV computer vision frame analyzer."""
    frame_bytes = generate_synthetic_frame("cam_vision", "VISION TEST")
    res = analyze_cctv_frame("cam_vision", frame_bytes)

    assert res["camera_id"] == "cam_vision"
    assert "objects_detected" in res
    assert "motion_score" in res
    assert "traffic_density" in res
    assert "anomaly_detected" in res


def test_cctv_collector_watchlist():
    """Test watchlist operations in snapshot collector."""
    assert snapshot_collector.add_to_watchlist("tfl_cam_01") is True
    watchlist = snapshot_collector.get_watchlist()
    assert "tfl_cam_01" in watchlist

    assert snapshot_collector.remove_from_watchlist("tfl_cam_01") is True
    assert "tfl_cam_01" not in snapshot_collector.get_watchlist()


def test_extract_media_info():
    """Test video URL extraction logic."""
    yt_info = extract_media_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert yt_info["provider"] == "YOUTUBE"
    assert "embed/dQw4w9WgXcQ" in yt_info["embed_url"]

    mp4_info = extract_media_info("https://example.com/video.mp4")
    assert mp4_info["provider"] == "DIRECT"
    assert mp4_info["type"] == "DIRECT_VIDEO"


def test_api_cameras_endpoint():
    """Test GET /api/cctv/cameras REST endpoint."""
    response = client.get("/api/cctv/cameras")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "cameras" in data
    assert len(data["cameras"]) > 0


def test_api_frame_endpoint():
    """Test GET /api/cctv/frame/{camera_id} endpoint."""
    response = client.get("/api/cctv/frame/tfl_cam_01")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 100


def test_api_vision_analyze_endpoint():
    """Test POST /api/cctv/analyze/{camera_id} endpoint."""
    response = client.post("/api/cctv/analyze/tfl_cam_01")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "analysis" in data
    assert data["analysis"]["camera_id"] == "tfl_cam_01"


def test_api_video_extract_endpoint():
    """Test POST /api/video/extract endpoint."""
    response = client.post("/api/video/extract", json={"url": "https://example.com/stream.m3u8"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["media"]["playable"] is True


def test_api_news_videos_endpoint():
    """Test GET /api/news/videos REST endpoint."""
    response = client.get("/api/news/videos")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "news_videos" in data
    assert len(data["news_videos"]) > 0


def test_api_news_video_push_endpoint():
    """Test POST /api/news/videos/push endpoint."""
    payload = {
        "title": "Noticia Test con Video Embed",
        "summary": "Resumen de prueba de noticia con video incorporado",
        "source": "Fuente Test",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "country": "VEN",
        "category": "NACIONAL"
    }
    response = client.post("/api/news/videos/push", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["item"]["title"] == "Noticia Test con Video Embed"
    assert "youtube-nocookie" in data["item"]["video_url"]

