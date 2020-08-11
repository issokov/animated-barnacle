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
    SESSION_CLOSED = 5
    TOO_MANY_REQUEST = 6

@unique
class MonitorType(Enum):
    SCREENING = 0
    DESCRIPTION = 1
    PRICE_HISTORY = 2
    HISTOGRAM = 3


class MonitorEvent:
    def __init__(self, url: str, event_type: MonitorEventType):
        self.url = url
        self.event_type = event_type


class Monitor(ABC):
    def __init__(self, url: str, period: float, db_wrapper: DBWrapper):
        self.url = url
        self.period = period
        self.db_wrapper = db_wrapper
        self._last_request_time = None

    @abstractmethod
    async def run(self, session: ABCSteamSession):
        pass

    @abstractmethod
    def get_monitor_type(self):
        pass

    def get_request_time(self) -> datetime:
        return self._last_request_time