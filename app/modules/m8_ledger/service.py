"""M8 应用服务：编排领域规则、持久化与对外视图。"""
import hashlib
import time
from pathlib import Path

from app.config import RULE_VERSION
from app.errors import DomainError
from app.modules.m8_ledger import rules, store

from app.modules.m8_ledger.rules import new_state  # noqa: F401

RECEIPT_SAMPLE = Path(__file__).resolve().parents[3] / 'sample_data' / 'receipts.csv'
ISSUE_SAMPLE = Path(__file__).resolve().parents[3] / 'sample_data' / 'issuances.csv'


def ledger_id_for(receipt_csv):
    digest = hashlib.sha256(receipt_csv.encode('utf-8')).hexdigest()[:12]
    return 'LG-' + hashlib.sha256(
        (RULE_VERSION + ':ledger:' + digest).encode('utf-8')).hexdigest()[:12]


def create_ledger(receipt_csv):
    """按称重回执建账。同内容重提交复用既有台账（幂等）。"""
    if not isinstance(receipt_csv, str):
        raise DomainError('TYPE', '回执 CSV 必须是文本')
    ledger_id = ledger_id_for(receipt_csv)
    try:
        existing = store.get_ledger(ledger_id)
        return existing, True
    except DomainError as exc:
        if exc.code != 'NOT_FOUND':
            raise
    state = new_state()
    state['ledger_id'] = ledger_id
    state['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    state['rule_version'] = RULE_VERSION
    state['receipt_sha256'] = hashlib.sha256(
        receipt_csv.encode('utf-8')).hexdigest()
    state, accepted, quarantined = rules.import_receipts(receipt_csv, state)
    state['receipt_rows_accepted'] = accepted
    state['receipt_rows_quarantined'] = quarantined
    store.create_ledger(ledger_id, state)
    return state, False


def view(ledger_id):
    state = store.get_ledger(ledger_id)
    return {
        'ledger_id': state['ledger_id'],
        'created_at': state['created_at'],
        'rule_version': state['rule_version'],
        'receipt_sha256': state['receipt_sha256'],
        'lots': rules.balances(state),
        'issues': rules.issues(state),
        'quarantine': state['quarantine'],
        'import_events': state['import_events'],
        'conservation': rules.conservation(state),
        'receipt_rows_accepted': state.get('receipt_rows_accepted', 0),
        'receipt_rows_quarantined': state.get('receipt_rows_quarantined', 0),
    }


def issue_one(ledger_id, payload):
    state = store.get_ledger(ledger_id)
    record, replayed = rules.request_issue(
        state, request_id=payload.get('request_id', ''),
        lot=payload.get('lot', ''), furnace=payload.get('furnace', ''),
        dry_mass=payload.get('dry_mass', ''), unit=payload.get('unit', 'kg'),
        idempotency_key=payload.get('idempotency_key'))
    if not replayed:
        store.save_ledger(ledger_id, state)
    return record, replayed


def issue_batch(ledger_id, csv_text):
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise DomainError('EMPTY', '领用 CSV 为空')
    state = store.get_ledger(ledger_id)
    summary = rules.run_batch(state, csv_text)
    store.save_ledger(ledger_id, state)
    return summary, state
