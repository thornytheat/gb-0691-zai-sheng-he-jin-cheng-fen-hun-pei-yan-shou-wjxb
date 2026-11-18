from copy import deepcopy
from app.modules.m3_recipe.rules import apply
def test_recipe_v1(ctx): assert all(r['配方']=='V1' for r in ctx['stages']['3']['rows'])
def test_recipe_eligible(ctx): assert len(ctx['eligible'])==46
def test_moisture_limit(ctx):
    c=deepcopy(ctx);c['normalized']=[{**c['normalized'][0],'moisture':'6'}];apply(c);assert not c['eligible']
def test_conflicting_lot_mass(ctx): # TRAP-19
    c=deepcopy(ctx);c['normalized'][1]['dry_mass']='999';apply(c);assert all(r['lot']!='00001' for r in c['eligible'])
def test_version_lock(ctx): # TRAP-25
    c=deepcopy(ctx);c['normalized']=[{**c['normalized'][0],'revision':'2'}];apply(c);assert c['quarantine'][-1]['原因码']=='REVISION'
def test_order_independence(ctx):
    c=deepcopy(ctx);c['normalized'].reverse();apply(c);assert len(c['eligible'])==len(ctx['eligible'])
def test_recipe_sample_reject_count(ctx): assert ctx['stages']['3']['new_quarantine']==0

