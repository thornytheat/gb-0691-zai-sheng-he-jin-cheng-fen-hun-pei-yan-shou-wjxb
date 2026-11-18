from app.domain import blend
from app.numeric import number
from decimal import Decimal

def apply(ctx):
    rows=[]
    for batch in sorted({r['batch'] for r in ctx['eligible']}):
        group=[r for r in ctx['eligible'] if r['batch']==batch]
        rows.extend({'炉次':batch,**row} for row in blend(group))
    ctx['mixture']=rows
    lots={(r['batch'],r['lot']):number(r['dry_mass']) for r in ctx['eligible']}
    total=sum(lots.values(),Decimal(0))
    return {'rows':rows,'metrics':[['混配干重',str(total),'kg'],['元素',len(rows),'项'],['来料批次',len(lots),'批']]}
