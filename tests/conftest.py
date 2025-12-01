import os
import sys
import types

# --- Ensure backend root is on sys.path so "app" imports work ---
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))  # go up from tests/ to backend root
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ===================== SQLALCHEMY STUBS ======================

# Main sqlalchemy module
sqlalchemy = types.ModuleType("sqlalchemy")

class Column:
    def __init__(self, *args, **kwargs):
        pass


class String:
    def __init__(self, *args, **kwargs):
        pass


class Boolean:
    def __init__(self, *args, **kwargs):
        pass


class DateTime:
    def __init__(self, *args, **kwargs):
        pass


class Date:
    def __init__(self, *args, **kwargs):
        pass


class Text:
    def __init__(self, *args, **kwargs):
        pass


class ForeignKey:
    def __init__(self, *args, **kwargs):
        pass


class Enum:
    def __init__(self, *args, **kwargs):
        pass


class ARRAY:
    def __init__(self, *args, **kwargs):
        pass


class Integer:
    def __init__(self, *args, **kwargs):
        pass


def text(*args, **kwargs):
    return None


def declarative_base():
    class Base:
        metadata = types.SimpleNamespace(create_all=lambda *a, **k: None)

    return Base


# Attach to sqlalchemy module
sqlalchemy.Column = Column
sqlalchemy.String = String
sqlalchemy.Boolean = Boolean
sqlalchemy.DateTime = DateTime
sqlalchemy.Date = Date
sqlalchemy.Text = Text
sqlalchemy.ForeignKey = ForeignKey
sqlalchemy.Enum = Enum
sqlalchemy.ARRAY = ARRAY
sqlalchemy.Integer = Integer
sqlalchemy.text = text
sqlalchemy.declarative_base = declarative_base

# Register main sqlalchemy module
sys.modules["sqlalchemy"] = sqlalchemy

# sqlalchemy.dialects.postgresql stub
dialects = types.ModuleType("sqlalchemy.dialects")
postgresql = types.ModuleType("sqlalchemy.dialects.postgresql")

class UUID:
    def __init__(self, *args, **kwargs):
        pass

postgresql.UUID = UUID
postgresql.ARRAY = ARRAY  # reuse the same ARRAY class

sys.modules["sqlalchemy.dialects"] = dialects
sys.modules["sqlalchemy.dialects.postgresql"] = postgresql

# sqlalchemy.orm stub
orm = types.ModuleType("sqlalchemy.orm")

def relationship(*args, **kwargs):
    return None

orm.relationship = relationship
orm.declarative_base = declarative_base

sys.modules["sqlalchemy.orm"] = orm

# sqlalchemy.ext.asyncio stub (in case something imports it)
ext = types.ModuleType("sqlalchemy.ext")
ext_asyncio = types.ModuleType("sqlalchemy.ext.asyncio")

class AsyncSession:
    pass

def create_async_engine(*args, **kwargs):
    return object()

def async_sessionmaker(*args, **kwargs):
    class Maker:
        def __call__(self, *a, **k):
            return None
    return Maker()

ext_asyncio.AsyncSession = AsyncSession
ext_asyncio.create_async_engine = create_async_engine
ext_asyncio.async_sessionmaker = async_sessionmaker

sys.modules["sqlalchemy.ext"] = ext
sys.modules["sqlalchemy.ext.asyncio"] = ext_asyncio

# ===================== OTHER STUBS ======================

# pydantic_settings.BaseSettings stub (if app.core.config uses it)
ps_mod = types.ModuleType("pydantic_settings")

class BaseSettings:
    def __init__(self, *args, **kwargs):
        pass

ps_mod.BaseSettings = BaseSettings
sys.modules["pydantic_settings"] = ps_mod

# Fake app.core.config.settings so imports succeed
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
    openai_api_key = "test-key"

app_core_config.settings = FakeSettings()
sys.modules["app.core.config"] = app_core_config

# Minimal app.db.database module so app.db.models can import Base
app_db_database = types.ModuleType("app.db.database")
app_db_database.Base = declarative_base()
sys.modules["app.db.database"] = app_db_database