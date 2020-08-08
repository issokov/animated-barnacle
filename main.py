import asyncio
from observer import Observer

class DummyTask:
    pass

async def main():
    queue = asyncio.Queue()
    mongo = object()
    observer = Observer(queue)
    await observer.init()
    observer_task = asyncio.create_task(observer.run())

    first_task = DummyTask(mongo, 10)
    second_task = DummyTask(mongo, 3)
    await observer.add_task(first_task)
    await observer.add_task(second_task)
    await observer_task
    await observer.session.aio_destructor()

if __name__ == "__main__":
    asyncio.run(main())