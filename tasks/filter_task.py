from enum import Enum, unique

from pprint import pprint
import numpy as np
import asyncio
import matplotlib.pyplot as mpl

from collections import defaultdict
from datetime import datetime, timedelta

from monitors.monitor import MonitorEvent, MonitorEventType, extract_appid_and_hashname, cut_history
from observer import Observer
from tasks.task import Task
from utils.db_wrapper import DBWrapper


@unique
class HistorySituation(Enum):
    GROW = 0
    FELL = 1
    BOUNCE_UP = 2
    UNKNOWN = 3
    HIGH_DISPERSION = 4
    LITTLE_DATA = 7


class HistoryStats:
    def __init__(self, history):
        self._history = history
        self.smoothed = None
        self.cutted_true = None
        self.time_for_smoothed = None
        self.histogram = None

    def get_average(self, start, finish):
        _, price, _ = zip(*cut_history(self._history, start, finish))
        return sum(price) / len(price)

    @property
    def dispersion(self, low_quantile=0.05, high_quantile=0.9):
        return np.quantile(self.histogram, high_quantile) - np.quantile(self.histogram, low_quantile)

    @property
    def average_sells(self):
        time, price, count = zip(*cut_history(self._history, 0, 30 * 7))
        return sum(count) / len(count)

    @property
    def profit_per_day(self, taxes=0.1):
        profit_price = self.get_average(0, 90 * 24) * taxes / 2
        leveled = np.array(self.cutted_true) - self.smoothed
        buy_price = -profit_price
        sell_price = profit_price
        bought, fixed_profit = False, 0
        high, low = [], []
        for stamp, price in zip(self.time_for_smoothed, leveled):
            if price < buy_price and not bought:
                bought = True
                low.append((stamp, price))
            elif price > sell_price and bought:
                bought = False
                fixed_profit += 1
                high.append((stamp, price))
        return fixed_profit / 90

    def get_trend(self, start, finish):
        time, price, count = zip(*cut_history(self._history, start, finish))
        return np.polyfit(time, price, deg=1)[0]

    def calc_deviations(self):
        window_size = 24
        time, price, count = zip(*cut_history(self._history, 0, 30 * 24))
        box = np.ones(window_size) / window_size
        self.smoothed = np.convolve(price, box, mode='same')
        median = self.get_average(0, 90 * 24)
        start, finish = window_size // 2, -window_size // 2
        self.cutted_true = np.array(price[start:finish])
        self.smoothed = self.smoothed[start:finish]
        self.time_for_smoothed = time[start:finish]
        self.histogram = [int((smooth - real) / median * 100) for real, smooth in zip(self.cutted_true, self.smoothed)]

    def get_type(self):
        self.calc_deviations()
        if self.profit_per_day > 0.8 and self.dispersion > 20 and self.get_trend(0, 24) > 0 and self.average_sells > 10:
            print(self.average_sells)
            return HistorySituation.HIGH_DISPERSION
        return HistorySituation.UNKNOWN


def get_history_situation(history: list) -> HistorySituation:
    if datetime.utcnow().timestamp() - history[0][0] > timedelta(
            days=180).total_seconds():  # It's old stabilized item
        return HistoryStats(history).get_type()
    return HistorySituation.LITTLE_DATA


class FilterTask(Task):
    min_price = 1.0
    max_price = 100.0
    min_count = 300

    def __init__(self, observer: Observer, db_wrapper: DBWrapper, output_queue: asyncio.Queue):
        super().__init__(observer, db_wrapper, output_queue)
        self._running = False
        self._completed_count = 0
        self._rude_items = []
        self._price_histories = dict()
        self._classified = defaultdict(list)

    def init_parameters(self, min_count, min_price, max_price):
        self.min_price = min_price
        self.max_price = max_price
        self.min_count = min_count

    async def run(self, _id: int):
        self._running = True
        self._rude_items = await self.db_wrapper.get_registered(self.min_count, self.min_price, self.max_price)
        print(f"Founded {len(self._rude_items)}")
        for item in self._rude_items:
            identifier = (item['app_id'], item['market_hash_name'])
            price_history = await self.db_wrapper.get_price_history(*identifier)
            if not price_history or (datetime.utcnow().timestamp() - price_history["history"][-1][0]) > 7200:
                await self.observer.update_price_history(_id, *identifier)
            else:
                self._price_histories[identifier] = price_history
                self._classified[get_history_situation(price_history['history'])].append(identifier)
                self._completed_count += 1
        while self._completed_count != len(self._rude_items):
            await asyncio.sleep(1)
        for item in self._classified[HistorySituation.HIGH_DISPERSION]:
            self.show_plot(*item)
        pprint(self._classified)
        print('FilterPriceHistory task completed')

    def show_plot(self, app_id: str, market_hash_name: str):
        price_history = self._price_histories[(app_id, market_hash_name)]
        time, price, count = zip(*cut_history(price_history['history'], 0, 7 * 24))
        y = np.polyval(np.polyfit(time, price, deg=3), time)
        mpl.plot(time, y, 'r')
        mpl.plot(time, price)
        mpl.title(market_hash_name)
        mpl.show()

    async def put_event(self, monitor_event: MonitorEvent):
        if monitor_event.type is MonitorEventType.SUCCESS:
            self._completed_count += 1
            identifier = extract_appid_and_hashname(monitor_event.url)
            price_history = await self.db_wrapper.get_price_history(*identifier)
            self._price_histories[identifier] = price_history
            self._classified[get_history_situation(price_history['history'])].append(identifier)
        else:
            print(monitor_event)
