REASONS = {"COLUMNS":"列数不符", "HEADER":"字段缺失", "MISSING":"必填值为空", "NUMBER":"数值无效", "RANGE":"超出范围", "DUPLICATE":"相同行重复", "CONFLICT":"同键数值冲突", "VERSION":"版本冲突", "EMPTY":"输入为空", "STRUCTURE":"文件结构错误", "UNIT":"单位无效", "ELEMENT":"元素无效", "BASIS":"干湿基无效", "NOT_FOUND":"台账或批号不存在", "INSUFFICIENT":"干重余量不足", "QUARANTINED":"批号已隔离", "IDEMPOTENT":"请求号幂等冲突", "BATCH_STOP":"批量领用中断", "REQUEST":"请求格式错误", "LOT_CONFLICT":"批号元数据冲突", "MOISTURE":"水分超标", "REVISION":"配方版本不符"}
def isolate(ctx, row, code, detail):
    ctx['quarantine'].append({**row, '原因码': code, '原因': detail})
