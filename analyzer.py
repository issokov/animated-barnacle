import asyncio
from observer import Observer
from utils.db_wrapper import MongoWrapper

from screening_monitor import ScreeningMonitor
from description_monitor import DescriptionMonitor


class Analyzer:
    def __init__(self):
        self._observer_queue = asyncio.Queue()
        self._observer = Observer(self._observer_queue)
        self._mongo = MongoWrapper()
        self._running = False

    async def run(self):
        self._running = True
        asyncio.create_task(self._observer.run())
        while self._running:
            await asyncio.sleep(0.001)
        await self._observer.stop()
        print('Observer and analyzer was stopped')

    async def stop(self):
        self._running = False

    async def make_screening(self, how_much):
        for start, delay in zip(range(0, how_much, 100), [x * 0.5 for x in range(how_much // 100)]):
            url = f"https://steamcommunity.com/market/search/render/?query=&start={start}&count=100&" \
                  f"search_descriptions=0&sort_column=popular&sort_dir=desc&appid=730&norender=1"
            await self._observer.add_monitor(ScreeningMonitor(url, 0, self._mongo), delay)

    async def get_description(self, item_url):
        description = await self._mongo.get_description(item_url)
        if not description:
            await self._observer.run_monitor_with_delay(DescriptionMonitor(item_url, self._mongo))
        return await self._mongo.get_description(item_url)


async def main():
    analyzer = Analyzer()
    task = asyncio.create_task(analyzer.run())
    await asyncio.sleep(5)
    print(await analyzer.get_description('https://steamcommunity.com/market/listings/730/Danger%20Zone%20Case'))
    print("Sleep 10 sec")
    await asyncio.sleep(10)
    print("Wake upped")
    await analyzer.stop()
    await task


if __name__ == "__main__":
    asyncio.run(main())
