# 香葱预测

> 仓库显示名：**香葱预测** ｜ 仓库地址 slug：`xiangcong-yuce`
> 每日自动采集**全国天气**与**自然灾害预警**数据，回顾**过去 12 / 24 / 36 / 60 / 120 个月**的香葱价格走势，
> 预测**未来 3 天 / 1 周 / 半月 / 1 月 / 2 月 / 3 月**行情，统计市面常见香葱种类与全国种植省份分布，
> 并**重点跟踪云南泸西县**（全国最大香葱单品生产基地）。

由 GitHub Actions 在**北京时间每日早上 8:00** 定时执行，自动生成单页 HTML 报告并提交回仓库，可一键发布为 GitHub Pages 站点。

---

## 一、目录结构

```
xiangcong-yuce/
├── .github/workflows/daily-report.yml   # 定时任务（UTC 00:00 = 北京 08:00）
├── run.py                               # 主入口：编排采集 → 预测 → 渲染
├── src/
│   ├── config.py                        # 产区、观测点、品种、模型参数
│   ├── weather.py                       # 天气采集（Open-Meteo）
│   ├── disaster.py                      # 灾害预警（中央气象台）
│   ├── price.py                         # 价格历史 + 六档预测模型
│   ├── longterm.py                      # 10 年长周期序列重建 + 窗口统计
│   └── report.py                        # HTML 报告渲染（含 SVG 走势图）
├── automations/                         # 定时任务配置库（6 个任务的完整提示词快照）
│   └── README.md                        # 任务索引 / 协作链路 / 恢复指南
├── data/
│   ├── price_history.json               # 价格历史（observed 实测 / model 估算）
│   └── sources/                         # 其余定时任务按统一 schema 落盘的行情数据
│       └── <任务slug>_YYYY-MM-DD.json   # 由推送任务汇总进日报第九章「多源行情汇总」
├── outputs/                             # 报告产出（提交入库，用于 Pages）
│   ├── 香葱行情日报_YYYY-MM-DD.html
│   ├── latest.html                      # 最新一期
│   ├── index.html                       # 报告归档列表
│   └── data.json                        # 机器可读数据
├── requirements.txt
└── README.md
```

## 二、数据源

| 模块 | 来源 | 说明 |
|---|---|---|
| 天气 | Open-Meteo Forecast API | 核心产区 16 天逐日预报（气温/降水/风速/天气现象），ECMWF、ICON 等多模式融合 |
| 气候基准 | Open-Meteo Archive API | 近 30 天实测气温，用于计算距平；失败时回退月气候态 |
| 自然灾害 | 中央气象台 `nmc.cn/rest/findAlarm` | 全国生效气象预警，按省/灾种聚合并做产业链二次分级 |
| 价格 | 人工录入实测观测点 | 云南产地综合交易价、昆明王旗营批发市场等 |
| 产业底数 | 泸西县政府/红河州媒体公开报道、百度百科 | 基地面积、产量、产值、销售半径等 |

> **透明度声明**：农产品批发价格尚无稳定可用的免鉴权公开接口，当前版本价格采用「人工实测观测点 + 模型估算」混合口径，报告中会明确标注实际使用的数据层级。

## 三、预测模型

```
P(h) = P₀ × SeasonalRatio(target, today)
          × (1 + WeatherImpact[0, h))
          × (1 + Momentum(h))
          × (1 + BeyondForecastAdj)      # 仅当 h > 逐日预报覆盖天数
```

- **季节性**：按月份锚点、以「月中心日」线性插值，避免跨月阶跃。反映香葱春节前高峰、夏季低谷、冬季回升的年内规律。
- **天气冲击**：逐日累加，强降水（≥10mm）+1.5%/天、大风（≥17m/s）+1%/天、气温距平 −1.2%/℃（偏高加速生长→供给增→压制价格）。总体限幅 [−5%, +8%]。
- **动量**：向实测均线回归，回归强度随预测期递增（至 20 天达上限）。
- **超期修正**：超出 16 天逐日预报的部分，叠加厄尔尼诺背景下 11 月云南降水偏多 10%–20% 的气候态预期。

## 四、本地运行

```bash
cd xiangcong-monitor
python run.py              # 生成当日报告到 outputs/
python run.py --dry-run    # 仅打印关键结果，不落盘
```

仅依赖 Python 标准库，Python 3.9+ 即可。

## 五、部署到 GitHub

### 1. 添加 SSH 公钥

本机密钥位于 `C:\ssh-keys\`（纯英文路径，规避中文用户名导致的编码问题）：

- 公钥：`C:\ssh-keys\github_id_ed25519.pub`
- 私钥：`C:\ssh-keys\github_id_ed25519`

复制公钥全文，粘贴到 https://github.com/settings/ssh/new ，
Title 填 `香葱预测 / xiangcong-yuce`，**Key type 保持 Authentication Key**，保存。

验证连通性：

```bash
ssh -T -i C:/ssh-keys/github_id_ed25519 git@github.com
# 出现 "Hi <用户名>! You've successfully authenticated" 即成功
```

### 2. 创建仓库并推送

在 GitHub 网页新建一个**空仓库**：

- **Repository name**：`xiangcong-yuce`
- **Description（建议填）**：`香葱预测 · 每日 08:00 自动抓取天气与灾害数据，回顾 10 年行情并预测未来 3 天至 3 个月香葱价格`
- **不要**勾选 README / .gitignore / License

然后双击运行 `C:\ssh-keys\push-github.bat`，按提示输入 GitHub 用户名即可完成推送。

也可手动执行：

```bash
cd xiangcong-monitor
git init
git add .
git commit -m "feat: 香葱预测自动化监测系统"
git branch -M main
git remote add origin git@github.com/<你的用户名>/xiangcong-yuce.git
git push -u origin main
```

> 若使用 HTTPS 方式推送，密码处需填 **Personal Access Token**，而非账户登录密码。
> 新版 GitHub 界面入口：Settings → Developer settings → Personal access tokens →
> **Tokens (classic)** → Generate new token，勾选 `repo` 与 `workflow` 权限。

### 2. 启用定时执行

推送后，进入仓库 **Settings → Actions → General**，确认
*Workflow permissions* 为 **Read and write permissions**。
`.github/workflows/daily-report.yml` 中的 `cron: '0 0 * * *'` 即**北京时间每日 08:00**。

> **关于准点**：GitHub Actions 的 `schedule` 在整点负载最高，实际触发常延迟 5–30 分钟，
> 偶尔被跳过，属平台已知行为。若希望更贴近 8:00，可把 cron 改为错峰值
> （如 `'55 23 * * *'` = 北京 07:55，提前进入队列）。
> 如需严格准点，改用外部 cron（云服务器 / 云函数）调用 `workflow_dispatch`。

### 3.（可选）启用 GitHub Pages

进入 **Settings → Pages → Build and deployment → Source**，选择 **GitHub Actions**。
此后每次运行会自动发布，`outputs/index.html` 为归档首页。

## 六、多任务行情汇总（data/sources/）

除本仓库流水线外，其余香葱行情定时任务（Gemini / ChatGPT / 全国监测 / grok / 香葱行情）
每日 00:00 采集后，按统一 schema 把**全部**报价写入
`data/sources/<slug>_YYYY-MM-DD.json`，由推送任务在 03:00 汇总进日报第九章
「多源行情汇总 · 全部定时任务」，全量展示、不截断。

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

口径约定：价格统一换算为 **元/公斤**；`price_type` 必须标注
（产地地头价 / 产地收购价 / 产地批发价 / 销地批发价 / 零售价）；估算值在 `note` 注明。
汇总窗口默认 3 天（防止单任务漏跑），损坏文件自动跳过、不影响主流程。

## 七、维护要点

- **更新实测价格**：编辑 `data/price_history.json`，新增
  `{"date": "YYYY-MM-DD", "variety": "红香葱", "market": "云南产地", "price": x.xx,
   "source": "observed", "note": "来源说明"}`，模型会自动以其为基准。
- **调整模型参数**：`src/config.py` 中的 `MODEL`（季节性因子、天气冲击系数、动量强度）。
- **增删观测点**：`src/config.py` 的 `OBSERVATION_POINTS`（含经纬度与产区/销区属性）。
- **历史价格会自我累积**：每日运行会写入 `model` 点用于回测，但均线与最新价只取
  `observed` 点，避免估算值自我强化。

---

数据仅供参考，不构成采销、囤货或投资建议。
