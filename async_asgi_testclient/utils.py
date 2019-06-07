from dataclasses import dataclass
from functools import partial

import asyncio


async def is_last_one(gen):
    prev_el = None
    async for el in gen:
        prev_el = el
        async for el in gen:
            yield (False, prev_el)
            prev_el = el
        yield (True, prev_el)


@dataclass
class Message():

    event: str
    reason: str
    task: asyncio.Task


def create_monitored_task(coro, send):
    future = asyncio.create_task(coro)
    future.add_done_callback(partial(_callback, send))
    return future


async def receive(ch):
    msg = await ch.get()
    if isinstance(msg, Message):
        if msg.event == "err":
            raise msg.reason
    return msg


def _callback(ch, fut):
    try:
        fut.result()
    except asyncio.CancelledError:
        ch(Message("exit", "killed", fut))
        raise
    except Exception as e:
        ch(Message("err", e, fut))
    else:
        ch(Message("exit", "normal", fut))


async def _send_after(timeout, queue, msg):
    if timeout is None:
        return
    await asyncio.sleep(timeout)
    await queue.put(msg)


async def set_timeout(queue, timeout):
    task = asyncio.current_task()
    msg = Message("err", asyncio.TimeoutError, task)
    return asyncio.create_task(_send_after(timeout, queue, msg))
