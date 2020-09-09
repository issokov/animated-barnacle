from datetime import datetime, timedelta
from collections import defaultdict
from bisect import bisect_left

import numpy

BUYER_TAX, SELLER_TAX = 0.869, 1.15


def round_penny(value: float):
    return int(100 * (value + 0.005)) / 100


class Slice:

    def __init__(self, timestamp: float, slice_default_dict):
        self.timestamp = timestamp
        self.slice = slice_default_dict

    def __sub__(self, other):
        result = self.slice.copy()
        for price, count in other.slice.items():
            result[price] -= count
        return Slice(other.timestamp, result)

    def get(self, high_or_low=True):
        prices = sorted(self.slice.keys(), reverse=high_or_low)
        for price in prices:
            if self.slice[price] > 0:
                return price

    def __iter__(self):
        return iter((self.timestamp, self.slice))

    def __lt__(self, other):
        return self.timestamp < other.timestamp


class MarketStats:
    max_permitted_delay = 600
    min_duration = 3600 * 3
    max_average_delay = 300
    min_value, average, max_value = 0, None, float('+inf')
    authority = 3600 * 24 * 2

    def __init__(self, **kwargs):
        self.init_arguments(kwargs)
        self.buy_accumulator = list([Slice(0, dict())])
        self.sell_accumulator = list([Slice(0, dict())])
        self.status = None
        self.price_history = None

    def init_arguments(self, kwargs):
        self.max_permitted_delay = kwargs.pop('max_permitted_delay', self.max_permitted_delay)
        self.min_duration = kwargs.pop('min_duration', self.min_duration)
        self.max_average_delay = kwargs.pop('max_average_delay', self.max_average_delay)
        self.min_value = kwargs.pop('min_value', self.min_value)
        self.max_value = kwargs.pop('max_value', self.max_value)
        self.average = kwargs.pop('average', self.average)
        if len(kwargs):
            raise NameError(f'Unknown MarketStats parameters: {kwargs}')

    def add_histogram(self, order_book):
        time = order_book['timestamp']
        previous_time = self.buy_accumulator[-1].timestamp
        if time < previous_time:
            raise ValueError(f"New order book timestamp should be greater than others:\n{previous_time} < {time}")
        elif time > previous_time:
            self.buy_accumulator.append(Slice(time, dict(self.buy_accumulator[-1].slice)))
            self.sell_accumulator.append(Slice(time, dict(self.sell_accumulator[-1].slice)))
            for price, count in order_book['buy']:
                if price > self.min_value:
                    self.buy_accumulator[-1].slice[price] = self.buy_accumulator[-1].slice.get(price, 0) + count
            for price, count in order_book['sell']:
                if price < self.max_value:
                    self.sell_accumulator[-1].slice[price] = self.sell_accumulator[-1].slice.get(price, 0) + count

    def enough_data(self):
        """
        Required data for the last {self.min_duration} seconds
        The period between records should be no more than {self.max_permitted_delay} seconds
        Average records period < {self.max_average_delay} seconds
        """
        start = (datetime.utcnow() - timedelta(seconds=self.min_duration + self.max_average_delay)).timestamp()
        start_index = bisect_left(self.buy_accumulator, Slice(start, None))
        if start_index == len(self.buy_accumulator):
            return False
        last_stamp = self.buy_accumulator[start_index].timestamp
        accumulative_delay = max_delay = last_stamp - start
        for stamp, _ in self.buy_accumulator[start_index + 1:]:
            accumulative_delay += stamp - last_stamp
            max_delay = max(max_delay, stamp - last_stamp)
            last_stamp = stamp
        average_delay = accumulative_delay / (len(self.buy_accumulator) - start_index)
        print(f'Duration: {int(accumulative_delay)} {"OK" if accumulative_delay > self.min_duration else "FAIL"}\n'
              f'AvgDelay: {int(average_delay * 100) / 100} {"OK" if average_delay < self.max_average_delay else "FAIL"}\n'
              f'MaxDelay: {int(max_delay)} {"OK" if max_delay < self.max_permitted_delay else "FAIL"}\n')
        return max_delay < self.max_permitted_delay and \
               average_delay < self.max_average_delay and \
               accumulative_delay > self.min_duration

    def fill(self, histograms_cursor):
        prev_book = None
        for order_book in histograms_cursor:
            if not prev_book or prev_book['timestamp'] < order_book['timestamp']:
                self.add_histogram(order_book)
            prev_book = order_book

    def get_smoothed_order_book(self, buy_or_sell: bool, duration, offset=0, divide=True):
        target = self.buy_accumulator if buy_or_sell else self.sell_accumulator
        now = int(datetime.utcnow().timestamp())
        start, finish = now - offset - duration, now - offset
        left_index = max(0, bisect_left(target, Slice(start, None)) - 1)
        right_index = min(len(target) - 1, bisect_left(target, Slice(finish, None)))
        if left_index + 1 == len(target) and left_index == right_index:
            left_index = len(target) - 2
        left_stamp, left_order = target[left_index]
        right_stamp, right_order = target[right_index]
        result = defaultdict(lambda: 0, right_order)  # TODO __sub__
        divider = right_index - left_index if right_index != left_index and divide else 1
        for price, count in left_order.items():
            result[price] -= count
        for price in result.keys():
            result[price] /= divider
        return right_index - left_index, result

    def get_cutted_price(self, is_buy: bool, threshold, duration: int, offset=0):
        """
        Return smoothed price for buy_accumulator or sell_accumulator with choosen duration, offset and threshold
        :param is_buy: in True case use buy_accumulator, otherwise sell_accumulator
        :param duration: smoothing period, higher value gives deeper smoothing
        :param offset: how many last seconds we should ignore
        :param threshold: max items count which we identify as noise
        :return: optimized possible price for selling/buying item
        """
        count, order_book = self.get_smoothed_order_book(is_buy, duration, offset, divide=True)
        sorted_keys = sorted(order_book.keys(), reverse=is_buy)
        for price in sorted_keys:
            if order_book[price] < threshold:
                threshold -= order_book[price]
            elif order_book[price]:
                return price

    def add_price_history(self, price_history):
        self.price_history = price_history

    def avg_hour_sells(self, period_hours=6):
        if self.price_history:
            time, price, count = zip(*self.price_history['history'])
            return sum(count[-period_hours:]) / period_hours

    def get_interpolation_points(self, is_buy: bool, threshold, duration: int, step):
        return [self.get_cutted_price(is_buy, threshold, step, start) for start in range(0, duration, step)][::-1]

    def get_prime_sell_price(self, duration=6 * 3600, step=30, luckiness=0.8):
        sell = self.get_interpolation_points(False, 0, duration, step)
        return round_penny(numpy.quantile(list(filter(lambda x: x is not None, sell)), q=luckiness))

    def get_prime_buy_price(self, duration=6 * 3600, step=30, luckiness=0.9):
        buy = self.get_interpolation_points(True, 0, duration, step)
        return round_penny(numpy.quantile(list(filter(lambda x: x is not None, buy)), q=1 - luckiness))

    def get_latest_price(self, buy_or_sell=True):
        target = self.buy_accumulator if buy_or_sell else self.sell_accumulator
        return (target[-1] - target[-2]).get(high_or_low=buy_or_sell)
