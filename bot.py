from market_data import MarketData, MarketObserver, MongoWrapper, SimpleStealer, Task, TaskType
from multiprocessing import Process, Queue
from time import sleep
from analyzer import Analyzer
from pprint import pprint


def _run_market_manager(queue: Queue):
    print('Preparing MarketData for processing...')
    market = MarketData(queue, MarketObserver(SimpleStealer()), MongoWrapper())
    print("Prepared. Running...")
    market.running = True
    while market.running:
        try:
            market.run()
        except Exception as e:
            print('Unknown error. Sleep 30 seconds and rebooting')
            print(e)
            sleep(30)
            market.task_list.clear()
            market.run()

    print('MarketData shutdowned')


class Bot:
    def __init__(self):
        pass

    def run(self):
        queue = Queue()
        p = Process(target=_run_market_manager, args=(queue,))
        p.start()
        analyzer = Analyzer()
        running = True
        while running:
            command = input()
            if command == 'exit':
                queue.put('exit')
                # p.join()
                running = False
            elif 'register' in command:
                url, delay = command.split(' ')[1:]
                queue.put(Task(TaskType.HISTOGRAM, url, int(delay)))
            elif 'show' in command:
                url, duration = command.split(' ')[1:3]
                analyzer.show_stats(url, int(duration))
            else:
                print(f'Unknown command {command}')


if __name__ == "__main__":
    Bot().run()
