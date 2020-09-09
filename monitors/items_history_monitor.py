from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession
from monitors.monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, find_between, time_now, fill_url_blank


class ItemsHistoryMonitory(Monitor):
    def __init__(self, blank_url: str, period: float, db_wrapper: DBWrapper):
        super().__init__(blank_url, period, db_wrapper)
        self.monitor_type = MonitorType.INVENTORY

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        event, data = await self.get_data(session)
        event.set_monitor_type(self.get_monitor_type())  # TODO move it into Monitor(ABC)
        if event.type is MonitorEventType.SUCCESS:
            pass
        return event

    def get_monitor_type(self):
        return self.monitor_type
