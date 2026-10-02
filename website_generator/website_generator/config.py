import os
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("MODEL", "gemini-3.5-flash")
