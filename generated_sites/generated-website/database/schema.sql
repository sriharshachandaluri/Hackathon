-- Database Schema for Task Manager
-- FEATURE_001, FEATURE_002: Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL
);
