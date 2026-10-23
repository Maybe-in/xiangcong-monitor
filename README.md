# 香葱行情日报 · 自动化监测系统

每日自动采集**全国天气**与**自然灾害预警**数据，分析并预测**未来 3 天 / 1 周 / 半月 / 1 月**的香葱行情，统计市面常见香葱种类与全国种植省份分布，并**重点跟踪云南泸西县**（全国最大香葱单品生产基地）。

由 GitHub Actions 在**北京时间每日凌晨 3 点**定时执行，自动生成单页 HTML 报告并提交回仓库，可一键发布为 GitHub Pages 站点。

---

## 一、目录结构

```
xiangcong-monitor/
├── .github/workflows/daily-report.yml   # 定时任务（UTC 19:00 = 北京 03:00）
├── run.py                               # 主入口：编排采集 → 预测 → 渲染
├── src/
│   ├── config.py                        # 产区、观测点、品种、模型参数
│   ├── weather.py                       # 天气采集（Open-Meteo）
│   ├── disaster.py                      # 灾害预警（中央气象台）
│   ├── price.py                         # 价格历史 + 四档预测模型
│   └── report.py                        # HTML 报告渲染（含 SVG 走势图）
├── data/
│   └── price_history.json               # 价格历史（observed 实测 / model 估算）
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

### 1. 创建仓库并推送

```bash
cd xiangcong-monitor
git init
git add .
git commit -m "feat: 香葱行情日报自动化监测系统"
git branch -M main
git remote add origin https://github.com/<你的用户名>/xiangcong-monitor.git
git push -u origin main
```

推送时若提示输入密码，请使用 **Personal Access Token**（Settings → Developer settings →
Personal access tokens → Tokens (classic)，勾选 `repo` 权限），而非账户登录密码。

### 2. 启用定时执行

推送后，进入仓库 **Settings → Actions → General**，确认
*Workflow permissions* 为 **Read and write permissions**。
`.github/workflows/daily-report.yml` 中的 `cron: '0 19 * * *'` 即北京时间每日 03:00。

> 提示：GitHub Actions 的定时任务在仓库长期无活动或负载较高时可能延迟数分钟甚至被跳过，
> 属平台已知行为；如需严格准时，可改用外部 cron（如云服务器、云函数）触发
> `workflow_dispatch`。

### 3.（可选）启用 GitHub Pages

进入 **Settings → Pages → Build and deployment → Source**，选择 **GitHub Actions**。
此后每次运行会自动发布，`outputs/index.html` 为归档首页。

## 六、维护要点

- **更新实测价格**：编辑 `data/price_history.json`，新增
  `{"date": "YYYY-MM-DD", "variety": "红香葱", "market": "云南产地", "price": x.xx,
   "source": "observed", "note": "来源说明"}`，模型会自动以其为基准。
- **调整模型参数**：`src/config.py` 中的 `MODEL`（季节性因子、天气冲击系数、动量强度）。
- **增删观测点**：`src/config.py` 的 `OBSERVATION_POINTS`（含经纬度与产区/销区属性）。
- **历史价格会自我累积**：每日运行会写入 `model` 点用于回测，但均线与最新价只取
  `observed` 点，避免估算值自我强化。

---

数据仅供参考，不构成采销、囤货或投资建议。
