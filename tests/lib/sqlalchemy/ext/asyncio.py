"""Stubs for sqlalchemy.ext.asyncio used in tests"""


class AsyncSession:
    pass


def create_async_engine(*a, **k):
    return object()


def async_sessionmaker(*a, **k):
    class Maker:
        def __init__(self):
            pass

        def __call__(self, *a, **k):
            return None

    return Maker()


__all__ = ["AsyncSession", "create_async_engine", "async_sessionmaker"]
