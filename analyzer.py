import asyncio

from observer import Observer
from tasks.short_trade_task.short_trade_task import ShortTradeTask
from utils.db_wrapper import MongoWrapper

from tasks.task import Task
from tasks.collector_task import CollectorTask
from tasks.filter_task import FilterTask


class Analyzer:

    def __init__(self, controller_queue: asyncio.Queue):
        self.controller_queue = controller_queue
        self.observe_queue = asyncio.Queue()
        self.db_wrapper = MongoWrapper()
        self.observer = Observer(self.observe_queue, self.db_wrapper)
        self.running = False
        self._is_stopped = True
        self.tasks = dict()

    async def run(self):
        observer_task = asyncio.create_task(self.observer.run())
        self.running = True
        self._is_stopped = False
        while self.running:
            while not self.observe_queue.empty():
                event = await self.observe_queue.get()
                if event.owner in self.tasks:
                    await self.tasks[event.owner].put_event(event)
                else:
                    print('Monitor doesnt have owner Task, monitor will be deleted')
                    self.observer.stop_monitor(event.url)
            await asyncio.sleep(0.001)

        await self.observer.stop()
        await observer_task
        self._is_stopped = True

    async def stop(self):
        self.running = False
        while not self._is_stopped:
            await asyncio.sleep(0.1)

    async def add_task(self, task: Task):
        _id = len(self.tasks)
        self.tasks[_id] = task
        asyncio.create_task(task.run(_id))

    async def collector_task(self):
        await self.add_task(CollectorTask(self.observer, self.db_wrapper, self.controller_queue))

    async def filter_task(self):
        filter_task = FilterTask(self.observer, self.db_wrapper, self.controller_queue)
        filter_task.init_parameters(500, 1, 100)
        await self.add_task(filter_task)

    async def short_trade_task(self):
        # TODO In development. Now - testing.
        cands = [
            ('264710', 'Planet%204546B%20Postcard'),
            ('730', 'Five-SeveN%20%7C%20Flame%20Test%20%28Field-Tested%29'),
            ('730', 'Glove%20Case'),
            ('730', 'Sawed-Off%20%7C%20Morris%20%28Field-Tested%29'),
            ('730', 'Operation%20Breakout%20Weapon%20Case'),
            ('730', 'Negev%20%7C%20Desert-Strike%20%28Field-Tested%29'),  # +
            ('730', 'MP9%20%7C%20Black%20Sand%20%28Well-Worn%29'),  # +
            ('730', 'UMP-45%20%7C%20Labyrinth%20%28Field-Tested%29'),  # +
            ('730', 'XM1014%20%7C%20Oxide%20Blaze%20%28Minimal%20Wear%29'),  # +
            ('730', 'UMP-45%20%7C%20Mudder%20%28Field-Tested%29'),  # +
            ('730', 'XM1014%20%7C%20Blue%20Steel%20%28Minimal%20Wear%29'),  # +
            ('730', 'P2000%20%7C%20Turf%20%28Well-Worn%29'),  # +
            ('730', 'MP7%20%7C%20Mischief%20%28Battle-Scarred%29'),  # +
            ('730', 'R8%20Revolver%20%7C%20Survivalist%20%28Field-Tested%29'),  # +
            ('730', 'Sawed-Off%20%7C%20Origami%20%28Field-Tested%29'),  # +
            ('730', 'PP-Bizon%20%7C%20Night%20Ops%20%28Minimal%20Wear%29'),  # +
            ('730', 'Sawed-Off%20%7C%20Zander%20%28Field-Tested%29'),  # +
            ('730', 'M249%20%7C%20Gator%20Mesh%20%28Minimal%20Wear%29'),  # +
            ('730', 'Tec-9%20%7C%20Army%20Mesh%20%28Minimal%20Wear%29'),  # +
            ('730', 'P2000%20%7C%20Urban%20Hazard%20%28Well-Worn%29'),  # +
            ('730', 'UMP-45%20%7C%20Corporal%20%28Field-Tested%29'),  # +
            ('730', 'Nova%20%7C%20Sand%20Dune%20%28Minimal%20Wear%29'),  # + False oscillations???
            ('730', 'Five-SeveN%20%7C%20Forest%20Night%20%28Minimal%20Wear%29'),  # +
            ('730', 'MAG-7%20%7C%20Rust%20Coat%20%28Minimal%20Wear%29'),  # + False oscillations???
            ('730', 'Spectrum%20Case'),
            ('730', 'Prisma%202%20Case'),
            ('730', 'Five-SeveN%20%7C%20Flame%20Test%20%28Minimal%20Wear%29'),
            ('730', 'AK-47%20%7C%20Redline%20%28Field-Tested%29'),
            ('730', 'Prisma%20Case'),
            ('730', 'CS20%20Case')
        ]
        for cand in cands:
            short_trade_task = ShortTradeTask(self.observer, self.db_wrapper, self.controller_queue)
            await short_trade_task.init_parameters(*cand, cash=10, period=60)
            await self.add_task(short_trade_task)
            await asyncio.sleep(1)

# Testing:
async def main():
    controller_queue = asyncio.Queue()
    analyzer = Analyzer(controller_queue)
    asyncio.create_task(analyzer.run())
    # await analyzer.collector_task()
    # await asyncio.sleep(30)
    # await analyzer.filter_task()
    await asyncio.sleep(3)
    await analyzer.short_trade_task()
    print("Sleep for 15 seconds")
    await asyncio.sleep(3600 * 24)
    print("Wake up")
    await analyzer.stop()


if __name__ == "__main__":
    asyncio.run(main())
