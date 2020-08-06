from abc import ABC

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession


class Task(ABC):
    def __init__(self, db_wrapper: DBWrapper, session: ABCSteamSession, period: float):
        self.db_wrapper = db_wrapper
        self.session = session
        self.period = period

    async def run(self):
        pass