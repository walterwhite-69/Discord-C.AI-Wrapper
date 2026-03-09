import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in your .env file!")
