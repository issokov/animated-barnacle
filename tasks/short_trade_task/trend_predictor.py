from enum import unique, Enum

from tasks.short_trade_task.market_stats import MarketStats


@unique
class RateStatus(Enum):
    PLATO = 0
    FALL = 1
    FALL_STOP = 2
    BOTTOM_REBOUND = 3
    WAIT_FOR_BUY = 4
    GROWTH = 5
    GROWTH_STOP = 6
    PEAK_REBOUND = 7
    SHARP_DROP = 8
    SHARP_INCREASE = 9


class TrendPredictor:
    def __init__(self, market_stats: MarketStats):
        self.market_stats = market_stats

    def buy_allowed(self) -> bool:
        # TODO: implement
        return True
