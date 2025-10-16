"""Minimal stub of SQLAlchemy used for tests."""
from types import SimpleNamespace


class Column:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class String:
    def __init__(self, *args, **kwargs):
        pass


class DateTime:
    pass


class Boolean:
    pass


def declarative_base():
    class Base:
        metadata = SimpleNamespace(create_all=lambda *a, **k: None)

    return Base


def Column(*a, **k):
    return Column


__all__ = ["Column", "String", "DateTime", "Boolean", "declarative_base"]
