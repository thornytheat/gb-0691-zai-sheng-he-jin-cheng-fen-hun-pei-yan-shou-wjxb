from app.domain import TARGETS
from app.numeric import number
def apply(ctx):
    rows=[]
    for r in ctx['intervals']:
        lo,hi=TARGETS[r['元素']];a=number(r['含量下界_pct']);b=number(r['含量上界_pct'])
        status='通过' if lo<=a<=b<=hi else '不合格' if b<lo or a>hi else '待补测'
        rows.append({**r,'下限_pct':str(lo),'上限_pct':str(hi),'验收':status})
    ctx['acceptance']=rows
    balance=ctx['input_count']==len(ctx['normalized'])+ctx['duplicates']+len([r for r in ctx['quarantine'] if r['原因码'] not in ('LOT_CONFLICT','MOISTURE','REVISION')])
    ctx['balanced']=balance
    return {'rows':rows,'metrics':[['验收通过',sum(r['验收']=='通过' for r in rows),'项'],['输入守恒','相符' if balance else '差异',''],['累计隔离',len(ctx['quarantine']),'条']]}

