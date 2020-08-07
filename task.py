import asyncio

from abc import ABC, abstractmethod

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession


class Task(ABC):
    def __init__(self, db_wrapper: DBWrapper, period: float):
        self.db_wrapper = db_wrapper
        self.period = period

    @abstractmethod
    async def run(self, session: ABCSteamSession, queue: asyncio.Queue):
        pass