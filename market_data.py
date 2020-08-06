import json
from enum import Enum
from pickle import load
from time import sleep



from abc import ABC, abstractmethod
from requests.exceptions import RequestException
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from multiprocessing import Queue
from json.decoder import JSONDecodeError
from datetime import datetime, timedelta, timezone
from urllib import parse

from pprint import pprint

def time_now():
    return int(datetime.utcnow().timestamp())


class BrokenPageSource(Exception):
    pass


class WrongCurrency(Exception):
    pass


def extract_appid_and_hashname(item_url: str):
    item_url = item_url[len('https://steamcommunity.com/market/listings/'):]
    return item_url.split('/')


def is_immediately_resoldable(page_source: str):
    return '"marketable":1' in page_source and '"market_marketable_restriction"' not in page_source


def extract_item_nameid(page_source: str):
    start = page_source.find('Market_LoadOrderSpread( ')
    if start != -1:
        start += len('Market_LoadOrderSpread( ')
        end = page_source.find(' );', start)
        if end != -1:
            return page_source[start:end]
        raise BrokenPageSource()
    return None


class MarketObserver:

    def __init__(self, stealer: WebStealer):
        if issubclass(type(stealer), WebStealer):
            self.stealer = stealer
            if not self.stealer.is_alive():
                raise RuntimeError("Stealer is not working fine")
        else:
            raise TypeError("stealer should be subclassed from WebStealer")

    def collect_items(self, app_id, start, q=''):
        template = f"https://steamcommunity.com/market/search/render/?query={q}&start={start}&count=100&" \
                   f"search_descriptions=0&sort_column=popular&sort_dir=desc&appid={app_id}&norender=1"
        return self.compose_and_send(template, q=q, app_id=app_id, start=start)

    def get_description(self, item_url: str) -> dict:
        """
        Returns required for processing item data dict:
            app_id - game id
            market_hash_name - common encoded item name
            is_short_tradable - can you sell it immediately after purchase
            item_nameid - unique id for histogram request. None - when it doesn't have histogram
            url - item url on trade market
        :param item_url:
        :return:
        """
        page_source = self.stealer.get_page(item_url)
        try:
            app_id, hash_name = extract_appid_and_hashname(item_url)
            return {
                "app_id": app_id,
                "market_hash_name": hash_name,
                "is_short_tradable": is_immediately_resoldable(page_source),
                'item_nameid': extract_item_nameid(page_source),
                'url': item_url
            }
            preferences = self.stealer.get_account_preferences()
        # TODO: log it
        except BrokenPageSource:
            print(f"WARNING: There is broken page: {item_url}")

    def compose_and_send(self, template, **kwargs):
        try:
            url = template.format(**kwargs, **preferences)
            data = self.stealer.get_page(url)
            return json.loads(data)
        except (JSONDecodeError, TypeError):
            # TODO make log
            print(f"WARNING: Unable to decode answer on {template}. Maybe page is broken")

    def get_histogram(self, item_nameid: str) -> dict:
        """
        Returns prices histogram for item
        """
        template = "https://steamcommunity.com/market/itemordershistogram" \
                   "?country={country}" \
                   "&language={language}" \
                   "&currency={currency}" \
                   "&item_nameid={item_nameid}" \
                   "&two_factor={two_factor}" \
                   "&norender={norender}"
        return self.compose_and_send(template, item_nameid=item_nameid)

    def get_price_history(self, app_id: str, market_hash_name: str):
        """
        Returns price history
        :return:
        """
        template = "https://steamcommunity.com/market/pricehistory/" \
                   "?currency={currency}" \
                   "&appid={app_id}" \
                   "&market_hash_name={market_hash_name}"
        return self.compose_and_send(template, app_id=app_id, market_hash_name=market_hash_name)


def reformat_price_history(raw, market_hash_name: str) -> dict:
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
        normalized_datetime = datetime.strptime(record[0], "%b %d %Y %H: +0").astimezone(tz=timezone.utc)
        history.append([int(normalized_datetime.timestamp()), record[1], int(record[2])])
    return {'market_hash_name': market_hash_name, 'history': history}


def reformat_histogram(raw) -> dict:
    return {
        'timestamp': time_now(),
        'sell_count': int(raw['sell_order_count'].replace(',', '')),
        'buy_count': int(raw['buy_order_count'].replace(',', '')),
        'sell': list(map(lambda x: x[:2], raw['sell_order_graph'])),
        'buy': list(map(lambda x: x[:2], raw['buy_order_graph']))
    }


class TaskType(Enum):
    PRICE_HISTORY = 0
    HISTOGRAM = 1
    SCREENING = 2


class Task:
    def __init__(self, task_type: TaskType, url: str, delay=None, start=None):
        self.url = url
        self.task_type = task_type
        self.delay = delay
        self.start = time_now() if start is None else start


class MarketData:
    def __init__(self, queue: Queue, observer: MarketObserver, db_wrapper: DBWrapper):
        self.running = False
        self.sleep_duration = 0.01
        self.task_list = []
        self.queue = queue
        self.observer = observer
        if issubclass(type(db_wrapper), DBWrapper):
            self.db_wrapper = db_wrapper
        else:
            raise TypeError(f"db_wrapper({type(db_wrapper)}) should be subclassed from DBWrapper")

    def get_description(self, item_url):
        description = self.db_wrapper.get_description(item_url)
        if description is None:
            description = self.observer.get_description(item_url)
            self.db_wrapper.add_description(description)
        return description

    def collect_items(self, app_id, how_much=500):
        for page in range(0, how_much, 100):
            print(page)
            data = self.observer.collect_items(app_id=app_id, start=page)
            if data['success'] != 1:
                # TODO: log it Wrong API
                print('Cannot collect items: wrong API')
            if not data['results']:
                if page != how_much:
                    print(f"We could collect only ~{100 * page}~ items. There is no more")
                    break
            for item in data['results']:
                asset = item['asset_description']
                if asset['marketable'] and 'market_marketable_restriction' not in asset:
                    app_id = asset['appid']
                    name = asset['market_hash_name']
                    pure_item = {
                        "time": time_now(),
                        "app_id": app_id,
                        "market_hash_name": name,
                        "count": item["sell_listings"],
                        "price": item["sell_price"],
                        "link": f"https://steamcommunity.com/market/listings/{app_id}/{parse.quote(name)}"
                    }
                    self.db_wrapper.register_item(pure_item)

    def register_task(self, task: Task):
        if task.delay is None:
            self.execute_task(task)
        else:
            self.task_list.append(task)
        # TODO log it
        print(f'Register task: {task.url}')

    def update_task_executor(self):
        # TODO: REIMPLEMENT
        with ThreadPoolExecutor() as executor:
            feature_dict = {executor.submit(self.execute_task, task): task.url for task in self.task_list}
            try:
                for feature in as_completed(feature_dict.keys(), timeout=3):
                    task = feature.result()
                    if task and task.delay is not None:
                        task.start += task.delay
                        print(f'Task {feature_dict[feature]} completed')
            except TimeoutError:
                # TODO log it
                print(f'Timed out')
        sleep(self.sleep_duration)

    def execute_task(self, task: Task):
        if task.start < time_now():
            params = self.get_description(task.url)
            if task.task_type == TaskType.PRICE_HISTORY:
                self.update_price_history(params['app_id'], params['market_hash_name'])
            elif task.task_type == TaskType.HISTOGRAM:
                self.update_histogram(params['item_nameid'])
            else:
                assert False  # Unknown task_type
            return task
        return None

    def update_price_history(self, app_id: str, market_hash_name: str):
        raw = self.observer.get_price_history(app_id, market_hash_name)
        if raw is not None and raw['success']:
            expected_currency = self.observer.stealer.get_account_preferences()['price_suffix']
            if raw["price_suffix"].encode('utf-8') == expected_currency.encode('utf-8'):
                price_history = reformat_price_history(raw, market_hash_name)
                self.db_wrapper.update_price_history(app_id, market_hash_name, price_history)
            else:
                raise WrongCurrency(
                    f"Wrong currency: expected '{expected_currency.encode('utf-8')}'"
                    f" got '{raw['price_suffix'].encode('utf-8')}'")
        else:
            # TODO log it
            print(f"WARNING: Price history for {app_id}/{market_hash_name} was not been updated")

    def update_histogram(self, item_nameid: str):
        raw = self.observer.get_histogram(item_nameid)
        if raw is not None and raw['success'] == 1:
            expected_currency = self.observer.stealer.get_account_preferences()['price_suffix']
            if raw["price_suffix"].encode('utf-8') == expected_currency.encode('utf-8'):
                histogram = reformat_histogram(raw)
                self.db_wrapper.update_histogram(item_nameid, histogram)
            else:
                raise WrongCurrency(
                    f"Wrong currency: expected '{expected_currency.encode('utf-8')}'"
                    f" got '{raw['price_suffix'].encode('utf-8')}'")
        else:
            # TODO log it
            print(f"WARNING: Histogram for {item_nameid} was not been updated")

    def run(self):
        self.running = True
        while self.running:
            while not self.queue.empty():
                task = self.queue.get()
                if isinstance(task, Task):
                    self.register_task(task)
                if isinstance(task, str) and task.lower() == 'exit':
                    self.running = False
                    # TODO: put all tasks in database
            self.update_task_executor()
