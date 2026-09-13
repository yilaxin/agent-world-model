# W1 基线策略攻坚：阶段目标与验收

**负责人**：卢政坤（20 小时/周）｜**周期**：2026-09-12 – 2026-11-10（阶段二收口）
**配套工具**：`scripts/attribute_webarena_failures.py`、`WEBARENA_FAILURE_ATTRIBUTION.md`、`WEBARENA_DEV_FAILURE_ATTRIBUTION.md`
**存放位置**：本文件随代码仓库版本管理；总体计划见工作区根的《实施计划_2026-09-12_阶段二至结题.md》。

---

## 一、为什么门禁必须比"12%"更严

Round-4 的结果是严格零效应：W4 − Reactive = 0.00 个百分点，95% CI [0.00, 0.00]，240 个配对单元上一个 episode 的成败都没变。连续三轮零主效应说明问题不在重排，而在**基线能力本身**。但在动手之前，必须先确认"提升 10%"这件事在这个实验设计下是否可测。

按配对二项（精确 McNemar，双侧 α=0.05，80% 功效）计算，要声称 **+10% 相对提升** 所需的配对单元数：

| 基线成功率 | 绝对提升 | 需要配对单元（损失比 0.3） | 需要配对单元（损失比 0.5） |
|---:|---:|---:|---:|
| 5.0% | 0.5pp | 3140 | 4980 |
| 7.6%（Round-4 实测） | 0.8pp | 2070 | 3280 |
| 12% | 1.2pp | 1310 | 2080 |
| 20% | 2.0pp | 790 | 1250 |
| 30% | 3.0pp | 530 | 830 |
| 40% | 4.0pp | 400 | 630 |
| 50% | 5.0pp | 320 | 500 |

当前 Round-4 只有 240 个配对单元。**结论：即使基线做到 50%，+10% 相对提升依然测不出来。** 所以"把基线抬到 12%"并不足够，必须同时解决三件事：

1. 把基线抬到 30% 以上（此时 10% 相对提升 = 3pp，落在可测区间边缘）；
2. 把最终验收的配对单元数从 240 提到 ≥ 540（建议 600）；
3. 如果最终效应小于 +10% 相对，就如实报告绝对百分点与置信区间，**不声称达标**。

### 另一个必须正视的问题：dev 不能代表 holdout

| 数据集 | 现状（reactive） |
|---|---|
| Round-3 dev（v7，seed 0，28 题） | GitLab 0/9、Reddit 1/10、Shopping 4/9 = **17.9%** |
| W1 工作集（40 题 × 3 seed，2026-09-12 实测） | GitLab 0/69、Shopping 3/51 = **2.5%** |
| Round-4 冻结 holdout（240 episodes/策略） | GitLab 0–2/120、Shopping 9/120 = **4.2%** |

Shopping 上 dev 44% 对 holdout 7.5%，差了近 6 倍；工作集实测 2.5% 更接近 holdout 量级。**只盯 dev 会被系统性误导**，所以"用 dev 冒烟、用工作集判、用 holdout 声称"这条三层纪律必须写成硬规则。

### W1 基线归因（2026-09-12，工作集 120 条）

| 主类型 | 条数 | 占比（117 条失败） |
|---|---:|---:|
| 循环/停滞 | 42 | 36% |
| 预算耗尽 | 38 | 33% |
| 流程路径错误 | 23 | 20% |
| 目标理解偏差 | 6 | 5% |
| 缺显式终止 | 3 | 3% |
| 表单/搜索流程不完整 | 3 | 3% |
| 动作执行失败 | 2 | 2% |
| 成功 | 3 | — |

完整证据：`WEBARENA_W1_BASELINE_ATTRIBUTION.md`、`data/reports/webarena_w1_baseline_attribution.json`。
每次改动后以这份 JSON 为 `--baseline` 运行差分工具，目标类型必须下降 ≥ 40%。

---

## 二、门禁（修订版）

| 编号 | 时机 | 内容 | 不通过怎么办 |
|---|---|---|---|
| **G-W1-1 冒烟** | 每次改动后（≤1 h） | dev 28 题（seed 0）配对比较：成功率不低于上一版，且归因主类型条数不上升 | 直接回退该改动 |
| **G-W1-2 周检** | 每周一次（3–5 h，可过夜） | W1 工作集 3 站 × 24 题 × 3 seed = 216 episodes，与上一版配对比较，bootstrap CI 下界 > 0 | 停一周做归因，不加新模块 |
| **G-W1-3 阶段预检** | 11-10 前 | dev/W1 工作集 reactive ≥ 30%，且 `loop_stall` 占比 < 15% | 延后 holdout 冒险，只报告进展 |
| **G-W1-4 冻结验收** | 阶段二收口 | 新建 Round-5 冻结 holdout：2 站 × 60 题 × 5 seed = **600 配对单元**，reactive ≥ 30%，评测器异常 0 | 不启动 W4 对比，不写"提升"结论 |
| **G-W1-5 对比** | G-W1-4 通过后 | 在 Round-5 上跑 W4（含护栏两态），按配对 CI 判定是否达标 | 若 CI 下界 ≤ 0，按负结果如实报告 |

**为什么是 600 单元**：30% 基线、+10% 相对提升时，损失比 0.3–0.5 需要 530–830 个配对单元；600 是可执行设计里最接近的选择（2 站 × 60 题 × 5 seed）。若最终只做到 20% 基线，则把对外声称的效应量改为"相对 +20%"（400–630 单元区间内可测），并在报告中说明口径调整。

**Round-5 的任务池规则**：只能从未被 Round-1/2/3/4 冻结过的任务中抽取，抽完即冻结（记录 selection salt 与 SHA-256），抽出后看一眼就作废并重抽。

---

## 三、分模块目标（按归因工作量排序）

归因基线：全量 1508 条失败中，循环 408、流程路径 353、预算耗尽 299、候选缺失 227；dev v7 的 23 条失败中，循环 12、预算 6、流程路径 4、目标理解 1。

| 里程碑 | 模块 | dev 基线 | 目标 | 判定信号 |
|---|---|---|---|---|
| **M1** | 循环恢复 | 12/28 | ≤ 4（dev） | `repeated_actions` 信号条数；同一 (action,target) 连续重复 |
| **M2** | 站点流程知识 | 4/28 | ≤ 1（dev） | `wrong_route`：从未到达目标流程页面；`no_typing` 占比 |
| **M3** | 候选优先级与预算 | 6/28 | ≤ 2（dev） | `budget_exhausted`：12 步内无提交；唯一 URL 数 |
| **M4** | 候选生成 | dev 为 0，holdout 227 | holdout 上不上升 | `candidate_missing`：候选与子目标意图不兼容 |

**M1 的具体证据**：循环类失败中 98% 有重复动作，但只有 2% 同时具备候选语义失配。也就是说循环不是"选错了"，是"点下去没反应还在点"。优先做：动作后状态指纹比对（state_id 未变化即视为无效动作）、同一目标重复点击熔断、无效动作计数触发的重新观察。

**M2 的具体证据**：GitLab 失败轨迹最常点击 `Merge requests`(112)、`Help`(102)、`D`(90)、`Commits`(53)、`To-Do List`(49)，全在全局导航栏和帮助页；55% 的流程类失败整条轨迹没执行过任何 `fill`/`type`。优先做：任务措辞 → 目标流程页的直接路由（建项目/建 issue/评论/加成员/查提交），以及进入流程后优先执行输入而非继续点击。

---

## 四、每周 20 小时怎么分配

| 时段 | 内容 | 工时 |
|---|---|---|
| 周一–周二 | 单模块实现（一次只动一个模块） | 8 h |
| 周三 | 冒烟 G-W1-1 + 归因刷新（等待时间可并行读轨迹） | 3 h |
| 周四–周五 | 按归因结果修，必要时提交周检跑批 | 6 h |
| 周六 | 周检 G-W1-2 + 记录 `P0_W1_PROGRESS.md` | 3 h |

**成本提示**：reactive 模式的评测**不需要 GPU、不需要推理服务**（`evaluate_webarena_online.py` 只在 `world-model` 模式下才构造远端 agent）。整个 W1 迭代可以零 GPU 成本运行；只有 G-W1-4/G-W1-5 需要开 AutoDL。

---

## 五、每次迭代的固定闭环

```bash
# 1) 起站点容器（GitLab 8023 / Shopping 7770），只跑 reactive
bash scripts/run_webarena_round3_dev_reactive.sh          # 约 30-45 分钟

# 2) 刷新 dev 归因（28 条，秒级）
python3 scripts/attribute_webarena_failures.py \
  --report-dir data/reports \
  --report-glob 'webarena_r3dev_v7_*.json' \
  --include-prefix webarena_ \
  --output-json data/reports/webarena_dev_failure_attribution.json \
  --output-markdown WEBARENA_DEV_FAILURE_ATTRIBUTION.md \
  --output-html WEBARENA_DEV_FAILURE_ATTRIBUTION.html

# 3) 与上一版做配对差分（这一步出 PASS/FAIL 结论）
python3 scripts/diff_failure_attribution.py \
  --baseline data/reports/webarena_dev_failure_attribution.json \
  --candidate data/reports/webarena_dev_failure_attribution_v8.json \
  --target loop_stall \
  --output-markdown W1_DIFF_latest.md \
  --output-json data/reports/webarena_dev_diff_latest.json
```

差分工具按 `(site, mode, guard, task_id, seed)` 做配对，输出迁移矩阵（fixed / regressed / recategorised / unchanged）、各类型条数变化、以及门禁判定，不参与配对的 episode 会单独计数，避免任务集变化把结果做花。

注意：新一版的报告要另存为 `webarena_r3dev_v8_*.json` 形式并同步进 `--report-glob`，否则会与 v7 混在一起；上一版的归因 JSON 要保留一份作为 `--baseline`。输出参数必须用 `/mnt/c/...` 的 POSIX 路径。

---

## 六、每个模块的完成定义（DoD）

1. 代码改动 + 对应单测通过（`pytest tests/ -q`）。
2. `diff_failure_attribution.py` 判定 **PASS**，即同时满足：
   - 目标类型条数下降 ≥ 40%；
   - 其他类型涨幅 ≤ 10%，且 baseline 为 0 的新类型不得新增超过 1 条；
   - 配对成功数不下降；
   - 没有 `evaluator_environment` 失败。
3. 回退样本（`regressed_examples`）逐条确认：是环境抖动还是真实回退；真实回退必须修掉。
4. `P0_W1_PROGRESS.md` 追加一条记录：日期、模块、改动摘要、政策指纹、差分报告结论与关键数字。

---

## 七、风险与对策

| 风险 | 对策 |
|---|---|
| dev 只有 28 条，噪声大 | 冒烟只看方向，周检用 216 条配对；任何结论都要求 CI 下界 > 0 |
| 反复调 dev 导致过拟合 | dev 与 holdout 完全隔离；Round-5 冻结后只测一次；抽任务时记录 salt |
| 循环恢复掩盖真实探索需求 | 用"唯一 URL 数"和"子目标推进"作为护栏指标，不只看重复动作条数 |
| 到 11-10 仍不足 30% 基线 | 阶段二报告如实写明"能力提升进展 + 未达可声称阈值"，把达标推到阶段三 |
| 站点容器不稳定造成假失败 | 归因里 `evaluator_environment` 类必须为 0，否则该轮重跑 |

---

## 七之二、任务池审计（2026-09-12 实测）

按 `scripts/prepare_webarena_p0_round3_holdout.py` 的资格规则（`sites == [site]`、评测器非 `fuzzy_match`、且从未在任何一轮记录中出现）清点 812 条任务源：

| 站点 | 该站任务 | 其中 fuzzy | 已被历轮使用 | **剩余可用** |
|---|---:|---:|---:|---:|
| GitLab | 180 | 8 | 153 | **23** |
| Shopping | 187 | 34 | 153 | **17** |
| Reddit | 106 | 2 | 106 | **0** |

**结论一**：原计划的"3 站 × 24 题"工作集不可行——Reddit 池已彻底耗尽，GitLab+Shopping 合计只剩 40 题。

**结论二**：Round-5 原设计的"2 站 × 60 题 × 5 seed = 600 配对单元"同样不可行，可用未见过任务最多支撑 40 题。

**可选的替代设计**：把历轮**冻结 holdout** 任务（Round-2/3/4，剔除 fuzzy）作为预先登记的确认集整体复用，规则固定、不做挑选：

| 集合 | 非 fuzzy 任务 | 3 seed 配对单元 | 5 seed 配对单元 |
|---|---:|---:|---:|
| GitLab | 98 | 294 | 490 |
| Shopping | 91 | 273 | 455 |
| GitLab + Shopping | 189 | **567** | 945 |
| 含 Reddit | 236 | 708 | 1180 |

567 个配对单元落在"+10% 相对提升、30% 基线"所需的 530–830 区间内。代价是这些任务在早期轮次被评测过（策略已换代，配对比较仍成立），因此**必须在报告中披露"复用已冻结 holdout 集合"这一设计，并把"仅未见过任务"的结果作为次要指标同时报告**。

---

## 八、分工

| 事项 | 负责 |
|---|---|
| 模块实现与 dev 调参 | 卢政坤 |
| 评测编排、归因刷新、报告对比、PR 流转 | Codex（按需触发） |
| 冻结 holdout 生成与 SHA-256 记录 | Codex 执行、卢政坤确认抽签 salt |
| 论文与结题材料 | 暂缓（用户决定） |
