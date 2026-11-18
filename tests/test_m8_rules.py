from decimal import Decimal

import pytest

from app.config import SAMPLE
from app.errors import DomainError
from app.modules.m8_ledger import rules, service
from app.modules.m8_ledger.service import new_state


RECEIPTS = service.RECEIPT_SAMPLE.read_text(encoding='utf-8-sig')
ISSUANCES = service.ISSUE_SAMPLE.read_text(encoding='utf-8-sig')


def _build(csv_text=RECEIPTS):
    state = new_state()
    state, accepted, quarantined = rules.import_receipts(csv_text, state)
    return state


def test_wet_weight_kept_for_settlement_dry_balance_for_production():
    state = _build()
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1001')
    # 1020kg 湿重、8% 水分 → 干重 938.4；结算湿重原样保留
    assert lot['wet_mass_kg'] == '1020'
    assert Decimal(lot['dry_total_kg']) == Decimal('938.4000')
    assert Decimal(lot['dry_balance_kg']) == Decimal('938.4000')


def test_wet_basis_assay_converted_to_dry_and_bound():
    state = _build()
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1002')
    zn = next(a for a in lot['assay'] if a['元素'] == 'Zn')
    # 湿基 4.8%、水分 6.5% → 干基 4.8/0.935 ≈ 5.1337
    assert Decimal(zn['low_pct']) == Decimal('5.1337')
    assert zn['source_basis'] == 'wet' and zn['basis'] == 'dry'


def test_tonne_and_kg_unified_and_full_width_digits():
    state = _build()
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1002')
    assert Decimal(lot['wet_mass_kg']) == Decimal('1250')


def test_conflicting_assay_quarantines_whole_lot_and_blocks_issue():
    state = _build()
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1001')
    assert lot['status'] == '隔离'
    codes = {q['原因码'] for q in state['quarantine'] if q.get('批号') == 'L-1001'}
    assert 'CONFLICT' in codes
    with pytest.raises(DomainError) as exc:
        rules.request_issue(state, request_id='X1', lot='L-1001',
                            furnace='F-9', dry_mass='10', unit='kg')
    assert exc.value.code == 'QUARANTINED'


def test_dirty_rows_quarantined_not_zeroed():
    state = _build()
    q = {(q.get('批号'), q['原因码']) for q in state['quarantine']}
    assert ('L-1010', 'MISSING') in q       # 水分缺失不能当 0
    assert ('L-1011', 'MISSING') in q       # 含量 N/A 不能当 0
    assert all(lot['lot'] not in ('L-1010', 'L-1011')
               for lot in rules.balances(state))


def test_duplicate_receipt_row_is_skipped_not_double_counted():
    state = _build()
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1001')
    # 回执湿重仍是 1020，未因重复行翻倍
    assert lot['wet_mass_kg'] == '1020'


def test_issue_deducts_dry_only_and_binds_receipt_furnace():
    state = _build()
    rec, replayed = rules.request_issue(
        state, request_id='R1', lot='L-1003', furnace='F-2201',
        dry_mass='260', unit='kg')
    assert replayed is False
    assert rec['receipt_id'] == 'RZ-20261118-03'
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1003')
    # 860 × 0.96 = 825.6 干重，扣 260 后余 565.6
    assert Decimal(lot['dry_balance_kg']) == Decimal('565.6000')
    assert Decimal(rec['remaining_kg']) == Decimal('565.6000')


def test_overdraw_rejected_without_deduction():
    state = _build()
    lot_before = next(r for r in rules.balances(state)
                      if r['lot'] == 'L-1003')['dry_balance_kg']
    with pytest.raises(DomainError) as exc:
        rules.request_issue(state, request_id='R2', lot='L-1003',
                            furnace='F-2201', dry_mass='9999', unit='kg')
    assert exc.value.code == 'INSUFFICIENT'
    lot_after = next(r for r in rules.balances(state)
                     if r['lot'] == 'L-1003')['dry_balance_kg']
    assert lot_before == lot_after


def test_retry_same_request_id_replays_without_double_deduction():
    state = _build()
    first, _ = rules.request_issue(
        state, request_id='R3', lot='L-1003', furnace='F-2201',
        dry_mass='100', unit='kg')
    again, replayed = rules.request_issue(
        state, request_id='R3', lot='L-1003', furnace='F-2201',
        dry_mass='100', unit='kg')
    assert replayed is True
    assert again == first
    assert len(state['issues']) == 1
    lot = next(r for r in rules.balances(state) if r['lot'] == 'L-1003')
    assert Decimal(lot['dry_balance_kg']) == Decimal('825.6') - Decimal('100')


def test_same_request_id_with_different_payload_refused():
    state = _build()
    rules.request_issue(state, request_id='R4', lot='L-1003',
                        furnace='F-2201', dry_mass='100', unit='kg')
    with pytest.raises(DomainError) as exc:
        rules.request_issue(state, request_id='R4', lot='L-1004',
                            furnace='F-2201', dry_mass='100', unit='kg')
    assert exc.value.code == 'IDEMPOTENT'


def test_batch_interrupts_and_resumes_from_confirmed_point():
    state = _build()
    # 让 REQ-A-03（L-1004 领 800kg）超量：先把 L-1004 余量全部领出
    rules.request_issue(state, request_id='PRE', lot='L-1004',
                        furnace='F-X', dry_mass='1800', unit='kg')
    summary = rules.run_batch(state, ISSUANCES)
    assert summary['stopped_at'] == 'REQ-A-03'
    assert len(summary['results']) == 2          # 前两条确认，第三条失败即停
    confirmed = {r['request_id'] for r in state['issues']}
    assert {'REQ-A-01', 'REQ-A-02'} <= confirmed
    # 红冲 PRE（回补 1800）并移除该预置请求，恢复成无预置的初始余量后续跑
    state['lots']['L-1004']['dry_balance_kg'] = '1800.0000'
    state['issues'] = [r for r in state['issues'] if r['request_id'] != 'PRE']
    # 同一 CSV 重放：前两条已确认 → 跳过，不重复扣减，后续依次确认
    resumed = rules.run_batch(state, ISSUANCES)
    assert resumed['stopped_at'] is None
    handles = [r['处理'] for r in resumed['results']]
    assert handles[:2] == ['已确认（跳过）', '已确认（跳过）']
    assert len({r['request_id'] for r in state['issues']
                if r['request_id'].startswith('REQ-A')}) == 9
    assert rules.conservation(state)['conserved'] is True


def test_batch_stop_record_cleared_after_successful_resume():
    state = _build()
    rules.request_issue(state, request_id='PRE', lot='L-1004',
                        furnace='F-X', dry_mass='1800', unit='kg')
    rules.run_batch(state, ISSUANCES)
    assert any(q.get('原因码') == 'BATCH_STOP' and q.get('request_id') == 'REQ-A-03'
               for q in state['quarantine'])
    state['lots']['L-1004']['dry_balance_kg'] = '1800.0000'
    state['issues'] = [r for r in state['issues'] if r['request_id'] != 'PRE']
    rules.run_batch(state, ISSUANCES)
    assert not any(q.get('request_id') == 'REQ-A-03' for q in state['quarantine'])


def test_conservation_holds_after_full_batch():
    state = _build()
    rules.run_batch(state, ISSUANCES)
    check = rules.conservation(state)
    assert check['conserved'] is True
    assert Decimal(check['issued_kg']) + Decimal(check['balance_kg']) \
        == Decimal(check['open_dry_total_kg'])


def test_unknown_lot_and_missing_furnace_are_domain_errors():
    state = _build()
    with pytest.raises(DomainError) as exc:
        rules.request_issue(state, request_id='R5', lot='NO-SUCH',
                            furnace='F-1', dry_mass='1', unit='kg')
    assert exc.value.code == 'NOT_FOUND'
    with pytest.raises(DomainError):
        rules.request_issue(state, request_id='R6', lot='L-1003',
                            furnace='', dry_mass='1', unit='kg')


def test_header_mismatch_and_bad_columns():
    state = new_state()
    with pytest.raises(DomainError) as exc:
        rules.import_receipts(
            'receipt_id,lot,batch,wet_mass,unit,moisture,element,assay,basis,extra\n'
            + ','.join(['x'] * 10) + '\n', state)
    assert exc.value.code == 'HEADER'
    state2 = new_state()
    rules.import_receipts(RECEIPTS + 'only,three,cols\n', state2)
    assert any(q['原因码'] == 'COLUMNS' for q in state2['quarantine'])
