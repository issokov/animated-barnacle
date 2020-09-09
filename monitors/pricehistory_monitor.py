from datetime import datetime, timezone

from utils.db_wrapper import DBWrapper
from utils.steam_session import ABCSteamSession
from monitors.monitor import Monitor, MonitorEvent, MonitorType, MonitorEventType, extract_appid_and_hashname


class BrokenPage(Exception):
    pass


class WrongCurrency(Exception):
    pass


def reformat_price_history(raw, app_id: str, market_hash_name: str) -> dict:
    """
    list of 3 items:
        - steam formatted datetime
        - median price
        - solds count
    :param:
    :return:
    """
    history = []
    for record in raw['prices']:
        normalized_datetime = datetime.strptime(record[0], "%b %d %Y %H: +0")  # .astimezone(tz=timezone.utc)
        history.append([int(normalized_datetime.timestamp()), record[1], int(record[2])])
    return {'app_id': app_id, 'market_hash_name': market_hash_name, 'history': history}


class PricehistoryMonitor(Monitor):
    def __init__(self, blank_url: str, period: float, db_wrapper: DBWrapper):
        super().__init__(blank_url, period, db_wrapper)
        self.monitor_type = MonitorType.PRICEHISTORY

    async def run(self, session: ABCSteamSession) -> MonitorEvent:
        # TODO LOGS
        event, data = await self.get_data(session)
        event.set_monitor_type(self.get_monitor_type())  # TODO move it into Monitor(ABC)
        if event.type is MonitorEventType.SUCCESS:
            expected_currency = session.get_account_preferences()['price_suffix']
            if data["price_suffix"].encode('utf-8') == expected_currency.encode('utf-8'):
                app_id, market_hash_name = extract_appid_and_hashname(self.blank_url)
                price_history = reformat_price_history(data, app_id, market_hash_name)
                await self.db_wrapper.update_price_history(app_id, market_hash_name, price_history)
            elif not data["price_suffix"].encode('utf-8'):
                event.type = MonitorEventType.TIMEOUT
                return event
            else:
                raise WrongCurrency(
                    f"Wrong currency: expected '{expected_currency.encode('utf-8')}'"
                    f" got '{data['price_suffix'].encode('utf-8')}'")
        return event

    def get_monitor_type(self):
        return self.monitor_type
