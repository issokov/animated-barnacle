import asyncio
from abc import ABC, abstractmethod

from utils.steam_session import ABCSteamSession, SteamSession


class MarketInteractor:
    def __init__(self, session: ABCSteamSession):
        self.user = session
        self.buy_orders = dict()

    async def create_buy_order(self, app_id: str, market_hash_name: str, item_penny_price: float, count: int) -> str:
        url = 'https://steamcommunity.com/market/createbuyorder/'
        data = {
            "sessionid": await self.user.get_session_id(),
            "currency": self.user.get_account_preferences()['currency'],
            "appid": app_id, "market_hash_name": market_hash_name,
            "price_total": item_penny_price * count,
            "quantity": count,
            "billing_state": "",
            "save_my_address": 0
        }
        referer = f"https://steamcommunity.com/market/listings/{app_id}/{market_hash_name}"
        response = await self.user.post(url, data, referer)
        if response.status == 200:
            json = await response.json()
            if json['success'] == 1:  # TODO: handle response status
                self.buy_orders[json['buy_orderid']] = (app_id, market_hash_name, item_penny_price, count)
            return json['buy_orderid']

    async def close_buy_order(self, buy_order_id: str) -> bool:
        url = "https://steamcommunity.com/market/cancelbuyorder/"
        data = {
            "sessionid": await self.user.get_session_id(),
            "buy_orderid": buy_order_id
        }
        response = await self.user.post(url, data, "https://steamcommunity.com/market")
        return response.status == 200 and (await response.json())['success'] == 1


class Agent(ABC):
    def __init__(self, interactor: MarketInteractor):
        self.interactor = interactor
        self.analyzer_queue = asyncio.Queue()

    def get_interaction_queue(self) -> asyncio.Queue:
        return self.analyzer_queue

    @abstractmethod
    async def update(self):
        pass

async def main():
    session = SteamSession('/home/issokov/Desktop/credentials.txt')
    await session.init_session()
    if await session.is_alive():
        interactor = MarketInteractor(session)
        buy_order = await interactor.create_buy_order('730', 'CS20 Case', 4, 1)
        if buy_order is not None:
            print(buy_order)
            await asyncio.sleep(10)
            print(await interactor.close_buy_order(buy_order))
        else:
            print('Cannot create buy order')
    else:
        print('Session is dead')
    await session.aio_destructor()

if __name__ == '__main__':
    asyncio.run(main())