# 再生合金成分混配与验收

再生金属配料员使用本工具完成：合并废料检验批，按配方称重混配并复核各元素上下限。

## 业务

元素质量按物料净重×含量汇总；干湿基转换，低于检出限给上下界，不可把未检出当零，配方版本锁定。七个模块：来料接收、成分归一、配方约束、混配试算、不确定区间、验收对照、复配批次。模块独立API及页面入口见docs/API.md。样例中包含真实常见脏数据，原因码和原始行号在隔离面板及证据文件中可复核。

## 启动与验证

```sh
docker compose up --build -d
docker compose exec -T app pytest -q
docker compose config --quiet
```

打开 http://localhost:18205 。点击“运行样例”，或展开输入区提交CSV。切换七个模块查看计算依据。复核区可通过或退回，同一版本仅允许一次复核。证据CSV包含所有阶段与隔离行，批次内容不因复核变更。

SQLite保存在命名卷records；容器重建保留历史。只在确认不再需要数据时执行 `docker compose down -v` 重建。端口可通过.env中的PORT调整。本地也可 `pip install -r requirements.txt` 后 `python -m app.main`。

## 定义与限制

详见docs/DATA-DICTIONARY.md、docs/DEPTH.md。单文件最大5MB/一万行，本工具按确定性文件离线复算，不查询外部业务系统。源码位于app，测试位于tests，样例位于sample_data。
