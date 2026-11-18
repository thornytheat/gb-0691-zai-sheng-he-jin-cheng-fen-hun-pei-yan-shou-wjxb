from app.modules.m7_reblend.rules import apply
from copy import deepcopy
def test_sample_candidates(ctx): assert len(ctx['stages']['7']['rows'])==24
def test_removal_conserves_lots(ctx): assert all(r['剩余批次']==23 for r in ctx['stages']['7']['rows'])
def test_candidate_order(ctx): assert ctx['stages']['7']['rows'][0]['移除批号']=='00001'
def test_reblend_empty(): assert apply({'eligible':[]})['rows']==[]
def test_reblend_single(ctx):
    c=deepcopy(ctx);c['eligible']=c['eligible'][:1];assert apply(c)['rows'][0]['复配结果']=='需复测'
def test_reblend_deterministic(ctx): assert apply(ctx)['rows']==apply(ctx)['rows']
def test_bad_lots_excluded(ctx): assert all(r['移除批号']!='00900' for r in ctx['stages']['7']['rows'])

