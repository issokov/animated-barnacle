import asyncio
from monitor_manager import MonitorManager
from utils.db_wrapper import DBWrapper, MongoWrapper

from screening_monitor import ScreeningMonitor
from description_monitor import DescriptionMonitor
from pricehistory_monitor import PricehistoryMonitor
from histogram_monitor import HistogramMonitor


class Observer:
    def __init__(self, output_events: asyncio.Queue, db_wrapper: DBWrapper):
        self._observer_queue = output_events
        self._mongo = db_wrapper
        self._monitor_manager = MonitorManager(self._observer_queue)
        self._running = False

    async def run(self):
        self._running = True
        asyncio.create_task(self._monitor_manager.run())
        while self._running:
            await asyncio.sleep(0.001)
        await self._monitor_manager.stop()
        print('Observer and analyzer was stopped')

    async def stop(self):
        self._running = False

    async def make_screening(self, how_many_hundreds: int, app_id='730', period=0):
        urls = []
        for start, delay in zip(range(0, how_many_hundreds, 100), [x * 0.5 for x in range(how_many_hundreds // 100)]):
            url = f"https://steamcommunity.com/market/search/render/?query=&start={start}&count=100&" \
                  f"search_descriptions=0&sort_column=popular&sort_dir=desc&appid={app_id}&norender=1"
            await self._monitor_manager.add_monitor(ScreeningMonitor(url, period, self._mongo), delay)
            urls.append(url)
        return urls

    async def get_description(self, item_url):
        description = await self._mongo.get_description(item_url)
        if not description:
            await self._monitor_manager.run_monitor_with_delay(DescriptionMonitor(item_url, self._mongo))
        return await self._mongo.get_description(item_url)

    async def update_price_history(self, app_id: str, market_hash_name: str, period=0):
        url = "https://steamcommunity.com/market/pricehistory/?currency={currency}" \
              f"&appid={app_id}&market_hash_name={market_hash_name}"
        # TODO make it available for other currencies
        await self._monitor_manager.add_monitor(PricehistoryMonitor(url, period, self._mongo))
        return url

    async def update_histogram(self, app_id: str, market_hash_name: str, period=0):
        desc = await self.get_description(f"https://steamcommunity.com/market/listings/{app_id}/{market_hash_name}")
        item_nameid = desc['item_nameid']
        url = "https://steamcommunity.com/market/itemordershistogram" \
              "?country={country}" \
              "&language={language}" \
              "&currency={currency}" \
              f"&item_nameid={item_nameid}" \
              "&two_factor={two_factor}" \
              "&norender={norender}"
        await self._monitor_manager.add_monitor(HistogramMonitor(url, period, self._mongo))
        return url

async def main():
    q = asyncio.Queue()
    m = MongoWrapper()
    observer = Observer(q, m)
    observer_task = asyncio.create_task(observer.run())
    await asyncio.sleep(3)
    await observer.make_screening(how_many_hundreds=500)
    await observer.update_price_history("730", "Danger%20Zone%20Case")
    await observer.update_histogram("730", "Danger%20Zone%20Case")

    print("Sleep 10 sec")
    await asyncio.sleep(10)
    print("Wake upped")
    await observer.stop()
    await observer_task


if __name__ == "__main__":
    asyncio.run(main())
