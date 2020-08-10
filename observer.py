import asyncio

from datetime import datetime

from monitor import Monitor, MonitorEventType
from utils.steam_session import SteamSession


def get_sleeping_time(monitor: Monitor, delay: float):
    current = datetime.now()
    last_update = monitor.get_request_time()
    last_update = last_update if last_update else current
    true_delay = delay - (current - last_update).total_seconds()
    return max(0., true_delay)


class Observer:
    def __init__(self, output_events: asyncio.Queue):
        # TODO move to config
        self._session = SteamSession('/home/issokov/Desktop/credentials.txt')
        self._sleep_delay = 0.001
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
                asyncio.create_task(self.add_monitor(monitor, delay))
            await asyncio.sleep(self._sleep_delay)

    async def stop(self):
        await self._session.aio_destructor()
        self._running = False

    async def _completed_callback(self, monitor_event):
        monitor = self._monitors[monitor_event.url]
        if monitor_event.event_type is not MonitorEventType.SUCCESS:
            print("Unsuccessful task execution: MonitorEventType: ", monitor_event.event_type)
            # TODO: case when threshold limitation, no internet, etc...
            if self._running:
                await self._run_task_queue.put((monitor, 0))
                # We can't call add_monitor immediately for to be protected from stack overflow
        else:
            print("You should put result in output queue", datetime.now())

            if monitor.period:
                if self._running:
                    await self._run_task_queue.put((monitor, monitor.period))
            else:
                self._monitors.pop(monitor.url)

    async def add_monitor(self, monitor: Monitor, delay=0):
        sleeping_time = get_sleeping_time(monitor, delay)
        print(f"Sleep for {sleeping_time}")
        await asyncio.sleep(sleeping_time)
        self._monitors[monitor.url] = monitor
        monitor_event = await monitor.run(self._session)
        await self._completed_callback(monitor_event)
