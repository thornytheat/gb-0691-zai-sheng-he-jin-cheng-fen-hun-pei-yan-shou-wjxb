import csv
import io

from flask import Blueprint, jsonify, render_template, request, Response

from app.errors import DomainError
from app.m8ledger_export import build_ledger_csv
from app.modules.m8_ledger import service

bp = Blueprint('m8', __name__)


def _csv_text(file_field='file'):
    if request.files:
        if file_field not in request.files:
            raise DomainError('REQUEST', '上传必须使用 %s 字段' % file_field, 400)
        from app.reader import decode
        return decode(request.files[file_field].read())
    payload = request.get_json(silent=True) or {}
    text = payload.get('csv')
    if not isinstance(text, str):
        raise DomainError('REQUEST', '缺少 csv 文本', 400)
    return text


@bp.route('/api/m8/ledgers', methods=['POST'])
def create_from_receipts():
    state, reused = service.create_ledger(_csv_text('receipts'))
    return jsonify({**service.view(state['ledger_id']), 'reused': reused})


@bp.route('/api/m8/ledgers')
def list_ledgers():
    from app.modules.m8_ledger import store
    return jsonify(store.list_ledgers())


@bp.route('/api/m8/ledgers/<ledger_id>')
def ledger_detail(ledger_id):
    return jsonify(service.view(ledger_id))


@bp.route('/api/m8/ledgers/<ledger_id>/issue', methods=['POST'])
def single_issue(ledger_id):
    payload = request.get_json(silent=True) or {}
    record, replayed = service.issue_one(ledger_id, payload)
    return jsonify({'issue': record, 'replayed': replayed,
                    'ledger': service.view(ledger_id)})


@bp.route('/api/m8/ledgers/<ledger_id>/batch', methods=['POST'])
def batch_issue(ledger_id):
    summary, state = service.issue_batch(ledger_id, _csv_text('issuances'))
    return jsonify({'batch': summary, 'ledger': service.view(ledger_id)})


@bp.route('/api/m8/ledgers/<ledger_id>/ledger.csv')
def ledger_csv(ledger_id):
    data = service.view(ledger_id)
    text = build_ledger_csv(data)
    return Response('﻿' + text, mimetype='text/csv', headers={
        'Content-Disposition':
            'attachment; filename=ledger-%s.csv' % ledger_id})


@bp.route('/ledger')
@bp.route('/ledger/<ledger_id>')
def ledger_page(ledger_id=None):
    from app.config import TITLE, MODULES
    from app.modules.m8_ledger import store
    if ledger_id is None:
        state = store.latest_ledger()
        if state is None:
            state, _ = service.create_ledger(
                service.RECEIPT_SAMPLE.read_text(encoding='utf-8-sig'))
        ledger_id = state['ledger_id']
    data = service.view(ledger_id)
    return render_template(
        'ledger.html', title=TITLE, modules=MODULES, data=data,
        receipt_sample=service.RECEIPT_SAMPLE.read_text(encoding='utf-8-sig'),
        issue_sample=service.ISSUE_SAMPLE.read_text(encoding='utf-8-sig'))
