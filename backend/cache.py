"""Bounded, in-memory TTL cache with shared in-flight requests and copy isolation."""
import asyncio
import copy
import threading
import time
from collections import OrderedDict


class AsyncTTLCache:
    def __init__(self, ttl_seconds=900, max_entries=128, clock=time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self.entries = OrderedDict()
        self.pending = {}
        self.lock = threading.RLock()

    def clear(self):
        with self.lock:
            self.entries.clear()

    async def get_or_load(self, key, loader):
        loop = asyncio.get_running_loop()
        pending_key = (loop, key)
        with self.lock:
            cached = self.entries.get(key)
            now = self.clock()
            if cached and now - cached[0] < self.ttl_seconds:
                self.entries.move_to_end(key)
                return copy.deepcopy(cached[1]), {'status':'hit', 'age_seconds':round(now-cached[0], 3), 'ttl_seconds':self.ttl_seconds}
            self.entries.pop(key, None)
            task = self.pending.get(pending_key)
            shared = task is not None
            if task is None:
                async def populate():
                    try:
                        value = await loader()
                        with self.lock:
                            # Empty results and failures never prevent an immediate retry.
                            if value:
                                stored_at = self.clock()
                                for old in [k for k,(at,_) in self.entries.items() if stored_at-at >= self.ttl_seconds]:
                                    self.entries.pop(old, None)
                                self.entries[key] = (stored_at, copy.deepcopy(value))
                                self.entries.move_to_end(key)
                                while len(self.entries) > self.max_entries:
                                    self.entries.popitem(last=False)
                        return value
                    finally:
                        with self.lock:
                            self.pending.pop(pending_key, None)
                task = loop.create_task(populate())
                # A disconnected caller may leave the shared provider request running.
                task.add_done_callback(lambda finished: finished.exception() if not finished.cancelled() else None)
                self.pending[pending_key] = task
        value = await asyncio.shield(task)
        return copy.deepcopy(value), {'status':'shared' if shared else 'miss', 'age_seconds':0, 'ttl_seconds':self.ttl_seconds}
