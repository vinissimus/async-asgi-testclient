async def is_last_one(gen):
    prev_el = None
    async for el in gen:
        prev_el = el
        async for el in gen:
            yield (False, prev_el)
            prev_el = el
        yield (True, prev_el)
