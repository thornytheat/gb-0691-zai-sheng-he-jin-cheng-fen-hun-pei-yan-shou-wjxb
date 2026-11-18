from app.domain import mass_kg,assay_bounds
from app.numeric import number
from decimal import Decimal
def test_thousands(): # TRAP-06
    assert mass_kg('１,２３４','kg')==Decimal('1234')
def test_units(): # TRAP-15
    assert mass_kg('0.1','t')==100
def test_sentinel_isolation(ctx): # TRAP-07
    assert sum(r['原因码']=='MISSING' for r in ctx['quarantine'])==2
def test_conflict_preserved(ctx): # TRAP-14
    assert sum(r['原因码']=='CONFLICT' for r in ctx['quarantine'])==1
def test_duplicate_separate(ctx): assert ctx['duplicates']==1
def test_nondetect_interval(): assert assay_bounds('<0.1')==(Decimal(0),Decimal('0.1'))
def test_wet_basis_conversion(ctx): assert next(r for r in ctx['normalized'] if r['lot']=='00902')['dry_mass']=='99.000'

