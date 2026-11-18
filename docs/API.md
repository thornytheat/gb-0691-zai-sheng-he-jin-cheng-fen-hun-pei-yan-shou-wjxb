# 接口

`POST /api/run`：JSON中的csv文本，省略使用样例；或multipart字段file。最大5MB。

`POST /api/m1`至`POST /api/m7`：独立运行到指定模块，JSON结构同运行接口。

`GET /api/history`：历史批次。`POST /api/review`接收id、revision和decision（通过或退回）。`GET /api/evidence.csv`提供单一证据导出。

结构错误422，版本变化409，文件过大413；错误返回code与message。所有页面可从左侧七个模块入口访问。

`GET /api/runs/<id>`读取指定批次；页面与证据CSV通过run_id查询参数绑定批次，模块导航保留该参数。

JSON请求体必须是对象，数组、标量、null、损坏JSON及错误上传字段返回400，且不运行默认样例。

## M8 称重回执领用台账（`/ledger`）

状态化模块，独立表 `ledger_state`/`ledger_issues` 存储，与七阶段计算批次互不影响。

- `POST /api/m8/ledgers`：按称重回执 CSV 建账（JSON `{"csv": ...}` 或 multipart 字段 `receipts`）。同规则版本+同回执内容复用同一台账，返回 `reused=true`。
- `GET /api/m8/ledgers`：台账清单；`GET /api/m8/ledgers/<ledger_id>`：单台账视图（批号台账、领用记录、隔离区、守恒）。
- `POST /api/m8/ledgers/<id>/issue`：单次领用，字段 `request_id,lot,furnace,dry_mass,unit`。同一 `request_id`（或 `idempotency_key`）重试回放原记录，不二次扣减；同号不同载荷返回 422 `IDEMPOTENT`。
- `POST /api/m8/ledgers/<id>/batch`：多批领用 CSV（JSON 或 multipart 字段 `issuances`，表头 `request_id,seq,lot,furnace,dry_mass,unit`）。任一请求失败即停，返回 `stopped_at`；已确认请求在重提交时跳过（续跑），成功续跑后清除该请求的 `BATCH_STOP` 隔离记录。
- `GET /api/m8/ledgers/<id>/ledger.csv`：台账下载，含原回执（原始湿重/到货含量）、每次领用去向（炉次/干重/领后余量）、当前余量与干重守恒、隔离记录四段。

业务错误码：`INSUFFICIENT`（超投，不扣减）、`QUARANTINED`（隔离批禁领）、`IDEMPOTENT`（请求号冲突）、`NOT_FOUND`（台账或批号不存在）、`BATCH_STOP`（批量中断）、`CONFLICT`（同批回执不一致，整批隔离）。
