import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

def get_db():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

# Database Initialization
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

class Task(BaseModel):
    title: str

class TaskResponse(BaseModel):
    id: int
    title: str

@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(task: Task):
    if not task.title:
        raise HTTPException(status_code=400, detail="Title must not be empty")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title) VALUES (?)", (task.title,))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": task_id, "title": task.title}

@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM tasks")
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": row["id"], "title": row["title"]} for row in rows]
