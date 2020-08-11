import asyncio

from datetime import datetime

from aiohttp import ContentTypeError, ClientError

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession, ThresholdReached
from monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, time_now


class BrokenPage(Exception):
    pass


def extract_appid_and_hashname(item_url: str):
    item_url = item_url[len('https://steamcommunity.com/market/listings/'):]
    return item_url.split('/')


def is_immediately_resoldable(page_source: str):
    return '"marketable":1' in page_source and '"market_marketable_restriction"' not in page_source


def extract_item_nameid(page_source: str):
    start = page_source.find('Market_LoadOrderSpread( ')
    if start != -1:
        start += len('Market_LoadOrderSpread( ')
        end = page_source.find(' );', start)
        if end != -1:
            return page_source[start:end]
    raise BrokenPage


class DescriptionMonitor(Monitor):
    def __init__(self, url: str, db_wrapper: DBWrapper):
        super().__init__(url, 0, db_wrapper)
        self.monitor_type = MonitorType.DESCRIPTION

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        try:
            self._last_request_time = datetime.now()
            response = await session.get(url=self.url)
            if response.status == 429:
                return MonitorEvent(self.url, MonitorEventType.TOO_MANY_REQUEST)
            data = await response.text()
        except ThresholdReached:
            return MonitorEvent(self.url, MonitorEventType.REQUEST_LIMIT)
        except ContentTypeError:
            return MonitorEvent(self.url, MonitorEventType.WEB_ERROR)
        except asyncio.TimeoutError:
            return MonitorEvent(self.url, MonitorEventType.TIMEOUT)
        except RuntimeError:
            return MonitorEvent(self.url, MonitorEventType.SESSION_CLOSED)
        except ClientError as e:
            print(e)
            return MonitorEvent(self.url, MonitorEventType.WEB_ERROR)
        except Exception as e:
            print('Unknown exception')
            print(e)
        else:
            try:
                app_id, hash_name = extract_appid_and_hashname(self.url)
                description = {
                    "app_id": app_id,
                    "market_hash_name": hash_name,
                    "is_short_marketable": is_immediately_resoldable(data),
                    'item_nameid': extract_item_nameid(data),
                    'url': self.url
                }
            except BrokenPage:
                return MonitorEvent(self.url, MonitorEventType.WEB_ERROR)
            await self.db_wrapper.add_description(description)
            return MonitorEvent(self.url, MonitorEventType.SUCCESS)

    def get_monitor_type(self):
        return self.monitor_type
