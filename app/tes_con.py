from sqlalchemy import create_engine  # type: ignore

from dotenv import load_dotenv  # type: ignore
import os

load_dotenv()
db_url = os.getenv("DATABASE_URL")

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("✅ Connected to PostgreSQL")
except Exception as e:
    print("Failed to connect:", e)
