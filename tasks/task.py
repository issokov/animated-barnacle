import asyncio
from abc import ABC, abstractmethod

from observer import Observer
from utils.db_wrapper import DBWrapper
from monitors.monitor import MonitorEvent


class Task(ABC):
    def __init__(self, observer: Observer, db_wrapper: DBWrapper, output_queue: asyncio.Queue):
        self.observer = observer
        self.db_wrapper = db_wrapper
        self.output_queue = output_queue

    @abstractmethod
    async def run(self, _id: int):
        pass

    @abstractmethod
    async def put_event(self, monitor_event: MonitorEvent):
        pass


