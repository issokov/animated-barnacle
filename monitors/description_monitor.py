from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession
from monitors.monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, extract_appid_and_hashname


class BrokenPage(Exception):
    pass


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
    def __init__(self, blank_url: str, db_wrapper: DBWrapper):
        super().__init__(blank_url, 0, db_wrapper)
        self.monitor_type = MonitorType.DESCRIPTION

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        event, data = await self.get_data(session, return_json=False)
        event.set_monitor_type(self.get_monitor_type())  # TODO move it into Monitor(ABC)
        if event.type is MonitorEventType.SUCCESS:
            try:
                app_id, hash_name = extract_appid_and_hashname(self.blank_url)
                description = {
                    "app_id": app_id,
                    "market_hash_name": hash_name,
                    "is_short_marketable": is_immediately_resoldable(data),
                    'item_nameid': extract_item_nameid(data),
                    'url': self.blank_url
                }
            except BrokenPage:
                return MonitorEvent(self.blank_url, MonitorEventType.WEB_ERROR)
            await self.db_wrapper.add_description(description)
        return event

    def get_monitor_type(self):
        return self.monitor_type
