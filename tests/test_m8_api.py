import io

from app.modules.m8_ledger import service

RECEIPTS = service.RECEIPT_SAMPLE.read_text(encoding='utf-8-sig')
ISSUANCES = service.ISSUE_SAMPLE.read_text(encoding='utf-8-sig')


def _ledger(client):
    resp = client.post('/api/m8/ledgers', json={'csv': RECEIPTS})
    assert resp.status_code == 200
    return resp.get_json()


def test_ledger_page_renders_and_default_sample_available(client):
    page = client.get('/ledger')
    assert page.status_code == 200
    text = page.data.decode()
    assert '称重回执领用台账' in text and '原回执' in text
    assert '每次领用去向' in text and '当前干重余量' in text


def test_receipt_import_is_idempotent(client):
    first = _ledger(client)
    again = client.post('/api/m8/ledgers', json={'csv': RECEIPTS}).get_json()
    assert first['ledger_id'] == again['ledger_id']
    assert again['reused'] is True
    rows = client.get('/api/m8/ledgers').get_json()
    assert len(rows) == 1 and rows[0]['ledger_id'] == first['ledger_id']


def test_view_binds_receipt_assay_and_balance_together(client):
    data = _ledger(client)
    lot = next(l for l in data['lots'] if l['lot'] == 'L-1003')
    assert lot['receipt_id'] == 'RZ-20261118-03'
    assert lot['wet_mass_kg'] == '860' and lot['dry_balance_kg'].startswith('825.6')
    assert 'Cu' in lot['到货含量'] and 'Zn' in lot['到货含量']
    # 不一致批已隔离并展示
    assert any(l['status'] == '隔离' for l in data['lots'])
    assert any(q['原因码'] == 'CONFLICT' for q in data['quarantine'])


def test_single_issue_and_retry_no_double_deduction(client):
    data = _ledger(client)
    lid = data['ledger_id']
    payload = {'request_id': 'WEB-1', 'lot': 'L-1003', 'furnace': 'F-2201',
               'dry_mass': '260', 'unit': 'kg'}
    ok = client.post(f'/api/m8/ledgers/{lid}/issue', json=payload)
    assert ok.status_code == 200 and ok.get_json()['replayed'] is False
    retry = client.post(f'/api/m8/ledgers/{lid}/issue', json=payload).get_json()
    assert retry['replayed'] is True
    view = client.get(f'/api/m8/ledgers/{lid}').get_json()
    assert len(view['issues']) == 1
    lot = next(l for l in view['lots'] if l['lot'] == 'L-1003')
    assert lot['dry_balance_kg'].startswith('565.6')
    assert view['conservation']['conserved'] is True


def test_issue_quarantined_lot_rejected(client):
    lid = _ledger(client)['ledger_id']
    resp = client.post(f'/api/m8/ledgers/{lid}/issue', json={
        'request_id': 'WEB-2', 'lot': 'L-1001', 'furnace': 'F-1',
        'dry_mass': '10', 'unit': 'kg'})
    assert resp.status_code == 422
    assert resp.get_json()['code'] == 'QUARANTINED'


def test_overdraw_rejected(client):
    lid = _ledger(client)['ledger_id']
    resp = client.post(f'/api/m8/ledgers/{lid}/issue', json={
        'request_id': 'WEB-3', 'lot': 'L-1003', 'furnace': 'F-1',
        'dry_mass': '9999', 'unit': 'kg'})
    assert resp.status_code == 422
    assert resp.get_json()['code'] == 'INSUFFICIENT'


def test_batch_resume_after_interruption(client):
    lid = _ledger(client)['ledger_id']
    # 先制造 L-1004 余量不足，使批量在 REQ-A-03 中断
    client.post(f'/api/m8/ledgers/{lid}/issue', json={
        'request_id': 'PRE', 'lot': 'L-1004', 'furnace': 'F-X',
        'dry_mass': '1500', 'unit': 'kg'})
    stopped = client.post(f'/api/m8/ledgers/{lid}/batch',
                          json={'csv': ISSUANCES}).get_json()
    assert stopped['batch']['stopped_at'] == 'REQ-A-03'
    # 同一 CSV 重试：前两条跳过、第三条仍失败 → 不重复扣减
    again = client.post(f'/api/m8/ledgers/{lid}/batch',
                        json={'csv': ISSUANCES}).get_json()
    assert [r['处理'] for r in again['batch']['results'][:2]] \
        == ['已确认（跳过）', '已确认（跳过）']
    assert again['batch']['stopped_at'] == 'REQ-A-03'
    # 在库内红冲 PRE（回补余量并移除预置请求）后即可续跑
    from app.modules.m8_ledger import store
    state = store.get_ledger(lid)
    state['lots']['L-1004']['dry_balance_kg'] = '1800.0000'
    state['issues'] = [r for r in state['issues'] if r['request_id'] != 'PRE']
    store.save_ledger(lid, state)
    done = client.post(f'/api/m8/ledgers/{lid}/batch',
                       json={'csv': ISSUANCES}).get_json()
    assert done['batch']['stopped_at'] is None
    view = client.get(f'/api/m8/ledgers/{lid}').get_json()
    seq_ids = [i['request_id'] for i in view['issues'] if i['request_id'].startswith('REQ-A')]
    assert sorted(seq_ids) == sorted({f'REQ-A-0{i}' for i in range(1, 10)})
    assert view['conservation']['conserved'] is True


def test_ledger_csv_download_shows_receipts_issues_balance(client):
    lid = _ledger(client)['ledger_id']
    client.post(f'/api/m8/ledgers/{lid}/batch', json={'csv': ISSUANCES})
    text = client.get(f'/api/m8/ledgers/{lid}/ledger.csv').data.decode('utf-8-sig')
    assert '原回执' in text and '原始湿重_kg' in text
    assert '每次领用去向' in text and 'REQ-A-01' in text and 'F-2201' in text
    assert '当前余量与干重守恒' in text and '隔离记录' in text
    assert 'RZ-20261118-01' in text


def test_upload_receipts_multipart(client):
    data = {'receipts': (io.BytesIO(RECEIPTS.encode('utf-8')), 'receipts.csv')}
    resp = client.post('/api/m8/ledgers', data=data,
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    assert resp.get_json()['ledger_id']


def test_batch_upload_multipart_on_subpath(client):
    lid = _ledger(client)['ledger_id']
    data = {'issuances': (io.BytesIO(ISSUANCES.encode('utf-8')), 'issuances.csv')}
    resp = client.post(f'/api/m8/ledgers/{lid}/batch', data=data,
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    assert resp.get_json()['batch']['stopped_at'] is None


def test_wrong_upload_field_rejected(client):
    data = {'wrong': (io.BytesIO(b'a,b'), 'x.csv')}
    resp = client.post('/api/m8/ledgers', data=data,
                       content_type='multipart/form-data')
    assert resp.status_code == 400


def test_unknown_ledger_404(client):
    assert client.get('/api/m8/ledgers/NOPE').status_code == 404
    assert client.get('/api/m8/ledgers/NOPE/ledger.csv').status_code == 404
    assert client.get('/ledger/NOPE').status_code == 404


def test_non_object_json_rejected_for_ledger_routes(client):
    for value in ([], 'text', 7, None):
        resp = client.post('/api/m8/ledgers', json=value) \
            if value is not None else \
            client.post('/api/m8/ledgers', data='null',
                        content_type='application/json')
        assert resp.status_code == 400 and resp.get_json()['code'] == 'REQUEST'


def test_pipeline_routes_still_work_alongside_ledger(client):
    run = client.post('/api/run', json={}).get_json()
    assert 'manifest' in run
    for n in range(1, 8):
        assert client.get(f'/work/{n}?run_id={run["manifest"]["run_id"]}').status_code == 200
