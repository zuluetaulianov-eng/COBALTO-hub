import asyncio
import json
import logging

from cobalto_worker import SafeEncoder
from dashboard import get_dashboard_data

logging.basicConfig(level=logging.DEBUG)


async def main():
    try:
        res = await get_dashboard_data(priority_only=False)
        print("Result:", "OK" if res else "FAILED")
        if res:
            with open("dashboard_persistent_cache.json", "w", encoding="utf-8") as f:
                json.dump(res, f, cls=SafeEncoder, ensure_ascii=False)
            print("Cache guardado exitosamente.")
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    asyncio.run(main())
