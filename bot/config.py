import os
import json
from dataclasses import dataclass, field


@dataclass
class Config:
    bot_token: str
    admin_ids: list[int] = field(default_factory=list)
    database_url: str = "sqlite+aiosqlite:///database.sqlite3"
    skip_updates: bool = True


def load_config() -> Config:
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.isfile(dotenv_path):
        with open(dotenv_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    raw = os.getenv("ADMIN_IDS", "[]").strip()
    if raw.startswith("["):
        admin_ids = json.loads(raw)
    else:
        admin_ids = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        admin_ids=admin_ids,
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///database.sqlite3"),
        skip_updates=os.getenv("SKIP_UPDATES", "True").lower() == "true",
    )
