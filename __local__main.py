from pathlib import Path
import os

from dotenv import load_dotenv
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
LOCAL_ENV_PATH = BASE_DIR / "local.env"

if LOCAL_ENV_PATH.exists():
    load_dotenv(LOCAL_ENV_PATH)
    print(f"Loaded environment variables from: {LOCAL_ENV_PATH}")
else:
    print("local.env not found. Using default environment variables.")

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_RELOAD = os.getenv("APP_RELOAD", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=APP_RELOAD,
        log_level=LOG_LEVEL,
    )