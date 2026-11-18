from decimal import Decimal
from app.numeric import number, fmt
from app.errors import DomainError
TARGETS={'Cu':(Decimal('7.5'),Decimal('12.5')),'Zn':(Decimal('3'),Decimal('7'))}
def mass_kg(value,unit):
    if unit not in ('kg','t'): raise DomainError('UNIT','重量单位无效')
    value=number(value)*(1000 if unit=='t' else 1)
    if value<=0: raise DomainError('RANGE','重量必须大于零')
    return value
def assay_bounds(value):
    if value.startswith('<'):
        upper=number(value[1:]);low=Decimal(0)
    else: low=upper=number(value)
    if not 0<=low<=upper<=100: raise DomainError('RANGE','元素含量超出范围')
    return low,upper
def blend(rows):
    lots={r['lot']:number(r['dry_mass']) for r in rows};total=sum(lots.values(),Decimal(0))
    answer=[]
    for element in sorted({r['element'] for r in rows}):
        group=[r for r in rows if r['element']==element]
        present={r['lot'] for r in group}
        low=sum((number(r['dry_mass'])*number(r['low'])/100 for r in group),Decimal(0))
        high=sum((number(r['dry_mass'])*number(r['high'])/100 for r in group),Decimal(0))
        missing=sum((mass for lot,mass in lots.items() if lot not in present),Decimal(0))
        answer.append({'元素':element,'干重_kg':str(total),'元素下界_kg':str(low),'元素上界_kg':str(high+missing),'含量下界_pct':fmt(low/total*100) if total else '0','含量上界_pct':fmt((high+missing)/total*100) if total else '0','缺测批数':len(lots)-len(present)})
    return answer
