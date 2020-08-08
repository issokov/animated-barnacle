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
        self.running_tasks = []

    async def init(self):
        if not self.session_inited:
            await self.session.try_init_cookies()
            self.session_inited = True

    async def run(self):
        await self.init()
        self.running = True
        while self.running:
            while self.running_tasks:
                done, pending = await asyncio.wait(self.running_tasks, return_when=asyncio.FIRST_COMPLETED)
                self.running_tasks = pending
                await asyncio.sleep(self.sleep_delay)
            await asyncio.sleep(self.sleep_delay)

    async def add_task(self, task: Task):
        self.running_tasks.append(asyncio.create_task(task.run(self.session, self.output_events)))

