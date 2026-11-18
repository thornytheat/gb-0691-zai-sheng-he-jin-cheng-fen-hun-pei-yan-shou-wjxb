"""M8 称重回执领用台账：纯领域逻辑，不依赖 Flask 与 SQLite。

结算口径：回执原始湿重 + 到货含量（湿基换算到干基后归档）。
配料口径：脱水后的干重余量，所有领用只能扣减干重。
同一批料（lot）把原回执、每次领用去向（炉次）、当前余量绑定在一起；
回执之间不一致先隔离，隔离批不参与任何扣减。
"""
from decimal import Decimal

from app.numeric import number, fmt
from app.errors import DomainError
from app.reader import parse_table

RECEIPT_HEADERS = ['receipt_id', 'lot', 'batch', 'wet_mass', 'unit',
                   'moisture', 'element', 'assay', 'basis']
ISSUE_HEADERS = ['request_id', 'seq', 'lot', 'furnace', 'dry_mass', 'unit']
VALID_ELEMENTS = ('Cu', 'Zn')


def new_state():
    return {'receipts': {}, 'lots': {}, 'issues': [], 'quarantine': [],
            'import_events': []}


def _kg(value, unit):
    if unit not in ('kg', 't'):
        raise DomainError('UNIT', '重量单位无效（仅支持 kg/t）')
    mass = number(value) * (Decimal('1000') if unit == 't' else Decimal('1'))
    if mass <= 0:
        raise DomainError('RANGE', '重量必须大于零')
    return mass


def _assay_bounds(value):
    text = str(value).strip()
    if text.startswith('<'):
        upper = number(text[1:])
        low = Decimal('0')
    else:
        low = upper = number(text)
    if not 0 <= low <= upper <= 100:
        raise DomainError('RANGE', '元素含量超出 0–100% 范围')
    return low, upper


def import_receipts(text, state):
    """解析称重回执 CSV，按 lot 归档；冲突与脏数据进隔离区。"""
    rows, bad = parse_table(text, RECEIPT_HEADERS, state.setdefault('quarantine', []))
    receipts = state.setdefault('receipts', {})
    lots = state.setdefault('lots', {})
    events = state.setdefault('import_events', [])
    accepted = 0
    for raw in rows:
        line = raw['行号']
        try:
            rid, lot, batch = raw['receipt_id'], raw['lot'], raw['batch']
            if not rid:
                raise DomainError('MISSING', '回执编号为空')
            if not lot:
                raise DomainError('MISSING', '批号为空')
            if not batch:
                raise DomainError('MISSING', '到货炉次/批次为空')
            wet = _kg(raw['wet_mass'], raw['unit'])
            moisture = number(raw['moisture'])
            if not 0 <= moisture < 100:
                raise DomainError('RANGE', '水分须在 [0,100) 区间')
            element = raw['element']
            if element not in VALID_ELEMENTS:
                raise DomainError('ELEMENT', '未知元素（仅 Cu/Zn）')
            if raw['basis'] not in ('wet', 'dry'):
                raise DomainError('BASIS', '干湿基标识无效')
            low, high = _assay_bounds(raw['assay'])
            dry_factor = Decimal('1') - moisture / Decimal('100')
            dry_mass = wet * dry_factor
            if raw['basis'] == 'wet':
                low, high = low / dry_factor, high / dry_factor
                if high > 100:
                    raise DomainError('RANGE', '湿基换算干基后含量大于 100%')
            meta = receipts.get(rid)
            if meta is not None and (meta['lot'] != lot or meta['batch'] != batch):
                raise DomainError('CONFLICT', '同一回执编号对应不同批号/到货批次')
            lotrec = lots.get(lot)
            if lotrec is not None:
                if lotrec['receipt_id'] != rid:
                    raise DomainError('CONFLICT', '批号已绑定其他回执：%s' % lotrec['receipt_id'])
                anchor = lotrec['_anchor']
                if anchor != (wet, moisture):
                    raise DomainError('CONFLICT', '同批回执湿重/水分不一致，先隔离')
            else:
                anchor = (wet, moisture)
            receipts[rid] = {'lot': lot, 'batch': batch}
            if lot not in lots:
                lots[lot] = {
                    'lot': lot, 'receipt_id': rid, 'arrival_batch': batch,
                    'wet_mass_kg': str(wet), 'moisture_pct': str(moisture),
                    'dry_total_kg': str(dry_mass), 'dry_balance_kg': str(dry_mass),
                    'status': '可用', 'anchor_row': line,
                    '_anchor': anchor, 'assay': {},
                }
            assays = lots[lot]['assay']
            prior = assays.get(element)
            if prior is not None:
                pf = (Decimal(prior['low_pct']), Decimal(prior['high_pct']))
                if pf == (low, high):
                    events.append({'行号': line, '事件': '重复回执行已跳过',
                                   '回执': rid, '批号': lot, '元素': element})
                    continue
                _quarantine_lot(state, lot, 'CONFLICT',
                                '同批 %s 到货含量不一致（%s–%s 对 %s–%s）'
                                % (element, prior['low_pct'], prior['high_pct'],
                                   fmt(low), fmt(high)), line, rid)
                continue
            assays[element] = {'low_pct': fmt(low), 'high_pct': fmt(high),
                               'basis': 'dry', 'source_row': line,
                               'source_basis': raw['basis']}
            accepted += 1
            events.append({'行号': line, '事件': '回执已归档',
                           '回执': rid, '批号': lot, '元素': element})
        except DomainError as exc:
            state['quarantine'].append(
                {'行号': line, '回执': raw.get('receipt_id', ''),
                 '批号': raw.get('lot', ''), '原值': '|'.join(
                     raw.get(k, '') for k in RECEIPT_HEADERS),
                 '原因码': exc.code, '原因': exc.message})
            bad[0] += 1
    return state, accepted, bad[0]


def _quarantine_lot(state, lot, code, detail, line, rid):
    rec = state['lots'][lot]
    rec['status'] = '隔离'
    state['quarantine'].append({'行号': line, '回执': rid, '批号': lot,
                                '原值': rec['receipt_id'], '原因码': code,
                                '原因': detail})


def _lot_view(rec):
    """对外批号视图：去除内部锚点，附加成分展示串。"""
    view = {k: v for k, v in rec.items() if not k.startswith('_')}
    view['assay'] = [{'元素': el, **vals} for el, vals in sorted(rec['assay'].items())]
    view['到货含量'] = '；'.join(
        '%s %s–%s%%' % (a['元素'], a['low_pct'], a['high_pct'])
        for a in view['assay']) or '缺测'
    return view


def balances(state):
    """当前余量台账：原回执、炉次成分、剩余量在同一视图。"""
    return [_lot_view(rec) for _, rec in sorted(state['lots'].items())]


def issues(state):
    """领用记录（每次去向），按确认顺序返回。"""
    return [dict(r) for r in state.get('issues', [])]


def request_issue(state, *, request_id, lot, furnace, dry_mass, unit,
                  seq=None, idempotency_key=None):
    """单次领用。request_id 相同的重试直接回放原结果，绝不二次扣减。"""
    existing = state.get('issues', [])
    idem = idempotency_key or request_id
    for prior in existing:
        if prior['request_id'] == request_id or prior.get('idempotency_key') == idem:
            if (prior['lot'] == lot and prior['furnace'] == furnace
                    and Decimal(prior['requested_kg']) == _kg(dry_mass, unit)):
                return dict(prior), True
            raise DomainError('IDEMPOTENT',
                              '请求号 %s 已用于不同领用，拒绝重复扣减' % request_id)
    if not request_id:
        raise DomainError('MISSING', '领用请求号为空')
    if not furnace:
        raise DomainError('MISSING', '炉次（去向）为空')
    draw = _kg(dry_mass, unit)
    rec = state['lots'].get(lot)
    if rec is None:
        raise DomainError('NOT_FOUND', '批号 %s 无回执记录' % lot)
    if rec['status'] == '隔离':
        raise DomainError('QUARANTINED', '批号 %s 已隔离，禁止领用' % lot)
    balance = Decimal(rec['dry_balance_kg'])
    if draw > balance:
        raise DomainError('INSUFFICIENT',
                          '领用 %.4fkg 超过干重余量 %.4fkg' % (draw, balance))
    rec['dry_balance_kg'] = str(fmt(balance - draw))
    record = {
        'request_id': request_id, 'idempotency_key': idem,
        'seq': seq if seq is not None else len(existing) + 1,
        'lot': lot, 'receipt_id': rec['receipt_id'], 'furnace': furnace,
        'requested_kg': str(fmt(draw)), 'remaining_kg': rec['dry_balance_kg'],
        'status': '已确认', 'assay_at_issue': rec['assay'] and _lot_view(rec)['到货含量'] or '缺测',
    }
    existing.append(record)
    state['issues'] = existing
    return record, False


def run_batch(state, rows_text):
    """多批领用：中断后从最后一个已确认请求续跑，重试不重复扣减。

    返回每条请求的处理结果；任何一条失败即停止，已确认条目保持不变，
    调用方修正后可用同一 CSV 重新提交（续跑）。
    """
    rows, bad = parse_table(rows_text, ISSUE_HEADERS, state.setdefault('quarantine', []))
    ordered = sorted(rows, key=lambda r: int(number(r['seq'])))
    done = {r['request_id'] for r in state.get('issues', [])}
    results, resumed = [], bool(done)
    for raw in ordered:
        if raw['request_id'] in done:
            prior = next(r for r in state['issues']
                         if r['request_id'] == raw['request_id'])
            results.append({**prior, '处理': '已确认（跳过）'})
            continue
        try:
            record, replayed = request_issue(
                state, request_id=raw['request_id'], lot=raw['lot'],
                furnace=raw['furnace'], dry_mass=raw['dry_mass'],
                unit=raw['unit'], seq=int(number(raw['seq'])))
            # 续跑成功后，移除该请求此前中断时留下的隔离记录
            state['quarantine'] = [
                q for q in state['quarantine']
                if not (q.get('原因码') == 'BATCH_STOP'
                        and q.get('request_id') == raw['request_id'])]
            record['处理'] = '重试回放' if replayed else ('续跑确认' if resumed else '已确认')
            results.append(record)
        except DomainError as exc:
            state['quarantine'].append(
                    {'行号': raw['行号'], '回执': '', '批号': raw.get('lot', ''),
                     'request_id': raw['request_id'],
                     '原值': '|'.join(raw.get(k, '') for k in ISSUE_HEADERS),
                     '原因码': 'BATCH_STOP', '原因': exc.message})
            bad[0] += 1
            return {'results': results, 'stopped_at': raw['request_id'],
                    'reason': exc.message, 'resumed': resumed,
                    'confirmed_count': len(state['issues'])}
    return {'results': results, 'stopped_at': None, 'reason': None,
            'resumed': resumed, 'confirmed_count': len(state['issues'])}


def conservation(state):
    """干重守恒核对：初始干重 = 累计领用 + 当前余量（仅可用批）。"""
    total_open = sum((Decimal(r['dry_total_kg']) for r in state['lots'].values()
                      if r['status'] != '隔离'), Decimal('0'))
    balance = sum((Decimal(r['dry_balance_kg']) for r in state['lots'].values()
                   if r['status'] != '隔离'), Decimal('0'))
    drawn = sum((Decimal(r['requested_kg']) for r in state.get('issues', [])),
                Decimal('0'))
    return {'open_dry_total_kg': str(fmt(total_open)),
            'issued_kg': str(fmt(drawn)),
            'balance_kg': str(fmt(balance)),
            'conserved': total_open == drawn + balance}
