import asyncio

from enum import Enum, unique
from abc import ABC, abstractmethod
from datetime import datetime

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession


def time_now():
    return int(datetime.utcnow().timestamp())


@unique
class MonitorEventType(Enum):
    SUCCESS = 0
    TIMEOUT = 1
    WEB_ERROR = 2
    EMPTY_RESPONSE = 3
    REQUEST_LIMIT = 4


@unique
class MonitorType(Enum):
    SCREENING = 0
    PRICE_HISTORY = 1
    HISTOGRAM = 2


class MonitorEvent:
    def __init__(self, url: str, m_e_t: MonitorEventType):
        self.url = url
        self.event_type = m_e_t


class Monitor(ABC):
    def __init__(self, url: str, period: float, db_wrapper: DBWrapper):
        self.url = url
        self.period = period
        self.db_wrapper = db_wrapper

    @abstractmethod
    async def run(self, session: ABCSteamSession):
        pass

    @abstractmethod
    def get_monitor_type(self):
        pass