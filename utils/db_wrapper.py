from abc import ABC, abstractmethod
from pymongo import MongoClient, ASCENDING
from datetime import datetime, timedelta


class DBWrapper(ABC):

    @abstractmethod
    async def register_item(self, item: dict):
        pass

    @abstractmethod
    async def get_registered(self, min_count: int, min_price: float, max_price: float):
        pass

    @abstractmethod
    async def add_description(self, description: dict):
        pass

    @abstractmethod
    async def get_description(self, item_url: str) -> dict:
        pass

    @abstractmethod
    async def update_histogram(self, item_nameid: str, histogram: dict):
        pass

    @abstractmethod
    async def get_histograms(self, item_url: str, period: int) -> list:
        pass

    @abstractmethod
    async def get_price_history(self, app_id: str, market_hash_name: str) -> dict:
        pass

    @abstractmethod
    async def update_price_history(self, app_id: str, market_hash_name: str, price_history: dict):
        pass


class MongoWrapper(DBWrapper):
    def __init__(self):
        self.client = MongoClient()
        self.db = None
        if 'TradeBot' not in self.client.list_database_names():
            # TODO: log that DB not found
            print('WARNING: DB not found we will create new one.')
        else:
            print('DB was found. All ok')
        self.db = self.client.get_database('TradeBot')

    async def register_item(self, item):
        self.db['items_list'].replace_one({'market_hash_name': item['market_hash_name'], 'app_id': item['app_id']},
                                          item, upsert=True)

    async def get_registered(self, min_count: int, min_price: float, max_price: float):
        return self.db['items_list'].find(
            {'count': {"$gte": min_count},
             'price': {"$gte": min_price, "$lte": max_price}})

    async def add_description(self, description: dict):
        self.db['descriptions'].replace_one({'url': description['url']}, description, upsert=True)
        print(f'Description was added {description["url"]}')

    async def get_description(self, item_url: str) -> dict:
        return self.db['descriptions'].find_one({'url': item_url})

    async def update_price_history(self, app_id: str, market_hash_name: str, price_history: dict):
        # TODO make it smarter
        self.db[f'app{app_id}'].replace_one({'market_hash_name': market_hash_name}, price_history, upsert=True)

    async def get_price_history(self, app_id, market_hash_name):
        return self.db[f'app{app_id}'].find_one({'market_hash_name': market_hash_name})

    async def update_histogram(self, item_nameid: str, histogram: dict):
        self.db[f'item{item_nameid}'].replace_one({'timestamp': histogram['timestamp']}, histogram, upsert=True)

    async def get_histograms(self, item_url: str, period: int) -> list:
        description = self.get_description(item_url)
        start_time = int((datetime.utcnow() - timedelta(seconds=period)).timestamp())
        cursor = self.db[f'item{description["item_nameid"]}'] \
            .find({'timestamp': {'$gte': start_time}}).sort([('timestamp', ASCENDING)])
        return [histo for histo in cursor]
