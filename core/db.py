import sqlite3
import json
import os
import hashlib
from datetime import datetime
from core.error_handling import handle_error
from services.dropbox_client import (
    list_templates, list_examples,
    upload_file_to_dropbox, delete_file_from_dropbox, move_file_in_dropbox
)
from core.constants import DROPBOX_TEMPLATES_ROOT, DROPBOX_EXAMPLES_ROOT

DB_PATH = os.path.join("data", "legal_automation_hub.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        handle_error(e, code="DB_CONN_001", raise_it=True)


def init_db():
    """Initialize DB tables for audit logs and quotas."""
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id TEXT,
            action TEXT NOT NULL,
            metadata TEXT,
            hash TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            key TEXT NOT NULL,
            limit_value INTEGER NOT NULL,
            used_value INTEGER DEFAULT 0,
            reset_at TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    except Exception as e:
        handle_error(e, code="DB_INIT_001", raise_it=True)


# ---------------------------
# Templates (Dropbox)
# ---------------------------

def get_templates(tenant_id: str, category: str = None, include_deleted: bool = False):
    """Directly list templates from Dropbox instead of SQLite."""
    if not category:
        categories = ["email", "batch_docs", "foia", "demand"]
        templates = []
        for cat in categories:
            templates += [
                {"name": f, "path": f"{DROPBOX_TEMPLATES_ROOT}/{cat}/{f}"}
                for f in list_templates(cat)
            ]
        return templates

    return [
        {"name": f, "path": f"{DROPBOX_TEMPLATES_ROOT}/{category}/{f}"}
        for f in list_templates(category)
    ]


def insert_template(tenant_id: str, name: str, path: str, category: str, tags: list = None):
    """
    Wrapper for compatibility with template_manager_ui.
    Simply uploads to Dropbox.
    """
    try:
        # Upload directly to Dropbox
        with open(path, "rb") as f:
            file_bytes = f.read()
        upload_file_to_dropbox(f"{DROPBOX_TEMPLATES_ROOT}/{category}/{name}", file_bytes)
        return {"name": name, "path": f"{DROPBOX_TEMPLATES_ROOT}/{category}/{name}"}
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_INSERT_001", raise_it=True)


def soft_delete_template(template_id: int, tenant_id: str):
    """Delete template from Dropbox by path (template_id is unused now)."""
    try:
        # This function should be called with path instead of id now
        delete_file_from_dropbox(template_id)  # here template_id is actually the path
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_DELETE_001", raise_it=True)


def update_template_name(template_id: int, tenant_id: str, new_name: str, new_path: str):
    """Rename a template in Dropbox."""
    try:
        move_file_in_dropbox(template_id, new_path)
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_UPDATE_001", raise_it=True)


# ---------------------------
# Examples (Dropbox)
# ---------------------------

def get_examples(tenant_id: str, category: str = None):
    """Retrieve examples directly from Dropbox."""
    try:
        if not category:
            categories = ["memos", "demands", "foia"]
            examples = []
            for cat in categories:
                files = list_examples(cat)
                examples += [
                    {"name": f, "path": f"{DROPBOX_EXAMPLES_ROOT}/{cat}/{f}"}
                    for f in files
                ]
            return examples

        files = list_examples(category)
        return [{"name": f, "path": f"{DROPBOX_EXAMPLES_ROOT}/{category}/{f}"} for f in files]

    except Exception as e:
        handle_error(e, code="DB_EXAMPLES_LIST_001", raise_it=True)


# ---------------------------
# Audit Log
# ---------------------------

def insert_audit_event(tenant_id: str, user_id: str, action: str, metadata: dict = None):
    try:
        ts = datetime.utcnow().isoformat()
        metadata_str = json.dumps(metadata or {})
        record_string = f"{tenant_id}|{user_id}|{action}|{metadata_str}|{ts}"
        record_hash = hashlib.sha256(record_string.encode()).hexdigest()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO audit_log (tenant_id, user_id, action, metadata, hash, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            user_id,
            action,
            metadata_str,
            record_hash,
            ts
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_AUDIT_INSERT_001", raise_it=True)


def get_audit_events(tenant_id: str, user_id: str = None, action: str = None, limit: int = 50):
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
        rows = []
        for row in cur.fetchall():
            row_dict = dict(row)
            record_string = f"{row_dict['tenant_id']}|{row_dict.get('user_id')}|{row_dict['action']}|{row_dict.get('metadata', '{}')}|{row_dict['timestamp']}"
            expected_hash = hashlib.sha256(record_string.encode()).hexdigest()
            row_dict["tampered"] = (row_dict["hash"] != expected_hash)
            rows.append(row_dict)
        conn.close()
        return rows

    except Exception as e:
        handle_error(e, code="DB_AUDIT_GET_001", raise_it=True)


# ---------------------------
# Quotas
# ---------------------------

def get_quota(tenant_id: str, key: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM quotas WHERE tenant_id = ? AND key = ?
        """, (tenant_id, key))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        handle_error(e, code="DB_QUOTA_GET_001", raise_it=True)


def set_quota(tenant_id: str, key: str, limit_value: int, reset_at: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO quotas (tenant_id, key, limit_value, used_value, reset_at)
        VALUES (?, ?, ?, 0, ?)
        ON CONFLICT(tenant_id, key) DO UPDATE SET limit_value = excluded.limit_value, reset_at = excluded.reset_at
        """, (tenant_id, key, limit_value, reset_at))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_QUOTA_SET_001", raise_it=True)


def increment_quota_usage(tenant_id: str, key: str, amount: int = 1):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE quotas SET used_value = used_value + ? WHERE tenant_id = ? AND key = ?
        """, (amount, tenant_id, key))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_QUOTA_INCREMENT_001", raise_it=True)


# Initialize DB and ensure tables exist
init_db()
