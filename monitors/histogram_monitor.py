from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession
from monitors.monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, find_between, time_now, fill_url_blank


class BrokenPage(Exception):
    pass


class WrongCurrency(Exception):
    pass


def reformat_histogram(raw) -> dict:
    return {
        'timestamp': time_now(),
        'sell_count': int(raw['sell_order_count'].replace(',', '')),
        'buy_count': int(raw['buy_order_count'].replace(',', '')),
        'sell': list(map(lambda x: x[:2], raw['sell_order_graph'])),
        'buy': list(map(lambda x: x[:2], raw['buy_order_graph']))
    }


class HistogramMonitor(Monitor):
    def __init__(self, blank_url: str, period: float, db_wrapper: DBWrapper):
        super().__init__(blank_url, period, db_wrapper)
        self.monitor_type = MonitorType.HISTOGRAM

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        event, data = await self.get_data(session)
        event.set_monitor_type(self.get_monitor_type())  # TODO move it into Monitor(ABC)
        if event.type is MonitorEventType.SUCCESS:
            expected_currency = session.get_account_preferences()['price_suffix']
            if data["price_suffix"].encode('utf-8') == expected_currency.encode('utf-8'):
                histogram = reformat_histogram(data)
                item_nameid = find_between('item_nameid=', '&', fill_url_blank(self.blank_url, session))
                await self.db_wrapper.update_histogram(item_nameid, histogram)
            else:
                raise WrongCurrency(
                    f"Wrong currency: expected '{expected_currency.encode('utf-8')}'"
                    f" got '{data['price_suffix'].encode('utf-8')}'")
        return event

    def get_monitor_type(self):
        return self.monitor_type
