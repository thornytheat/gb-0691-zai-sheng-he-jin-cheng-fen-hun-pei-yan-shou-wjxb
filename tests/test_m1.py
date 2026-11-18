from app.reader import decode
from app.pipeline import calculate
from app.errors import DomainError
import pytest
def test_sample_lots(ctx): assert len(ctx['stages']['1']['rows'])==50
def test_bom_header(raw): # TRAP-02
    assert calculate('\ufeff'+raw)['input_count']==50
def test_legacy_encoding(): # TRAP-01
    from app.config import SAMPLE
    raw=SAMPLE.with_name('legacy-gb18030.csv').read_bytes();assert 'lot' in decode(raw)
def test_structural_row(raw): assert any(r['原因码']=='COLUMNS' for r in calculate(raw+'bad,row\n')['quarantine'])
def test_empty_rejected():
    with pytest.raises(DomainError): calculate('')
def test_header_only(raw):
    with pytest.raises(DomainError): calculate(raw.splitlines()[0]+'\n')
def test_sample_input_account(ctx): assert ctx['input_count']==50

