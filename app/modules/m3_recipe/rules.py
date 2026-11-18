from app.numeric import number
from app.reasons import isolate
def apply(ctx):
    rows=[];valid=[];lotmeta={};conflicted=set()
    for r in ctx['normalized']:
        meta=(number(r['dry_mass']),number(r['moisture']),r['batch'],r['revision'])
        key=(r['batch'],r['lot'])
        if key in lotmeta and lotmeta[key]!=meta: conflicted.add(key)
        lotmeta[key]=meta
    for r in ctx['normalized']:
        reason='LOT_CONFLICT' if (r['batch'],r['lot']) in conflicted else 'MOISTURE' if number(r['moisture'])>5 else 'REVISION' if r['revision']!='1' else ''
        if reason: isolate(ctx,r,reason,'来料条件不符合配方V1')
        else: valid.append(r)
        rows.append({'炉次':r['batch'],'批号':r['lot'],'元素':r['element'],'配方':'V1','状态':reason or '可配','行号':r['行号']})
    ctx['eligible']=valid
    return {'rows':rows,'metrics':[['可配成分',len(valid),'条'],['冲突批',len(conflicted),'批'],['配方版本',1,'版']]}

