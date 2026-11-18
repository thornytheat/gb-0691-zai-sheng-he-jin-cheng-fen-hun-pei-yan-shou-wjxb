from app.domain import blend
from app.numeric import number
from decimal import Decimal
def test_decimal_dry_total(ctx): # TRAP-10
    assert number(ctx['stages']['4']['metrics'][0][1])==sum({r['lot']:number(r['dry_mass']) for r in ctx['eligible']}.values(),Decimal(0))
def test_unique_lot_mass():
    rows=[{'lot':'a','element':'Cu','dry_mass':'100','low':'10','high':'10'},{'lot':'a','element':'Zn','dry_mass':'100','low':'5','high':'5'}]
    assert blend(rows)[0]['干重_kg']=='100'
def test_exact_blend():
    r=blend([{'lot':'a','element':'Cu','dry_mass':'100','low':'10','high':'10'},{'lot':'b','element':'Cu','dry_mass':'300','low':'20','high':'20'}])[0]
    assert r['含量下界_pct']=='17.5000'
def test_missing_element_uncertain(ctx): assert all(r['缺测批数']>=1 for r in ctx['mixture'])
def test_empty_blend(): assert blend([])==[]
def test_two_elements(ctx): assert [r['元素'] for r in ctx['mixture']]==['Cu','Zn']
def test_weighted_not_arithmetic():
    assert blend([{'lot':'a','element':'Cu','dry_mass':'1','low':'0','high':'0'},{'lot':'b','element':'Cu','dry_mass':'9','low':'100','high':'100'}])[0]['含量下界_pct']=='90.0000'


def test_same_supplier_lot_separated_by_furnace(raw):
    import csv,io
    from app.pipeline import calculate
    records=list(csv.DictReader(io.StringIO(raw)))
    first=records[0];other={**first,'batch':'F-OTHER','mass':'1000','assay':'20'}
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=list(first));writer.writeheader();writer.writerows([first,other])
    result=calculate(out.getvalue())
    assert len(result['eligible'])==2 and not result['quarantine']
    mixtures={r['炉次']:r for r in result['mixture']}
    assert mixtures['F-1108']['含量下界_pct']=='9.0000'
    assert mixtures['F-OTHER']['含量下界_pct']=='20.0000'
