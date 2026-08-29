import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from extractor import (
    VIDEO_INDICATOR_REGEX,
    extract_featured_media,
    normalize_video_embed_url,
)


def test_normalize_video_embed_url_youtube():
    watch_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    embed_url = normalize_video_embed_url(watch_url)
    assert embed_url == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"

    short_url = "https://youtu.be/dQw4w9WgXcQ"
    assert normalize_video_embed_url(short_url) == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"

    shorts_url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    assert normalize_video_embed_url(shorts_url) == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


def test_normalize_video_embed_url_vimeo_and_others():
    vimeo_url = "https://vimeo.com/12345678"
    assert normalize_video_embed_url(vimeo_url) == "https://player.vimeo.com/video/12345678"

    dailymotion_url = "https://www.dailymotion.com/video/x7xzzz"
    assert normalize_video_embed_url(dailymotion_url) == "https://www.dailymotion.com/embed/video/x7xzzz"

    direct_mp4 = "https://cdn.example.com/video.mp4"
    assert normalize_video_embed_url(direct_mp4) == direct_mp4


def test_extract_featured_media_youtube_link():
    entry = {
        "link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Noticia urgente con video",
    }
    img, vid = extract_featured_media(entry, "https://www.youtube.com")
    assert vid == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


def test_extract_featured_media_opengraph():
    entry = {
        "link": "https://noticias.example.com/articulo-1",
        "summary": '<html><head><meta property="og:video" content="https://vimeo.com/98765432"></head></html>',
    }
    img, vid = extract_featured_media(entry, "https://noticias.example.com")
    assert vid == "https://player.vimeo.com/video/98765432"


def test_video_indicator_regex():
    assert VIDEO_INDICATOR_REGEX.search("Vea el video exclusivo grabado en vivo") is not None
    assert VIDEO_INDICATOR_REGEX.search("[VIDEO] Transmisión en directo desde la frontera") is not None
    assert VIDEO_INDICATOR_REGEX.search("Reporte general de economía local sin medios") is None
