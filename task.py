import asyncio

from enum import Enum, unique
from abc import ABC, abstractmethod
from datetime import datetime

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession


def time_now():
    return int(datetime.utcnow().timestamp())


@unique
class TaskEventType(Enum):
    SUCCESS = 0  # For periodic requests
    TIMEOUT = 1
    FINISHED = 2  # For one time request
    WEB_ERROR = 3
    EMPTY_RESPONSE = 4
    REQUEST_LIMIT = 5


@unique
class TaskType:
    SCREENING = 0
    PRICE_HISTORY = 1
    HISTOGRAM = 2


class TaskEvent:
    def __init__(self, url: str, task_event_type: TaskEventType):
        self.url = url
        self.task_event_type = task_event_type


class Task(ABC):
    def __init__(self, db_wrapper: DBWrapper, period: float):
        self.db_wrapper = db_wrapper
        self.period = period

    @abstractmethod
    async def run(self, session: ABCSteamSession, queue: asyncio.Queue):
        pass

    @abstractmethod
    async def get_task_type(self) -> int:
        pass

    @abstractmethod
    def __hash__(self):
        pass
