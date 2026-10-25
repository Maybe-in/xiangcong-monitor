# automations/ —— 香葱行情定时任务配置库

本目录保存该项目全部定时任务的**完整配置快照**，随代码一起版本管理、推送到 GitHub。
目的：任务配置可追溯、可回滚、可迁移（换机器或误删后能一键恢复）。

## 任务清单

| 文件 | 任务名 | 自动化 ID | 调度（北京时间） | 落盘 slug |
|---|---|---|---|---|
| `00-香葱行情日报推送.md` | 香葱行情日报 · 每日03:00生成并推送 | `5be6d07b-142f-4fe6-8182-5765cc9bfcfc` | 每日 03:00 | —（汇总方） |
| `01-gemini-香葱行情.md` | Gemini 每日香葱行情分析与预测报告 | `dd13c14c-2a95-457f-9572-dd8c3a24e804` | 每日 00:00 | `gemini` |
| `02-chatgpt-香葱行情监测.md` | 香葱行情监测chat gpt | `0a26a286-95dc-4caf-b14a-c4344b691c9b` | 每日 00:00 | `chatgpt` |
| `03-national-全国香葱行情监测.md` | 全国香葱行情监测与泸西县价格预测（每日） | `83f1872b-7ec4-44d5-be6d-4599a5a011c4` | 每日 00:00 | `national` |
| `04-grok-香葱行情.md` | grok香葱 | `bc2b2b8d-46a3-467e-a403-177edbac6841` | 每日 00:00 | `grok` |
| `05-xiangcong-香葱行情.md` | 香葱行情 | `376dffed-c5e4-4904-a77a-29193947212a` | 每日 00:00 | `xiangcong` |

## 协作链路

```
00:00  5 个生成任务采集行情
       └─ 写入 data/sources/<slug>_YYYY-MM-DD.json（统一 schema，全量不截断）
03:00  推送任务（00-）运行 run.py
       ├─ 汇总 data/sources/*.json → 日报第九章 + outputs/sources.html
       ├─ 新发地接口全部明细 → 「接口全部明细」表
       └─ git commit & push → GitHub（GitHub Actions 同时发布 Pages）
```

## 如何恢复一个任务

1. 打开对应 `.md`，复制「完整提示词」代码块内的全部内容（不含首尾 ```` 围栏）。
2. 在 WorkBuddy 新建自动化任务，粘贴为提示词。
3. 按文件头部标注设置：调度时间、状态 ACTIVE、工作目录。
4. 生成任务需确认落盘 slug 与表中一致，否则推送任务汇总不到它的数据。

## 统一数据 schema

```json
{
  "task": "任务名", "task_id": "自动化ID",
  "date": "YYYY-MM-DD", "generated_at": "YYYY-MM-DD HH:MM",
  "market_scope": "全国 / 云南 / 泸西县",
  "quotes": [{"date","item","variety","market","province","price_type",
              "unit","low","high","mid","source","source_url","note"}],
  "forecasts": [{"horizon","target_date","item","center","low","high","delta_pct","confidence"}],
  "summary": "本期核心结论"
}
```

价格统一 **元/公斤**；`price_type` 必填（产地地头价 / 产地收购价 / 产地批发价 /
销地批发价 / 零售价）；估算值在 `note` 注明。汇总窗口默认 3 天。
