import sqlite3

def get_connection():
    """Connection interface for the tasks database."""
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema."""
    with get_connection() as conn:
        with open("database/schema.sql", "r") as f:
            conn.executescript(f.read())
