from app.numeric import number
from app.modules.m5_uncertainty.rules import apply
def test_sample_uncertainty(ctx): assert all(r['判定']=='需补测' for r in ctx['intervals'])
def test_width_nonnegative(ctx): assert all(number(r['区间宽度_pct'])>=0 for r in ctx['intervals'])
def test_known_bounds():
    c={'mixture':[{'含量下界_pct':'1','含量上界_pct':'2'}]};r=apply(c);assert r['rows'][0]['区间宽度_pct']=='1.0000'
def test_known_exact():
    c={'mixture':[{'含量下界_pct':'1','含量上界_pct':'1'}]};assert apply(c)['rows'][0]['判定']=='确定值'
def test_empty_uncertainty(): assert apply({'mixture':[]})['rows']==[]
def test_nondetect_not_zero(ctx): assert next(r for r in ctx['normalized'] if r['lot']=='00902')['high']!='0'
def test_unknown_lot_adds_upper(ctx): assert all(number(r['含量上界_pct'])>number(r['含量下界_pct']) for r in ctx['mixture'])

