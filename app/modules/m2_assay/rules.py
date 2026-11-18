from app.domain import mass_kg,assay_bounds
from app.numeric import number,fmt
from app.errors import DomainError
from app.reasons import isolate
def apply(ctx):
    accepted=[];seen={};duplicates=0
    for r in ctx['rows']:
        try:
            if not r['batch'] or not r['lot']: raise DomainError('MISSING','炉次或批号为空')
            mass=mass_kg(r['mass'],r['unit']);water=number(r['moisture'])
            if not 0<=water<100: raise DomainError('RANGE','水分须小于100%')
            if r['element'] not in ('Cu','Zn'): raise DomainError('ELEMENT','未知元素')
            if r['basis'] not in ('wet','dry'): raise DomainError('BASIS','干湿基无效')
            low,high=assay_bounds(r['assay']);dry=mass*(1-water/100)
            if r['basis']=='wet': low,high=low/(1-water/100),high/(1-water/100)
            if high>100: raise DomainError('RANGE','转换后含量大于100%')
            key=(r['batch'],r['lot'],r['element']);fingerprint=(mass,water,low,high,r['revision'])
            if key in seen:
                if seen[key]==fingerprint: duplicates+=1
                else: isolate(ctx,r,'CONFLICT','同一批元素数值不一致')
                continue
            seen[key]=fingerprint
            accepted.append({**r,'dry_mass':str(dry),'low':str(low),'high':str(high)})
        except DomainError as e: isolate(ctx,r,e.code,e.message)
    ctx['normalized']=accepted;ctx['duplicates']=duplicates
    return {'rows':accepted,'metrics':[['有效成分',len(accepted),'条'],['隔离',len(ctx['quarantine']),'条'],['重复',duplicates,'条']]}

