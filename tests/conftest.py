import sys
import os
import types

# Ensure repository root is on sys.path so 'app' package imports resolve
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Build a single sqlalchemy module object with the symbols the app imports
import importlib.util

sqlalchemy_mod = types.ModuleType("sqlalchemy")
sqlalchemy_mod.__file__ = "<tests-stub>/sqlalchemy/__init__.py"
sqlalchemy_mod.__path__ = []
sqlalchemy_mod.__spec__ = importlib.util.spec_from_loader("sqlalchemy", loader=None)

def _col(*a, **k):
    return None

sqlalchemy_mod.Column = _col
sqlalchemy_mod.String = lambda *a, **k: None
sqlalchemy_mod.DateTime = object()
sqlalchemy_mod.Boolean = object()

def select(*a, **k):
    # simple placeholder used by tests; real SQL building isn't necessary
    class Q:
        def where(self, *a, **k):
            return self

    return Q()

sqlalchemy_mod.select = select
sqlalchemy_mod.__all__ = ["select", "Column", "String", "DateTime", "Boolean", "declarative_base"]

def declarative_base():
    class Base:
        metadata = types.SimpleNamespace(create_all=lambda *a, **k: None)

    return Base

sqlalchemy_mod.declarative_base = declarative_base

# Dialects package and postgresql.UUID stub
dialects_mod = types.ModuleType("sqlalchemy.dialects")
postgresql_mod = types.ModuleType("sqlalchemy.dialects.postgresql")

class UUID:
    def __init__(self, *a, **k):
        pass

postgresql_mod.UUID = UUID

# ext.asyncio stubs
ext_mod = types.ModuleType("sqlalchemy.ext")
asyncio_mod = types.ModuleType("sqlalchemy.ext.asyncio")

class AsyncSession:
    pass

def create_async_engine(*a, **k):
    return object()

def async_sessionmaker(*a, **k):
    class Maker:
        def __call__(self, *a, **k):
            return None

    return Maker()

asyncio_mod.AsyncSession = AsyncSession
asyncio_mod.create_async_engine = create_async_engine
asyncio_mod.async_sessionmaker = async_sessionmaker

# Insert into sys.modules
sys.modules["sqlalchemy"] = sqlalchemy_mod
sys.modules["sqlalchemy.dialects"] = dialects_mod
sys.modules["sqlalchemy.dialects.postgresql"] = postgresql_mod
sys.modules["sqlalchemy.ext"] = ext_mod
sys.modules["sqlalchemy.ext.asyncio"] = asyncio_mod

# orm subpackage with declarative_base
orm_mod = types.ModuleType("sqlalchemy.orm")
orm_mod.declarative_base = declarative_base
sys.modules["sqlalchemy.orm"] = orm_mod

# pydantic_settings BaseSettings stub
ps_mod = types.ModuleType("pydantic_settings")

class BaseSettings:
    def __init__(self, *a, **k):
        pass

ps_mod.BaseSettings = BaseSettings
sys.modules["pydantic_settings"] = ps_mod

# Provide a fake app.core.config module with a settings object so imports succeed
app_core_config = types.ModuleType("app.core.config")

class FakeSettings:
    base_url = "http://localhost"
    database_url = "sqlite:///:memory:"
    jwt_secret_key = "secret"
    jwt_algorithm = "HS256"
    google_client_id = "gcid"
    google_client_secret = "gsecret"
    google_redirect_uri = "http://localhost/callback"
    app_deep_link = "app://deep"

app_core_config.settings = FakeSettings()
sys.modules["app.core.config"] = app_core_config

# Provide a minimal app.db.database module so app.db.models can import Base
app_db_database = types.ModuleType("app.db.database")
app_db_database.Base = declarative_base()
sys.modules["app.db.database"] = app_db_database
import sys

# Provide small in-memory stubs for SQLAlchemy symbols the app imports so tests
# can import app modules without installing the entire dependency.
import types

# Ensure repository root is on sys.path so 'app' package imports resolve
import os
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

sqlalchemy = types.SimpleNamespace()

class Column:
    def __init__(self, *args, **kwargs):
        pass


class String:
    def __init__(self, *args, **kwargs):
        pass


class DateTime:
    pass


class Boolean:
    pass


def declarative_base():
    class Base:
        metadata = types.SimpleNamespace(create_all=lambda *a, **k: None)

    return Base


sqlalchemy.Column = Column
sqlalchemy.String = String
sqlalchemy.DateTime = DateTime
sqlalchemy.Boolean = Boolean
sqlalchemy.declarative_base = declarative_base

ext_asyncio = types.SimpleNamespace()


class AsyncSession:
    pass


def create_async_engine(*a, **k):
    return object()


def async_sessionmaker(*a, **k):
    class Maker:
        def __call__(self, *a, **k):
            return None

    return Maker()


ext_asyncio.AsyncSession = AsyncSession
ext_asyncio.create_async_engine = create_async_engine
ext_asyncio.async_sessionmaker = async_sessionmaker

# Inject into sys.modules so normal imports like 'from sqlalchemy import Column' work
sys.modules["sqlalchemy"] = sqlalchemy
sys.modules["sqlalchemy.ext"] = types.SimpleNamespace()
sys.modules["sqlalchemy.ext.asyncio"] = ext_asyncio
