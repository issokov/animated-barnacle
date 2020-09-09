from datetime import datetime

from tasks.short_trade_task.market_stats import MarketStats, round_penny
from tasks.short_trade_task.trend_predictor import TrendPredictor

BUYER_TAX, SELLER_TAX = 0.869, 1.15


class BuyManager:
    overtake_period = 100

    def __init__(self, market_stats: MarketStats, trend_predictor: TrendPredictor):
        self.market_stats = market_stats
        self.trend_predictor = trend_predictor
        self.order_price = None
        self.order_count = 0
        self.order_time = 0
        self._impudence = 0

    def get_patience(self):
        avg_sells = self.market_stats.avg_hour_sells()
        avg_sells = avg_sells if avg_sells is not None else 10
        return int(avg_sells * (1 - self._impudence) * 0.1)

    def get_patience_price(self):
        return self.market_stats.get_cutted_price(True, self.get_patience(), 0)

    def set_order_completed(self):
        self.buy_closed()
        self._impudence = 0

    def buy_created(self, price: float, count: int):
        self.order_price = price
        self.order_count = count
        self.order_time = datetime.utcnow().timestamp()

    def buy_closed(self):
        self.order_price = None
        self.order_count = 0

    def should_close_order(self) -> bool:
        if self.order_price:
            market_price = self.get_patience_price()
            price_without_us = self.market_stats.get_latest_price()
            if price_without_us == self.order_price:
                price_without_us = self.market_stats.get_cutted_price(True, self.order_count, 0)
            if self.order_price < market_price or price_without_us + 0.01 < self.order_price:
                self._impudence = min(self._impudence + 0.1, 1)
                print(f'Impudence increased: {self._impudence}',
                      f'Patience: {int(self.market_stats.avg_hour_sells() * (1 - self._impudence) * 0.1)}')
                return True
        return False

    def calculate_buy_price(self):
        market_price = self.get_patience_price()
        return round_penny(market_price + 0.01)

    def get_expected_price(self):
        return min(self.market_stats.get_prime_sell_price(24 * 3600),
                   self.market_stats.get_prime_sell_price(12 * 3600),
                   self.market_stats.get_prime_sell_price(6 * 3600))

    def should_create_order(self, ) -> bool:
        if self.order_price is None:
            time_now = datetime.utcnow().timestamp()
            our_price = self.calculate_buy_price()
            if self.trend_predictor.buy_allowed() and \
                    self.order_time + self.overtake_period < time_now and \
                    round_penny(our_price * SELLER_TAX + 0.01) <= self.get_expected_price():
                return True
        return False
