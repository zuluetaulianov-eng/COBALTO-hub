"""
cctv_vision.py — Real computer-vision analytics for CCTV feeds using OpenCV.
Performs real object/motion detection against camera frames, returning
pedestrian counts, motion scores, traffic density, and anomaly indicators.
Designed for standalone usage and easy integration into external systems.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_hog = None
_mog2 = None


def _get_hog():
    """Lazy-load the OpenCV HOG people detector."""
    global _hog
    if _hog is None:
        try:
            import cv2
            holder = cv2.HOGDescriptor()
            holder.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            _hog = holder
        except Exception as e:
            logger.warning(f"[CCTV-VISION] HOG init failed: {e}")
            _hog = False
    return _hog or None


def _get_mog2():
    """Lazy-create MOG2 background subtractor for motion detection."""
    global _mog2
    try:
        import cv2
    except Exception:
        return None
    if _mog2 is None:
        try:
            _mog2 = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=36, detectShadows=True)
        except Exception as e:
            logger.warning(f"[CCTV-VISION] MOG2 init failed: {e}")
            _mog2 = False
    return _mog2 or None


def decode_frame(image_bytes: bytes) -> Optional[Any]:
    """Decode raw JPEG/PNG bytes into an OpenCV BGR frame, or None on failure."""
    try:
        import cv2
        import numpy as np
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        logger.debug(f"[CCTV-VISION] Frame decode error: {e}")
        return None


def analyze_cctv_frame(camera_id: str, image_bytes: bytes) -> Dict[str, Any]:
    """
    Run real computer-vision analysis on a CCTV camera frame.
    Returns a dict with detected objects, motion score, traffic density, anomaly status, and confidence.
    """
    now_iso = datetime.utcnow().isoformat() + "Z"

    try:
        import cv2
    except Exception as exc:
        return {
            "camera_id": camera_id,
            "timestamp": now_iso,
            "objects_detected": {"vehicles": 0, "pedestrians": 0, "bicycles": 0},
            "motion_score": 0.0,
            "traffic_density": "DESCONOCIDA",
            "anomaly_detected": False,
            "confidence": 0.0,
            "model": "COBALTO-VISION-FALLBACK",
            "tactical_status": "VISION NO DISPONIBLE",
            "error": f"OpenCV no disponible: {exc}",
        }

    frame = decode_frame(image_bytes)
    if frame is None or frame.size == 0:
        return {
            "camera_id": camera_id,
            "timestamp": now_iso,
            "objects_detected": {"vehicles": 0, "pedestrians": 0, "bicycles": 0},
            "motion_score": 0.0,
            "traffic_density": "DESCONOCIDA",
            "anomaly_detected": False,
            "confidence": 0.0,
            "model": "COBALTO-VISION",
            "tactical_status": "FRAME NO DECODIFICABLE",
        }

    h, w = frame.shape[:2]
    small = cv2.resize(frame, (640, int(640 * h / w))) if w > 640 else frame

    # 1. Pedestrian detection via HOG SVM
    pedestrians = 0
    hog = _get_hog()
    if hog is not None:
        try:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            rects, _ = hog.detectMultiScale(
                gray, winStride=(4, 4), padding=(8, 8), scale=1.05, hitThreshold=0.0
            )
            if len(rects) > 0:
                rects = cv2.groupRectangles(rects.tolist(), 1, 0.2)[0]
                pedestrians = len(rects)
        except Exception as e:
            logger.debug(f"[CCTV-VISION] HOG detection error: {e}")

    # 2. Motion score via MOG2
    motion_score = 0.0
    mog2 = _get_mog2()
    if mog2 is not None:
        try:
            fg_mask = mog2.apply(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            if fg_mask is not None:
                motion_pixels = int(cv2.countNonZero(cv2.threshold(fg_mask, 128, 255, cv2.THRESH_BINARY)[1]))
                total_pixels = fg_mask.shape[0] * fg_mask.shape[1]
                motion_score = round((motion_pixels / max(total_pixels, 1)) * 100.0, 2)
        except Exception as e:
            logger.debug(f"[CCTV-VISION] MOG2 motion error: {e}")

    # 3. Contour density heuristic for vehicles / activity
    vehicles_est = 0
    bicycles_est = 0
    if motion_score > 1.5:
        try:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(
                cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            candidates = 0
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 400 < area < 120000:
                    candidates += 1
            vehicles_est = max(0, min(candidates, 40))
            bicycles_est = max(0, min(candidates // 3, 6))
        except Exception:
            pass

    # 4. Traffic density & anomaly classification
    if motion_score > 20.0 or vehicles_est > 15:
        density = "ALTA"
    elif motion_score > 8.0 or vehicles_est > 7:
        density = "MODERADA"
    elif motion_score > 3.0:
        density = "FLUIDA"
    else:
        density = "ESTABLE"

    anomaly = motion_score > 35.0 or vehicles_est > 30
    confidence = round(min(0.99, 0.55 + (motion_score / 200.0) + (pedestrians * 0.02) + (vehicles_est * 0.005)), 2)

    return {
        "camera_id": camera_id,
        "timestamp": now_iso,
        "objects_detected": {
            "vehicles": vehicles_est,
            "pedestrians": pedestrians,
            "bicycles": bicycles_est,
        },
        "motion_score": motion_score,
        "frame_dimensions": {"width": w, "height": h},
        "traffic_density": density,
        "anomaly_detected": anomaly,
        "confidence": confidence,
        "model": "COBALTO-VISION (OpenCV HOG+MOG2)",
        "tactical_status": "ALERTA CRÍTICA" if anomaly else ("VIGILANCIA ALTA" if motion_score > 20.0 else "NORMAL"),
    }
