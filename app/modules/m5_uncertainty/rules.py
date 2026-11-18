from app.numeric import number,fmt
def apply(ctx):
    rows=[]
    for r in ctx['mixture']:
        width=number(r['含量上界_pct'])-number(r['含量下界_pct'])
        rows.append({**r,'区间宽度_pct':fmt(width),'判定':'需补测' if width else '确定值'})
    ctx['intervals']=rows
    return {'rows':rows,'metrics':[['需补测',sum(r['判定']=='需补测' for r in rows),'项'],['确定值',sum(r['判定']=='确定值' for r in rows),'项']]}

