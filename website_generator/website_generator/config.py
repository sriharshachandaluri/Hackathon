import os
from dotenv import load_dotenv
from google.adk.models.google_llm import Gemini
from google.genai import types

load_dotenv()

# Do not repeat quota-exhausted requests. One attempt makes the actual quota
# error visible promptly instead of spending more time on retries.
MODEL = Gemini(
    model=os.getenv("MODEL", "gemini-3.1-flash-lite"),
    retry_options=types.HttpRetryOptions(
        attempts=3,
        http_status_codes=[429, 500, 503, 504],
    ),
)

MAX_REPAIR_ITERATIONS = max(1, int(os.getenv("MAX_REPAIR_ITERATIONS", "3")))
