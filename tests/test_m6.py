from app.modules.m6_acceptance.rules import apply
from copy import deepcopy
def test_input_conservation(ctx): assert ctx['balanced'] is True
def test_acceptance_sample(ctx): assert len(ctx['acceptance'])==2
def test_exact_boundary_pass(ctx):
    c=deepcopy(ctx);c['intervals']=[{'元素':'Cu','含量下界_pct':'7.5','含量上界_pct':'12.5'}];assert apply(c)['rows'][0]['验收']=='通过'
def test_outside_range_fails(ctx):
    c=deepcopy(ctx);c['intervals']=[{'元素':'Cu','含量下界_pct':'13','含量上界_pct':'14'}];assert apply(c)['rows'][0]['验收']=='不合格'
def test_straddling_requires_test(ctx):
    c=deepcopy(ctx);c['intervals']=[{'元素':'Cu','含量下界_pct':'7','含量上界_pct':'8'}];assert apply(c)['rows'][0]['验收']=='待补测'
def test_limits_in_evidence(ctx): assert all('下限_pct' in r for r in ctx['acceptance'])
def test_mismatch_visible(ctx):
    c=deepcopy(ctx);c['input_count']+=1;apply(c);assert c['balanced'] is False

