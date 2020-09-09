from urllib import parse

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession
from monitors.monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, time_now


def _extract_pure_item(json_item: dict):
    asset = json_item['asset_description']
    if asset['marketable'] and 'market_marketable_restriction' not in asset:
        app_id = str(asset['appid'])
        name = asset['market_hash_name']
        return {
            "time": time_now(),
            "app_id": app_id,
            "market_hash_name": name,
            "count": json_item["sell_listings"],
            "price": json_item["sell_price"] / 100,
            "url": f"https://steamcommunity.com/market/listings/{app_id}/{parse.quote(name)}"
        }


class ScreeningMonitor(Monitor):
    def __init__(self, blank_url: str, period: float, db_wrapper: DBWrapper):
        super().__init__(blank_url, period, db_wrapper)
        self.monitor_type = MonitorType.SCREENING

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        event, data = await self.get_data(session)
        event.set_monitor_type(self.get_monitor_type())  # TODO move it into Monitor(ABC)
        if event.type is MonitorEventType.SUCCESS:
            if not data['results']:
                print('Empty response')
                return MonitorEvent(self.blank_url, MonitorEventType.EMPTY_RESPONSE)
            for item in data['results']:
                pure_item = _extract_pure_item(item)
                if pure_item:
                    await self.db_wrapper.register_item(pure_item)
        return event

    def get_monitor_type(self):
        return self.monitor_type
