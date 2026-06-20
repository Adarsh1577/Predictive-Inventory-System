import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(".env"))
except ImportError:
    pass

MODEL_FILENAME = os.getenv("MODEL_FILENAME", "inventory_forecast_models.pkl")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "inventory_system")


def mysql_connect():
    import mysql.connector

    if not DB_PASSWORD:
        raise ValueError(
            "DB_PASSWORD is not set. Create a .env file or set the environment variables."
        )

    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
