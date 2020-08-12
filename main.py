import asyncio
from observer import MonitorManager
from screening_monitor import ScreeningMonitor
from utils.db_wrapper import MongoWrapper


async def main():
    queue = asyncio.Queue()
    mongo = MongoWrapper()
    observer = MonitorManager(queue)
    asyncio.create_task(observer.run())

    url = f"https://steamcommunity.com/market/search/render/?query=&start=0&count=100&" \
          f"search_descriptions=0&sort_column=popular&sort_dir=desc&appid=730&norender=1"
    task = ScreeningMonitor(url, 1, mongo)
    await observer.add_monitor(task)

    print("Main loop goes sleep")
    await asyncio.sleep(30)
    print("Main loop wake up")

    await observer.stop()
    print("Return")


if __name__ == "__main__":
    asyncio.run(main())
