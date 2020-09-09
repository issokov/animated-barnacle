import asyncio

from monitors.monitor import MonitorEvent, MonitorEventType
from observer import Observer
from tasks.task import Task
from utils.db_wrapper import DBWrapper


class CollectorTask(Task):
    def __init__(self, observer: Observer, db_wrapper: DBWrapper, output_queue: asyncio.Queue):
        super().__init__(observer, db_wrapper, output_queue)
        self.items_count = 1500
        self.completed = set()
        self.running = False

    async def run(self, _id: int):
        self.running = True
        await self.observer.make_screening(_id, self.items_count, app_id='730')
        while self.running:
            await asyncio.sleep(1)
        print('Collector task completed')

    async def put_event(self, monitor_event: MonitorEvent):
        if monitor_event.type is MonitorEventType.SUCCESS:
            self.completed.add(str(monitor_event))
            print('Event accepted')
        else:
            print(f'Oops error: {monitor_event}')
        if len(self.completed) == self.items_count // 100:
            self.running = False