# 香葱行情

- **自动化 ID**：`376dffed-c5e4-4904-a77a-29193947212a`
- **调度**：每日 00:00（北京时间）· `FREQ=DAILY;BYHOUR=0;BYMINUTE=0`
- **状态**：ACTIVE
- **工作目录**：`C:\Users\不言不语\WorkBuddy\automation-2026-10-24-02-17-56`
- **数据落盘**：`data/sources/xiangcong_YYYY-MM-DD.json`（汇总进日报第九章并推送 GitHub）

> 本文件为该定时任务的完整配置快照，用于版本管理与迁移恢复。

## 完整提示词

````text
 每日定时获取全国各地天气、自然灾害数据，分析已经过去的12个月，24个月，36个月直到10年内价格行情走势，未来三天、一星期、半个月、一个月、两个月、三个月香葱行情，统计市面上常见的香葱种类，以及全国香葱种植省份，重点统计并预测泸西县的香葱行情，并生成图表

---

## 数据落盘与交付（必执行 — 供 GitHub 汇总推送）

完成本期分析后，必须把本任务采集到的**全部**行情数据按下列统一 schema 写入文件（UTF-8，当日同名文件直接覆盖）：

路径：`C:/Users/不言不语/WorkBuddy/automation-2026-10-24-02-17-56/xiangcong-monitor/data/sources/xiangcong_YYYY-MM-DD.json`

```json
{
  "task": "香葱行情",
  "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
  "date": "YYYY-MM-DD",
  "generated_at": "YYYY-MM-DD HH:MM",
  "market_scope": "全国 / 云南 / 泸西县（按实际覆盖范围填写）",
  "quotes": [
    {"date":"YYYY-MM-DD","item":"香葱","variety":"","market":"市场名","province":"省份",
     "price_type":"产地地头价|产地收购价|产地批发价|销地批发价|零售价",
     "unit":"元/公斤","low":4.0,"high":6.0,"mid":5.0,
     "source":"来源名","source_url":"","note":"口径或估算说明"}
  ],
  "forecasts": [
    {"horizon":"未来3天","target_date":"YYYY-MM-DD","item":"香葱",
     "center":4.49,"low":4.25,"high":4.73,"delta_pct":3.2,"confidence":"高"}
  ],
  "summary": "本期核心结论（1-3 句）"
}
```

要求：
1. `quotes` 写入本期实际采集到的**全部**报价行，全量不截断（不得只写最新一条）；确实无数据时写 `[]` 并在 summary 说明原因。
2. `forecasts` 覆盖六档：未来 3 天 / 7 天 / 15 天 / 1 个月 / 2 个月 / 3 个月。
3. 价格统一换算为 **元/公斤**；`price_type` 必须标注口径；估算值须在 `note` 注明。
4. 该文件会在每日 03:00 由「香葱行情日报 · 每日03:00生成并推送」任务汇总进日报第九章「多源行情汇总 · 全部定时任务」，与本仓库数据一并推送到 GitHub。
````
