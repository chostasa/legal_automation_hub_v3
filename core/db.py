import sqlite3
import json
import os
from datetime import datetime
from core.error_handling import handle_error

DB_PATH = os.path.join("data", "legal_automation_hub.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    """
    Get a SQLite3 connection with row factory set to dict-like access.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        handle_error(e, code="DB_CONN_001", raise_it=True)


def init_db():
    """
    Create all required tables if they do not exist.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Templates table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            tags TEXT,
            category TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            deleted INTEGER DEFAULT 0
        )
        """)

        # Examples table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            category TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            deleted INTEGER DEFAULT 0
        )
        """)

        # Audit log table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id TEXT,
            action TEXT NOT NULL,
            metadata TEXT,
            timestamp TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    except Exception as e:
        handle_error(e, code="DB_INIT_001", raise_it=True)


def insert_template(tenant_id: str, name: str, path: str, category: str, tags: list = None):
    """
    Insert a new template record.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO templates (tenant_id, name, path, category, tags, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            name,
            path,
            category,
            json.dumps(tags or []),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_INSERT_001", raise_it=True)


def get_templates(tenant_id: str, category: str = None, include_deleted: bool = False):
    """
    Retrieve templates for a tenant (optionally filter by category).
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = "SELECT * FROM templates WHERE tenant_id = ?"
        params = [tenant_id]

        if category:
            query += " AND category = ?"
            params.append(category)
        if not include_deleted:
            query += " AND deleted = 0"

        cur.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows

    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_GET_001", raise_it=True)


def soft_delete_template(template_id: int, tenant_id: str):
    """
    Mark a template as deleted (soft delete).
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE templates SET deleted = 1 WHERE id = ? AND tenant_id = ?
        """, (template_id, tenant_id))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_DELETE_001", raise_it=True)


def insert_audit_event(tenant_id: str, user_id: str, action: str, metadata: dict = None):
    """
    Insert a new audit event.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO audit_log (tenant_id, user_id, action, metadata, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (
            tenant_id,
            user_id,
            action,
            json.dumps(metadata or {}),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_AUDIT_INSERT_001", raise_it=True)

def update_template_name(template_id: int, tenant_id: str, new_name: str, new_path: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE templates SET name = ?, path = ? WHERE id = ? AND tenant_id = ?
    """, (new_name, new_path, template_id, tenant_id))
    conn.commit()
    conn.close()

def get_audit_events(tenant_id: str, user_id: str = None, action: str = None, limit: int = 50):
    """
    Retrieve audit events for a tenant with optional filters.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = "SELECT * FROM audit_log WHERE tenant_id = ?"
        params = [tenant_id]

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows

    except Exception as e:
        handle_error(e, code="DB_AUDIT_GET_001", raise_it=True)
