import asyncio
import pickle

from pprint import pprint
import matplotlib.pyplot as mpl
from utils.db_wrapper import MongoWrapper

async def main():
    db = MongoWrapper()
    histograms = await db.get_histograms('730', 'CS20%20Case', 3600*72)
    time, buy_0, buy_1, buy_2, buy_3, sell_0, sell_1, sell_2 = [], [], [], [], [], [], [], []
    for item in histograms:
        time.append(item['timestamp'])
        buy_0.append(item['buy'][0][0])
        buy_1.append(item['buy'][1][0])
        buy_2.append(item['buy'][2][0])
        buy_3.append(item['buy'][3][0])
        sell_0.append(item['sell'][0][0])
        sell_1.append(item['sell'][1][0])
        sell_2.append(item['sell'][2][0])

    #mpl.plot(time, buy_0, color='#992599', marker='*', linewidth=0)
    mpl.plot(time, buy_1, color='#042f66', marker='*', linewidth=0)
    #mpl.plot(time, buy_2, color='#042f46', marker='*', linewidth=0)
    #mpl.plot(time, buy_3, color='#022f36', marker='*', linewidth=0)
    #mpl.plot(time, sell_0, color='r', marker='*', linewidth=0)
    mpl.plot(time, sell_1, color='orange', marker='*', linewidth=0)
    #mpl.plot(time, sell_2, color='yellow', marker='*', linewidth=0)
    mpl.show()


if __name__ == "__main__":
    asyncio.run(main())
