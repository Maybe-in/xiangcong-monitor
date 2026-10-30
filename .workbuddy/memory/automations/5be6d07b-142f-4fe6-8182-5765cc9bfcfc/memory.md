# 香葱行情日报定时任务执行记录

## 2026-10-26 03:56（北京时间）执行
- 流水线 `python run.py` 成功，生成 `outputs/香葱行情日报_2026-10-26.html`。
- 数据：天气(泸西县16天预报/15观测点)、灾害预警100条、新发地接口17条(最新2026-10-25)、红香葱六档中枢 4.49/4.67/5.04/5.23/5.37/5.47。
- 提交并推送：commit `a66bf9b`，`git pull -X ours` 已 up to date，`git push origin main` 成功（ded7433..a66bf9b）。
- 未触发 rebase/冲突分支（远端未被 CI 抢先推送）。

## 2026-10-27 06:57（北京时间）执行
- 流水线 `python run.py` 成功，生成 `outputs/香葱行情日报_2026-10-27.html`。
- 数据：天气(泸西县16天预报/15观测点)、灾害预警100条、新发地接口41条(最新2026-10-26)、红香葱六档中枢 3.85→4.03/4.22/4.56/4.76/4.90/4.98；data/sources 接入5任务/283报价/72预测(扫描10文件)。
- 提交 `f916e7e`；`git pull` 因分支分叉失败→改用 `git fetch && git rebase origin/main`；冲突涉及 outputs/*.html、outputs/*.json、data/market_quotes.json，按策略用 `git checkout --theirs`(rebase 中即本地新生成版本)解决，rebase 完成后 `git push origin main` 成功（2fbbf5a..f916e7e）。

## 2026-10-28 09:39（北京时间）执行
- 流水线 `python run.py` 成功，生成 `outputs/香葱行情日报_2026-10-28.html`。
- 数据：天气(泸西县16天预报/15观测点)、灾害预警100条、新发地接口41条(最新2026-10-27)、红香葱六档中枢 3.85→4.04/4.26/4.56/4.75/4.90/4.96；data/sources 接入5任务/235报价/42预测(扫描15文件)。
- 提交 `234c00b`；`git pull -X ours` 因分支分叉报错→改用 `git fetch && git rebase origin/main`；冲突涉及 outputs/tasks/*.html、outputs/香葱行情日报_2026-10-28.html、outputs/*.json、data/market_quotes.json、data/price_history.json，按策略用 `git checkout --theirs`(rebase 中即本地新生成版本)解决，rebase 完成后 `git push origin main` 成功（c9b9959..234c00b）。

## 2026-10-29 03:58（北京时间）执行
- 流水线 `python run.py` 成功，生成 `outputs/香葱行情日报_2026-10-29.html`。
- 数据：天气(泸西县16天预报/15观测点)、灾害预警100条、新发地接口41条(最新2026-10-28)、红香葱六档中枢 3.85→3.99/4.18/4.56/4.74/4.90/4.94；data/sources 接入5任务/319报价/36预测(扫描20文件)。
- 提交 `6d3729b`；`git pull -X ours` 因分支分叉报错→改用 `git fetch && git rebase origin/main`；13 个文件冲突，按策略用 `git checkout --theirs` 逐个解决（rebase 中 theirs=本地新生成版本），`git add -A` 后 `git -c core.editor=true rebase --continue`（非交互环境需绕过编辑器），`git push origin main` 成功（352be41..5dc2d51）。
- 经验：非交互 shell 下 `git rebase --continue` 会因 EDITOR 未设置失败，需加 `-c core.editor=true`；中文文件名在 `git status` 中以八进制转义显示，grep 匹配字面中文会失败。

## 2026-10-30 03:34（北京时间）执行
- 流水线成功，生成 `outputs/香葱行情日报_2026-10-30.html`；新发地 41 条（最新 10-29）、灾害预警 100 条、天气 16 天；红香葱六档中枢 3.85→3.94/4.19/4.52/4.68/4.84/4.87；data/sources 5 任务/314 报价/36 预测（25 文件）。
- 提交 `4b7f50d`；远端 CI 有 3 个抢先提交 → `git pull --no-rebase -X ours` → 推送 `ebad5a5`（f24594c..ebad5a5）。
- 网络：SSH 22 端口超时、HTTPS 代理对 github.com 返回 502；改用 SSH 443 备用主机 `ssh://git@ssh.github.com:443/` 成功。已在仓库加 `url.<443>.insteadOf git@github.com:`，后续 `git push origin main` 自动走 443。
