import matplotlib.pyplot as plt
from market_data import MongoWrapper

from pprint import pprint


class Analyzer:
    def __init__(self):
        self.db_wrapper = MongoWrapper()

    def rude_filter(self):
        cursor = self.db_wrapper.get_registered(5000, 1, 40000)
        data = list(cursor)
        for item in data:
            prices = self.db_wrapper.get_price_history(item['app_id'], item['market_hash_name'])
            print(prices)

    def show_stats(self, url: str, duration: int):
        x, y_buy, y_sell = [], [], []
        histograms = self.db_wrapper.get_histograms(url, duration)
        if histograms:
            start = histograms[0]['timestamp']
            for histogram in histograms:
                x.append(histogram['timestamp'] - start)
                y_buy.append(histogram['buy'][0][0])
                y_sell.append(histogram['sell'][0][0])
            dpi = 100
            plt.figure(figsize=(min(300, 10 * len(histograms) // dpi), 10), dpi=dpi)
            plt.plot(x, y_buy)
            plt.plot(x, y_sell)
            plt.show()


