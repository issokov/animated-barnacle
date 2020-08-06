import asyncio

from task import Task
from utils.steam_session import SteamSession


class Observer:
    def __init__(self, output_events: asyncio.Queue):
        # TODO move to config
        self.session = SteamSession('/home/issokov/Desktop/credentials.txt')
        self.sleep_delay = 0.01
        self.output_events = output_events
        self.session_inited = False
        self.running = False

    async def run(self):
        if not self.session_inited:
            await self.session.try_init_cookies()
            self.session_inited = True
        self.running = True
        while self.running:

            await asyncio.sleep(self.sleep_delay)

    async def add_task(self, task: Task):
        # Read about callbacks, pool executors.. etc.
        pass