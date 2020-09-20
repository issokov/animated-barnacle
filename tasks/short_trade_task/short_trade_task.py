import asyncio
from enum import unique, Enum

from tasks.short_trade_task.trend_predictor import TrendPredictor
from tasks.task import Task
from observer import Observer
from utils.db_wrapper import DBWrapper
from tasks.short_trade_task.market_stats import MarketStats
from tasks.short_trade_task.buy_manager import BuyManager
from monitors.monitor import MonitorEvent, MonitorEventType, MonitorType


@unique
class ActionType(Enum):
    BUY = 0
    SELL = 1
    CLOSE_BUY = 2
    CLOSE_SELL = 3

# class ActionFabric:
#     def __init__(self, app_id: str, market_hash_name: str, ):

class Action:
    def __init__(self, action_type: ActionType, app_id: str, market_hash_name: str, price=None):
        self.type = action_type
        self.app_id = app_id
        self.market_hash_name = market_hash_name
        self.identifier = (self.app_id, self.market_hash_name)
        self.price = price
        if price is not None:
            if int(price * 100) / 100 != price or price <= 0:
                ValueError('Price should be float > 0, with two digits after point')
        elif price is not None:
            ValueError("Price should be None in Action.CloseBuy")

    @staticmethod
    def Buy(price: float, app_id: str, market_hash_name: str):
        return Action(ActionType.BUY, app_id, market_hash_name, price)

    @staticmethod
    def CloseBuy(app_id: str, market_hash_name: str):
        return Action(ActionType.CLOSE_BUY, app_id, market_hash_name, 0)

    @staticmethod
    def CreateSell():
        pass

    @staticmethod
    def CloseSell():
        pass


class ShortTradeTask(Task):
    period = 60
    cash = 0

    def __init__(self, observer: Observer, db_wrapper: DBWrapper, output_queue: asyncio.Queue):
        super().__init__(observer, db_wrapper, output_queue)
        self._running = False
        self.task_id = None
        self.item_identifier = None
        self.market_stats = MarketStats()
        self.trend_predictor = TrendPredictor(self.market_stats)
        self.buy_manager = BuyManager(self.market_stats, self.trend_predictor)

    async def init_parameters(self, app_id: str, market_hash_name: str, cash: float, **kwargs):
        self.cash = cash
        self.item_identifier = (app_id, market_hash_name)
        self.period = kwargs.get('period', self.period)
        #self.market_stats.fill(await self.db_wrapper.get_histograms(*self.item_identifier, 3600 * 24))
        print('Filled')

    async def run(self, task_id: int):
        self._running = True
        assert self.item_identifier
        await self.observer.update_histogram(task_id, *self.item_identifier, period=self.period)
        await self.observer.update_price_history(task_id, *self.item_identifier, period=3600)
        print('Updater started')

    async def update_model(self, histogram: dict):
        self.market_stats.add_histogram(histogram)
        if self.buy_manager.should_close_order():
            print(self.item_identifier[1])
            print('Close buy')
            await self.output_queue.put(Action.CloseBuy(*self.item_identifier))
            self.buy_manager.buy_closed()
        if self.buy_manager.should_create_order():
            price = self.buy_manager.calculate_buy_price()
            count = self.cash // price
            print(self.item_identifier[1])
            print(f'Create buy: {count} items at {price} RUB')
            await self.output_queue.put(Action.Buy(price, count, *self.item_identifier))

    async def put_event(self, monitor_event: MonitorEvent):
        if monitor_event.type is MonitorEventType.SUCCESS:
            if monitor_event.monitor_type is MonitorType.HISTOGRAM:
                histogram = list((await self.db_wrapper.get_histograms(*self.item_identifier, self.period + 10)))[-1]
                # await self.update_model(histogram)
            elif monitor_event.monitor_type is MonitorType.PRICEHISTORY:
                self.market_stats.add_price_history(await self.db_wrapper.get_price_history(*self.item_identifier))
            elif monitor_event.monitor_type is MonitorType.INVENTORY:
                pass
            else:
                print('nop', monitor_event.monitor_type)
        else:
            print(monitor_event)
