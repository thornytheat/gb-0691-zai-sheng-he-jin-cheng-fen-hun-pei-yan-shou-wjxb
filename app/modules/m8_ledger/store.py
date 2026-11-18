"""M8 台账持久化：与 runs.sqlite3 隔离的独立表，事务内扣减保证不重复。"""
import json
import os
import sqlite3
from pathlib import Path

from app.errors import DomainError
from app.numeric import serial

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_state(
  ledger_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS ledger_issues(
  ledger_id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  seq INTEGER NOT NULL,
  lot TEXT NOT NULL,
  furnace TEXT NOT NULL,
  requested_kg TEXT NOT NULL,
  remaining_kg TEXT NOT NULL,
  PRIMARY KEY(ledger_id, request_id),
  UNIQUE(ledger_id, idempotency_key)
);
"""


def _db_path():
    return Path(os.environ.get('APP_DB', 'data/runs.sqlite3'))


def connection():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    return db


def list_ledgers():
    with connection() as db:
        return [dict(r) for r in db.execute(
            'SELECT ledger_id, created_at, updated_at FROM ledger_state ORDER BY rowid')]


def _load(db, ledger_id):
    row = db.execute('SELECT payload FROM ledger_state WHERE ledger_id=?',
                     (ledger_id,)).fetchone()
    if row is None:
        raise DomainError('NOT_FOUND', '台账不存在', 404)
    return json.loads(row['payload'])


def get_ledger(ledger_id):
    with connection() as db:
        return _load(db, ledger_id)


def latest_ledger():
    with connection() as db:
        row = db.execute(
            'SELECT payload FROM ledger_state ORDER BY rowid DESC LIMIT 1').fetchone()
        return json.loads(row['payload']) if row else None


def create_ledger(ledger_id, state):
    with connection() as db:
        try:
            db.execute('INSERT INTO ledger_state(ledger_id,payload) VALUES (?,?)',
                       (ledger_id, json.dumps(serial(state), ensure_ascii=False)))
        except sqlite3.IntegrityError:
            raise DomainError('CONFLICT', '台账编号已存在', 409)
    return state


def save_ledger(ledger_id, state):
    payload = json.dumps(serial(state), ensure_ascii=False)
    with connection() as db:
        changed = db.execute(
            "UPDATE ledger_state SET payload=?, "
            "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE ledger_id=?",
            (payload, ledger_id)).rowcount
        if not changed:
            raise DomainError('NOT_FOUND', '台账不存在', 404)
        db.execute('DELETE FROM ledger_issues WHERE ledger_id=?', (ledger_id,))
        db.executemany(
            'INSERT INTO ledger_issues(ledger_id,request_id,idempotency_key,seq,'
            'lot,furnace,requested_kg,remaining_kg) VALUES (?,?,?,?,?,?,?,?)',
            [(ledger_id, r['request_id'], r.get('idempotency_key', r['request_id']),
              int(r['seq']), r['lot'], r['furnace'], r['requested_kg'],
              r['remaining_kg']) for r in state.get('issues', [])])
    return state
