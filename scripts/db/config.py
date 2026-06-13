from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GAMES_CSV = PROJECT_ROOT / "data" / "games_sample.csv"
RESULTS_DIR = PROJECT_ROOT / "scripts" / "results"

POSTGRES_USER = os.getenv("POSTGRES_USER", "steam")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "steam")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "steam_social")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

NUM_PLAYERS = 30
MIN_GAMES_PER_PLAYER = 4
MAX_GAMES_PER_PLAYER = 12
RANDOM_SEED = 42
