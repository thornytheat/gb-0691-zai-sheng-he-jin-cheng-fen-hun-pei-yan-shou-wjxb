import csv, io
from app.config import HEADERS, LIMIT
from app.errors import DomainError
from app.reasons import isolate
def decode(raw):
    for encoding in ('utf-8-sig','gb18030'):
        try: return raw.decode(encoding)
        except UnicodeDecodeError: pass
    raise DomainError('ENCODING','无法识别文件编码')
def parse_table(text, expected_headers, quarantine):
    """通用 CSV 解析：表头可调序、不得缺列/重复；结构脏行进隔离区。

    返回 (业务行列表, 隔离计数)。结构错误抛 DomainError，由上层决定状态码。
    计数用单元素列表承载，便于在循环中累加并回传给调用方。
    """
    text=text.lstrip('﻿') if isinstance(text,str) else ''
    if not text: raise DomainError('EMPTY','输入为空')
    reader=csv.reader(io.StringIO(text, newline=''), strict=True)
    try: head=next(reader,None)
    except csv.Error: raise DomainError('STRUCTURE','表头损坏')
    if head is None: raise DomainError('BLANK','文件仅有空行')
    head=[x.strip() for x in head]
    if set(head)!=set(expected_headers) or len(head)!=len(expected_headers):
        raise DomainError('HEADER','字段缺失或重复')
    rows=[];bad=[0];blank=0;repeated_head=0
    try:
        for cells in reader:
            if len(rows)+len(quarantine)+bad[0] >= LIMIT:
                raise DomainError('LIMIT','文件超过一万行')
            if not cells or all(not x.strip() for x in cells): blank+=1;continue
            if cells==head: repeated_head+=1;continue
            if len(cells)!=len(head):
                quarantine.append({'行号':reader.line_num,'原值':'|'.join(cells),
                                   '原因码':'COLUMNS','原因':'列数不符'})
                bad[0]+=1;continue
            rows.append({**dict(zip(head,[x.strip() for x in cells])),'行号':reader.line_num})
    except csv.Error: raise DomainError('STRUCTURE','引号未闭合或记录截断')
    if not rows and not quarantine:
        raise DomainError('HEADER_ONLY' if not blank else 'BLANK','文件没有业务记录')
    return rows,bad
def read_rows(ctx):
    text=ctx['text'].lstrip('﻿')
    if not text: raise DomainError('EMPTY','输入为空')
    reader=csv.reader(io.StringIO(text, newline=''), strict=True)
    try: head=next(reader,None)
    except csv.Error: raise DomainError('STRUCTURE','表头损坏')
    if head is None: raise DomainError('BLANK','文件仅有空行')
    head=[x.strip() for x in head]
    if set(head)!=set(HEADERS) or len(head)!=len(HEADERS):
        raise DomainError('HEADER','字段缺失或重复')
    rows=[];ctx['input_count']=0;ctx['blank_count']=0;ctx['header_count']=0
    try:
        for cells in reader:
            if len(rows)+len(ctx['quarantine']) >= LIMIT: raise DomainError('LIMIT','文件超过一万行')
            if not cells or all(not x.strip() for x in cells): ctx['blank_count']+=1;continue
            if cells==head: ctx['header_count']+=1;continue
            ctx['input_count']+=1
            if len(cells)!=len(head):
                isolate(ctx,{'行号':reader.line_num,'原值':'|'.join(cells)},'COLUMNS','列数不符');continue
            rows.append({**dict(zip(head,[x.strip() for x in cells])), '行号':reader.line_num})
    except csv.Error: raise DomainError('STRUCTURE','引号未闭合或记录截断')
    if not rows and not ctx['quarantine']: raise DomainError('HEADER_ONLY' if not ctx['blank_count'] else 'BLANK','文件没有业务记录')
    ctx['rows']=rows
    return rows
