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


class Message:
    def __init__(self, event, reason, task):
        self.event: str = event
        self.reason: str = reason
        self.task: asyncio.Task = task


def create_monitored_task(coro, send):
    future = asyncio.ensure_future(coro)
    future.add_done_callback(partial(_callback, send))
    return future


async def receive(ch, timeout=None):
    fut = set_timeout(ch, timeout)
    msg = await ch.get()
    if not fut.cancelled():
        fut.cancel()
    if isinstance(msg, Message):
        if msg.event == "err":
            raise msg.reason
    return msg


def _callback(send, fut):
    try:
        fut.result()
    except asyncio.CancelledError:
        send(Message("exit", "killed", fut))
        raise
    except Exception as e:
        send(Message("err", e, fut))
    else:
        send(Message("exit", "normal", fut))


async def _send_after(timeout, queue, msg):
    if timeout is None:
        return
    await asyncio.sleep(timeout)
    await queue.put(msg)


def set_timeout(queue, timeout):
    task = asyncio.Task.current_task()
    msg = Message("err", asyncio.TimeoutError, task)
    return asyncio.ensure_future(_send_after(timeout, queue, msg))
