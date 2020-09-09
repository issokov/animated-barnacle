import asyncio

from datetime import datetime

from monitors.monitor import Monitor, MonitorEventType
from utils.steam_session import SteamSession


def get_sleeping_time(monitor: Monitor, delay: float):
    current = datetime.now()
    last_update = monitor.get_request_time()
    last_update = last_update if last_update else current
    true_delay = delay - (current - last_update).total_seconds()
    return max(0., true_delay)


class MonitorManager:
    def __init__(self, output_events: asyncio.Queue):
        # TODO move to config
        self._session = SteamSession('/home/issokov/Desktop/credentials.txt')
        self._sleep_delay = 0.001
        self._output_events = output_events
        self.inited = False
        self._running = False
        self._monitors = dict()
        self._monitors_to_run = asyncio.Queue()

    async def init(self):
        if not self.inited:
            await self._session.init_session()
            self.inited = True

    async def run(self):
        await self.init()
        self._running = True

        while self._running:
            while not self._monitors_to_run.empty() and self._running:
                monitor, delay = await self._monitors_to_run.get()
                asyncio.create_task(self.run_monitor_with_delay(monitor, delay))
            await asyncio.sleep(self._sleep_delay)

        await self._session.aio_destructor()
        self.inited = False

    async def stop(self):
        self._running = False
        while self.inited:
            await asyncio.sleep(self._sleep_delay)

    async def _completed_callback(self, monitor_event):
        m_e_t = monitor_event.type
        await self._output_events.put(monitor_event)
        monitor = self._monitors.get(monitor_event.url, None)
        if monitor and self._running:
            if monitor_event.type is not MonitorEventType.SUCCESS:
                print(f"Unsuccessful event:\n{monitor_event}")
                if m_e_t is MonitorEventType.TIMEOUT or m_e_t is MonitorEventType.WEB_ERROR:
                    await self.add_monitor(monitor, 5)
                elif m_e_t is MonitorEventType.TOO_MANY_REQUEST:
                    await self.add_monitor(monitor, 300)
                    print("Too many requsts....")
            elif monitor.period:
                await self.add_monitor(monitor, monitor.period)

    async def add_monitor(self, monitor: Monitor, delay=0):
        await self._monitors_to_run.put((monitor, delay))

    def remove_monitor(self, monitor_url):
        self._monitors.pop(monitor_url)

    async def run_monitor_with_delay(self, monitor: Monitor, delay=0):
        sleeping_time = get_sleeping_time(monitor, delay)
        await asyncio.sleep(sleeping_time)
        self._monitors[monitor.blank_url] = monitor
        monitor_event = await monitor.run(self._session)
        await self._completed_callback(monitor_event)
