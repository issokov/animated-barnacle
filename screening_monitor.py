import asyncio

from datetime import datetime

from urllib import parse
from aiohttp import ContentTypeError, ClientError

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession, ThresholdReached
from monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, time_now


def _extract_pure_item(json_item: dict):
    asset = json_item['asset_description']
    if asset['marketable'] and 'market_marketable_restriction' not in asset:
        app_id = asset['appid']
        name = asset['market_hash_name']
        return {
            "time": time_now(),
            "app_id": app_id,
            "market_hash_name": name,
            "count": json_item["sell_listings"],
            "price": json_item["sell_price"],
            "link": f"https://steamcommunity.com/market/listings/{app_id}/{parse.quote(name)}"
        }


class ScreeningMonitor(Monitor):
    def __init__(self, url: str, period: float, db_wrapper: DBWrapper):
        super().__init__(url, period, db_wrapper)
        self.monitor_type = MonitorType.SCREENING

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        try:
            self._last_request_time = datetime.now()
            response = await session.get(url=self.url)
            data = await response.json()
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
            if response.status == 429:
                return MonitorEvent(self.url, MonitorEventType.TOO_MANY_REQUEST)
            if data['success'] != 1:
                print('Cannot collect items: wrong API')
                return MonitorEvent(self.url, MonitorEventType.WEB_ERROR)
            if not data['results']:
                print('Empty response')
                return MonitorEvent(self.url, MonitorEventType.EMPTY_RESPONSE)
            for item in data['results']:
                pure_item = _extract_pure_item(item)
                if pure_item:
                    await self.db_wrapper.register_item(pure_item)
            return MonitorEvent(self.url, MonitorEventType.SUCCESS)

    def get_monitor_type(self):
        return self.monitor_type
