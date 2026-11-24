import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from .config import settings


def _engine_url(url: str):
    parsed = make_url(url)
    if parsed.drivername not in {'sqlite', 'sqlite+pysqlite'}:
        raise ValueError('Only SQLite DATABASE_URL is supported')
    if parsed.database and parsed.database != ':memory:':
        from pathlib import Path
        Path(parsed.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return url

engine = create_engine(_engine_url(settings.database_url), connect_args={'check_same_thread': False}, pool_pre_ping=True)


def init_db():
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL
        )'''))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_session_id_id ON messages(session_id, id)'))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, system_prompt TEXT NOT NULL, created_at TEXT NOT NULL)'''))


def add_message(session_id: str, role: str, content: str, metadata: dict | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES (:s,:r,:c,:m,:t)'), {
            's': session_id, 'r': role, 'c': content,
            'm': json.dumps(metadata, separators=(',', ':')) if metadata is not None else None,
            't': now,
        })


def get_messages(session_id: str):
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT role, content, metadata FROM messages WHERE session_id=:s ORDER BY id ASC'), {'s': session_id}).mappings().all()
    return [dict(role=row['role'], content=row['content'], **({'metadata': json.loads(row['metadata'])} if row['metadata'] else {})) for row in rows]


def session_exists(session_id: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(text('SELECT 1 FROM messages WHERE session_id=:s LIMIT 1'), {'s': session_id}).first() is not None


def get_system_prompt(session_id: str):
    with engine.connect() as conn:
        row = conn.execute(text('SELECT system_prompt FROM sessions WHERE session_id=:s'), {'s': session_id}).first()
    return row[0] if row else None


def save_system_prompt(session_id: str, prompt: str):
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO sessions(session_id, system_prompt, created_at) VALUES (:s,:p,:t) ON CONFLICT(session_id) DO UPDATE SET system_prompt=excluded.system_prompt'), {'s':session_id,'p':prompt,'t':now})
