import asyncio

from monitor import Monitor, MonitorEventType
from utils.steam_session import SteamSession


class Observer:
    def __init__(self, output_events: asyncio.Queue):
        # TODO move to config
        self._session = SteamSession('/home/issokov/Desktop/credentials.txt')
        self._sleep_delay = 0.01
        self._output_events = output_events
        self._session_inited = False
        self._running = False
        self._monitors = dict()
        self._run_task_queue = asyncio.Queue()

    async def init(self):
        if not self._session_inited:
            await self._session.try_init_cookies()
            self._session_inited = True

    async def run(self):
        await self.init()
        self._running = True
        while self._running:
            while not self._run_task_queue.empty() and self._running:
                monitor, delay = await self._run_task_queue.get()
                await self.add_monitor(monitor, delay)
            await asyncio.sleep(self._sleep_delay)

    async def stop(self):
        await self._session.aio_destructor()
        self._running = False

    async def _completed_callback(self, monitor_event):
        monitor = self._monitors[monitor_event.url]
        if monitor_event.event_type is not MonitorEventType.SUCCESS:
            print("Unsuccessful task execution: MonitorEventType: ", monitor_event.event_type)
            # TODO: case when threshold limitation, no internet, etc...
            await self._run_task_queue.put((monitor, 0))
        else:
            print("You should put result in output queue")
            if monitor.period:
                await self._run_task_queue.put((monitor, monitor.period))
            else:
                self._monitors.pop(monitor.url)

    async def add_monitor(self, monitor: Monitor, delay=0):
        await asyncio.sleep(delay)
        self._monitors[monitor.url] = monitor
        monitor_event = await monitor.run(self._session)
        await self._completed_callback(monitor_event)
