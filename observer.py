import asyncio
from monitors.monitor_manager import MonitorManager
from monitors.monitor import MonitorType, MonitorEvent
from utils.db_wrapper import DBWrapper

from monitors.screening_monitor import ScreeningMonitor
from monitors.description_monitor import DescriptionMonitor
from monitors.pricehistory_monitor import PricehistoryMonitor
from monitors.histogram_monitor import HistogramMonitor


class Observer:
    def __init__(self, output_events: asyncio.Queue, db_wrapper: DBWrapper):
        self._output_events = output_events
        self._mongo = db_wrapper
        self._monitor_manager_events = asyncio.Queue()
        self._monitor_manager = MonitorManager(self._monitor_manager_events)
        self._running = False
        self._is_stopped = False
        self._owners = dict()

    async def run(self):
        self._running = True
        self._is_stopped = False
        asyncio.create_task(self._monitor_manager.run())

        while self._running:
            while not self._monitor_manager_events.empty():
                monitor_event = await self._monitor_manager_events.get()
                await self.match_event_with_owner(monitor_event)
            await asyncio.sleep(0.001)

        await self._monitor_manager.stop()
        self._is_stopped = True
        print('Observer was stopped')

    async def match_event_with_owner(self, monitor_event: MonitorEvent):
        owner = self._owners.get(monitor_event.url, None)
        # description is support monitor for other monitors
        if owner is None and monitor_event.monitor_type is not MonitorType.DESCRIPTION:
            print(f'Event without owner {monitor_event}')
            self.stop_monitor(monitor_event.url)
        else:
            monitor_event.owner = owner
            await self._output_events.put(monitor_event)

    async def stop(self):
        self._running = False
        while not self._is_stopped:
            await asyncio.sleep(0.001)

    def stop_monitor(self, monitor_url):
        self._monitor_manager.remove_monitor(monitor_url)

    async def make_screening(self, owner: int, how_many_hundreds: int, app_id='730', period=0):
        for start, delay in zip(range(0, how_many_hundreds, 100), [x * 0.5 for x in range(how_many_hundreds // 100)]):
            url = f"https://steamcommunity.com/market/search/render/?query=&start={start}&count=100&" \
                  f"search_descriptions=0&sort_column=popular&sort_dir=desc&appid={app_id}&norender=1"
            self._owners[url] = owner
            await self._monitor_manager.add_monitor(ScreeningMonitor(url, period, self._mongo), delay)

    async def get_description(self, item_url):
        description = await self._mongo.get_description(item_url)
        if not description:
            await self._monitor_manager.run_monitor_with_delay(DescriptionMonitor(item_url, self._mongo))
        return await self._mongo.get_description(item_url)

    async def update_price_history(self, owner: int, app_id: str, market_hash_name: str, period=0):
        url = "https://steamcommunity.com/market/pricehistory/?currency={currency}" \
              f"&appid={app_id}&market_hash_name={market_hash_name}"
        # TODO make it available for other currencies
        self._owners[url] = owner
        await self._monitor_manager.add_monitor(PricehistoryMonitor(url, period, self._mongo))

    async def run_inventory_manager(self, owner: int, input_queue: asyncio.Queue, output_queue: asyncio.Queue):
        url = "https://steamcommunity.com/market/myhistory/?query=&start=0&count=100&norender={norender}"


    async def update_histogram(self, owner: int, app_id: str, market_hash_name: str, period=0):
        desc = await self.get_description(f"https://steamcommunity.com/market/listings/{app_id}/{market_hash_name}")
        item_nameid = desc['item_nameid']
        url = "https://steamcommunity.com/market/itemordershistogram" \
              "?country={country}" \
              "&language={language}" \
              "&currency={currency}" \
              f"&item_nameid={item_nameid}" \
              "&two_factor={two_factor}" \
              "&norender={norender}"
        self._owners[url] = owner
        print(owner)  # TODO if db is empty cause error /no owner/ what the reason?
        await self._monitor_manager.add_monitor(HistogramMonitor(url, period, self._mongo))
