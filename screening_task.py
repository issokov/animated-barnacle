import asyncio

from aiohttp import ContentTypeError, ClientError, ServerTimeoutError
from hashlib import sha1

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession, ThresholdReached
from task import Task, TaskEvent, TaskType, TaskEventType, time_now


async def _extract_pure_item(json_item: dict):
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


class ScreeningTask(Task):
    def __init__(self, url: str, period: float, db_wrapper: DBWrapper):
        super().__init__(db_wrapper, period)
        self.task_type = TaskType.SCREENING
        self.url = url
        self.id = sha1(f"{self.task_type}-{url}".encode('utf-8'))

    async def run(self, session: ABCSteamSession, queue: asyncio.Queue):
        # TODO LOGS
        try:
            response = await session.get(url=self.url)
            data = await response.json()
        except ThresholdReached:
            await queue.put(TaskEvent(self.url, TaskEventType.REQUEST_LIMIT))
        except ContentTypeError:
            await queue.put(TaskEvent(self.url, TaskEventType.WEB_ERROR))
        except ServerTimeoutError:
            await queue.put(TaskEvent(self.url, TaskEventType.REQUEST_TIMEOUT))
        except ClientError as e:
            print(e)
            await queue.put(TaskEvent(self.url, TaskEventType.WEB_ERROR))
        else:
            if data['success'] != 1:
                print('Cannot collect items: wrong API')
                await queue.put(TaskEvent(self.url, TaskEventType.WEB_ERROR))
                return
            if not data['results']:
                print('Empty response')
                await queue.put(TaskEvent(self.url, TaskEventType.EMPTY_RESPONSE))
                return
            for item in data['results']:
                pure_item = _extract_pure_item(item)
                await self.db_wrapper.register_item(pure_item)
                await queue.put(TaskEvent(self.url, TaskEventType.FINISHED))

    def __hash__(self):
        return self.id

    async def get_task_type(self) -> int:
        return self.task_type
