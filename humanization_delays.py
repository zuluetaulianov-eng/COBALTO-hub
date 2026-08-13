import asyncio
import random
import time


async def human_delay_async(min_seconds: float = 1.0, max_seconds: float = 3.0) -> float:
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
    return delay


def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> float:
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    return delay


async def human_delay_between_requests_async(platform: str = "default") -> float:
    platform_delays = {
        "twitter": (2.0, 5.0),
        "instagram": (3.0, 7.0),
        "telegram": (1.0, 3.0),
        "tiktok": (3.0, 8.0),
        "youtube": (2.0, 4.0),
        "facebook": (4.0, 8.0),
        "linkedin": (3.0, 6.0),
        "reddit": (1.5, 3.5),
        "default": (1.0, 3.0),
    }
    min_delay, max_delay = platform_delays.get(platform, platform_delays["default"])
    return await human_delay_async(min_delay, max_delay)


def human_delay_between_requests(platform: str = "default") -> float:
    platform_delays = {
        "twitter": (2.0, 5.0),
        "instagram": (3.0, 7.0),
        "telegram": (1.0, 3.0),
        "tiktok": (3.0, 8.0),
        "youtube": (2.0, 4.0),
        "facebook": (4.0, 8.0),
        "linkedin": (3.0, 6.0),
        "reddit": (1.5, 3.5),
        "default": (1.0, 3.0),
    }
    min_delay, max_delay = platform_delays.get(platform, platform_delays["default"])
    return human_delay(min_delay, max_delay)


def simulate_human_browsing() -> float:
    reading_time = random.uniform(0.5, 2.0)
    time.sleep(reading_time)
    scroll_time = random.uniform(0.2, 0.8)
    time.sleep(scroll_time)
    thinking_time = random.uniform(0.3, 1.0)
    time.sleep(thinking_time)
    return reading_time + scroll_time + thinking_time


async def simulate_human_browsing_async() -> float:
    reading_time = random.uniform(0.5, 2.0)
    await asyncio.sleep(reading_time)
    scroll_time = random.uniform(0.2, 0.8)
    await asyncio.sleep(scroll_time)
    thinking_time = random.uniform(0.3, 1.0)
    await asyncio.sleep(thinking_time)
    return reading_time + scroll_time + thinking_time
