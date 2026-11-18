"""M8 台账下载：原回执、每次去向、剩余量三类记录同表可复核。"""
import csv
import io


def build_ledger_csv(data):
    out = io.StringIO(newline='')
    w = csv.writer(out)
    lid = data['ledger_id']
    w.writerow(['# 台账', lid, '规则版本', data['rule_version'],
                '回执SHA256', data['receipt_sha256'], '创建时间', data['created_at']])
    # 一、原回执（结算依据：原始湿重 + 到货含量）
    w.writerow([])
    w.writerow(['== 原回执（结算口径：原始湿重/到货含量）=='])
    w.writerow(['批号', '回执编号', '到货批次', '原始湿重_kg', '水分_pct',
                '脱水干重_kg', '当前干重余量_kg', '状态', '到货含量(干基)'])
    for lot in data['lots']:
        w.writerow([lot['lot'], lot['receipt_id'], lot['arrival_batch'],
                    lot['wet_mass_kg'], lot['moisture_pct'], lot['dry_total_kg'],
                    lot['dry_balance_kg'], lot['status'], lot['到货含量']])
    # 二、每次领用去向（生产口径：干重扣减）
    w.writerow([])
    w.writerow(['== 每次领用去向（配料口径：脱水干重）=='])
    w.writerow(['序号', '请求号', '批号', '回执编号', '去向炉次',
                '本次领用干重_kg', '领后余量_kg', '状态', '领用时刻成分', '处理'])
    for issue in data['issues']:
        w.writerow([issue['seq'], issue['request_id'], issue['lot'],
                    issue['receipt_id'], issue['furnace'], issue['requested_kg'],
                    issue['remaining_kg'], issue['status'],
                    issue.get('assay_at_issue', ''), issue.get('处理', '已确认')])
    # 三、剩余量与守恒
    w.writerow([])
    w.writerow(['== 当前余量与干重守恒 =='])
    c = data['conservation']
    w.writerow(['可用批初始干重_kg', c['open_dry_total_kg'],
                '累计领用_kg', c['issued_kg'],
                '当前余量_kg', c['balance_kg'],
                '守恒核对', '相符' if c['conserved'] else '差异'])
    # 四、隔离记录
    w.writerow([])
    w.writerow(['== 隔离记录（不一致先隔离，不参与扣减）=='])
    w.writerow(['原始行', '回执', '批号', '原因码', '原因', '原值'])
    for q in data['quarantine']:
        w.writerow([q.get('行号', ''), q.get('回执', ''), q.get('批号', ''),
                    q.get('原因码', ''), q.get('原因', ''), q.get('原值', '')])
    return out.getvalue()
