import os
from dotenv import load_dotenv

load_dotenv()


def get_database_url(async_mode: bool = False) -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "license_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "1234")
    driver = "postgresql+asyncpg" if async_mode else "postgresql+psycopg2"
    return f"{driver}://{user}:{password}@{host}:{port}/{name}"


SYNC_DATABASE_URL = get_database_url(async_mode=False)
ASYNC_DATABASE_URL = get_database_url(async_mode=True)
