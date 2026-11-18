# 深度登记 再生合金成分混配与验收

- 规模：中型
- 使用者与工作流：再生金属配料员，合并废料检验批，按配方称重混配并复核各元素上下限。
- 核心规则：元素质量按物料净重×含量汇总；干湿基转换，低于检出限给上下界，不可把未检出当零，配方版本锁定。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 来料接收 | 运行来料接收并复核证据 | `POST /api/m1`；`/work/1` | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py` |
| M2 成分归一 | 运行成分归一并复核证据 | `POST /api/m2`；`/work/2` | `app/modules/m2_assay/rules.py` | `tests/test_m2.py` |
| M3 配方约束 | 运行配方约束并复核证据 | `POST /api/m3`；`/work/3` | `app/modules/m3_recipe/rules.py` | `tests/test_m3.py` |
| M4 混配试算 | 运行混配试算并复核证据 | `POST /api/m4`；`/work/4` | `app/modules/m4_blend/rules.py` | `tests/test_m4.py` |
| M5 不确定区间 | 运行不确定区间并复核证据 | `POST /api/m5`；`/work/5` | `app/modules/m5_uncertainty/rules.py` | `tests/test_m5.py` |
| M6 验收对照 | 运行验收对照并复核证据 | `POST /api/m6`；`/work/6` | `app/modules/m6_acceptance/rules.py` | `tests/test_m6.py` |
| M7 复配批次 | 运行复配批次并复核证据 | `POST /api/m7`；`/work/7` | `app/modules/m7_reblend/rules.py` | `tests/test_m7.py` |
| M8 称重回执台账 | 回执建账、干重领用、续跑去重、台账下载 | `POST /api/m8/ledgers`；`/ledger` | `app/modules/m8_ledger/rules.py` | `tests/test_m8_rules.py`、`tests/test_m8_api.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py::test_legacy_encoding` |
| TRAP-06 | 千分位与全角 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_assay/rules.py` | `tests/test_m2.py::test_thousands` |
| TRAP-07 | 空值不可当零 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_assay/rules.py` | `tests/test_m2.py::test_sentinel_isolation` |
| TRAP-10 | 干重精确守恒 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m4_blend/rules.py` | `tests/test_m4.py::test_decimal_dry_total` |
| TRAP-14 | 同键冲突 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_assay/rules.py` | `tests/test_m2.py::test_conflict_preserved` |
| TRAP-15 | 吨与千克 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_assay/rules.py` | `tests/test_m2.py::test_units` |
| TRAP-19 | 批号元数据冲突优先 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m3_recipe/rules.py` | `tests/test_m3.py::test_conflicting_lot_mass` |
| TRAP-25 | 配方版本锁定 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m3_recipe/rules.py` | `tests/test_m3.py::test_version_lock` |
| TRAP-31 | 湿重直接投料超投 | 结算湿重被当成可投量 | 湿重仅作结算依据，领用只扣脱水干重余量 | `app/modules/m8_ledger/rules.py` | `tests/test_m8_rules.py::test_wet_weight_kept_for_settlement_dry_balance_for_production` |
| TRAP-32 | 重试重复扣减 | 网络重试再次扣余量 | request_id/幂等键回放原记录，不二次扣减 | `app/modules/m8_ledger/rules.py` | `tests/test_m8_rules.py::test_retry_same_request_id_replays_without_double_deduction` |
| TRAP-33 | 中断续跑重复确认 | 整批重跑导致已确认项重复 | 按已确认 request_id 跳过，从未确认处续跑 | `app/modules/m8_ledger/rules.py` | `tests/test_m8_rules.py::test_batch_interrupts_and_resumes_from_confirmed_point` |
| TRAP-34 | 同批回执不一致 | 静默采信后值覆盖前值 | 整批隔离并禁止领用，保留冲突原值 | `app/modules/m8_ledger/rules.py` | `tests/test_m8_rules.py::test_conflicting_assay_quarantines_whole_lot_and_blocks_issue` |

## 对账规则

输入记录 = 采信记录 + 隔离记录 + 相同行重复。重复表头与空行单独记数。业务合计按阶段中的守恒或差值列复核。运行清单有原文SHA256、规则版本与耗时；相同规则版本下同文重复提交复用批次。

## 已知不覆盖

部署为本地单用户工具，不连接外部上游系统。CSV单文件5MB及一万条业务记录上限；不推断未提供的未知数据。
