"""Caché con TTL y tamaño limitado (LRU) para búsquedas y operaciones costosas."""

import time
from collections import OrderedDict
from typing import TypeVar, Generic

K = TypeVar("K")
V = TypeVar("V")

class BoundedTTLCache(Generic[K, V]):
    """Una caché en memoria simple con tamaño máximo y TTL basado en acceso."""
    def __init__(self, maxsize: int, ttl: float):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: OrderedDict[K, tuple[V, float]] = OrderedDict()

    def get(self, key: K) -> V | None:
        if key not in self.cache:
            return None
        value, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        self.cache.move_to_end(key)
        return value

    def set(self, key: K, value: V) -> None:
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.maxsize:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time())
