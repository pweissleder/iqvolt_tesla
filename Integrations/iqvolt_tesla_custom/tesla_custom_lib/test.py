import asyncio
import logging
import unittest

import httpx

from .controller import *

import tracemalloc

# Enable tracemalloc
# Your code here

# Optionally, you can also print the current memory usage statistics

async def test_something():
    try:
        controller = Controller(httpx.AsyncClient(timeout=60, verify=False), "11112d24-db81-3548-b761-835a473ccb24")
        await controller.connect()
        controller.cars = await controller.generate_car_objects()
        await controller.get_vehicle_data("LRW3E7FS2PC657243")
        await controller.cars.get("LRW3E7FS2PC657243").stop_charge()
        print(await controller.update(car_id="929646475671510",force=True, vins=set("LRW3E7FS2PC657243")))
        await controller.cars.get("LRW3E7FS2PC657243").start_charge()
        print(await controller.update(car_id="929646475671510", force=True, vins=set("LRW3E7FS2PC657243")))
        print(await controller.get_vehicle_data("LRW3E7FS2PC657243"))

    except Exception as e:
        print(e)


if __name__ == '__main__':
    tracemalloc.start()
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(test_something())


