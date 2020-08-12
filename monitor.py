import asyncio
from aiohttp import ContentTypeError, ClientError

from enum import Enum, unique
from abc import ABC, abstractmethod
from datetime import datetime

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession, ThresholdReached


def time_now():
    return int(datetime.utcnow().timestamp())


def find_between(left: str, right: str, source: str):
    start = source.find(left)
    if start != -1:
        start += len(left)
        if right:
            finish = source.find(right, start)
            if finish != -1:
                return source[start:finish]
        else:
            return source[start:]
    return None


def extract_appid_and_hashname(item_url: str):
    if 'https://steamcommunity.com/market/listings/' in item_url:
        item_url = item_url[len('https://steamcommunity.com/market/listings/'):]
        return item_url.split('/')
    elif 'https://steamcommunity.com/market/pricehistory/' in item_url:
        app_id = find_between('appid=', '&', item_url)
        market_hash_name = find_between('market_hash_name=', '', item_url)
        return app_id, market_hash_name
    else:
        raise RuntimeError(f'Cannot extract app_id, hash_name, from {item_url}')


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
    PRICEHISTORY = 2
    HISTOGRAM = 3


class MonitorEvent:
    def __init__(self, url: str, event_type: MonitorEventType):
        self.url = url
        self.event_type = event_type


def fill_url_blank(blank_url: str, session: ABCSteamSession):
    preferences = session.get_account_preferences()
    return blank_url.format(**preferences)


class Monitor(ABC):
    def __init__(self, blank_url: str, period: float, db_wrapper: DBWrapper):
        self.blank_url = blank_url
        self.period = period
        self.db_wrapper = db_wrapper
        self._last_request_time = None

    async def get_data(self, session: ABCSteamSession, return_json=True):
        """Returns (MonitorEvent, data)"""
        try:
            self._last_request_time = datetime.now()
            response = await session.get(url=fill_url_blank(self.blank_url, session))
            if response.status == 429:
                return MonitorEvent(self.blank_url, MonitorEventType.TOO_MANY_REQUEST), None
            success_event = MonitorEvent(self.blank_url, MonitorEventType.SUCCESS)
            if return_json:
                data = await response.json()
                if data['success'] != 1:
                    print('Cannot collect items: wrong API')
                    return MonitorEvent(self.blank_url, MonitorEventType.WEB_ERROR), None
                return success_event, data
            else:
                return success_event, await response.text()
        except ThresholdReached:
            return MonitorEvent(self.blank_url, MonitorEventType.REQUEST_LIMIT), None
        except ContentTypeError:
            return MonitorEvent(self.blank_url, MonitorEventType.WEB_ERROR), None
        except asyncio.TimeoutError:
            return MonitorEvent(self.blank_url, MonitorEventType.TIMEOUT), None
        except RuntimeError:
            return MonitorEvent(self.blank_url, MonitorEventType.SESSION_CLOSED), None
        except ClientError as e:
            print(e)
            return MonitorEvent(self.blank_url, MonitorEventType.WEB_ERROR), None
        except Exception as e:
            print(f'Unknown exception: {e}')
            return MonitorEvent(self.blank_url, MonitorEventType.WEB_ERROR), None

    @abstractmethod
    async def run(self, session: ABCSteamSession):
        pass

    @abstractmethod
    def get_monitor_type(self):
        pass

    def get_request_time(self) -> datetime:
        return self._last_request_time
