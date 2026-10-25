# 历史数据规则

- 每天只新增 `outputs/history/YYYY-MM-DD.json` 和 `outputs/luxi/YYYY-MM-DD.html`。
- 已存在的日期文件禁止覆盖、禁止删除。
- `outputs/香葱行情日报_*.html`、`latest.html`、`archive.json` 是原有红葱/黑葱日报，不要动。
- 同一天重跑时，如果该日期文件已在，跳过。
- 可以更新 `outputs/history/index.json`、`outputs/luxi/index.html`、`outputs/latest-luxi.json` 和归档首页里的泸西专项表，但只能追加行。
