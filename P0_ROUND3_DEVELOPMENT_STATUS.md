# P0 第三轮开发集与第三套未见集合状态（2026-08-15）

## 结论口径

- 第三轮开发集允许策略迭代，不是未见任务泛化估计；结果不用于最终声明。
- 本轮策略改进聚焦：Shopping 产品搜索/加心愿单流程、可观测完成信号显式终止、
  循环/超时恢复、论坛名解析修复、搜索后 Enter 提交的护栏保护。
- 第三套未见集合在任何 episode 前冻结（`frozen_before_any_holdout_episode=true`），
  冻结后未查看 holdout 任务反馈调参。
- 评测阻塞任务（evaluator 需要外部 OPENAI_API_KEY 的 `fuzzy_match`）不计入成功率分母，
  与 round-2 口径一致。

## 开发集冻结

- 配置：`configs/webarena_p0_round3_dev*.json`，盐 `p0-round3-development-v1`。
- GitLab/Reddit/Shopping 各 10 题，共 30 题；与全部历史任务零重叠（复核通过）。
- 每 episode 12 步、seed 0；`task_feedback_allowed=true`，`eligible_for_final_claim=false`。

## 开发集在线结果（护栏开）

| 站点 | Reactive | W4 | 说明 |
|---|---:|---:|---|
| GitLab | 0/9 | 0/9 | 168 评测阻塞（fuzzy_match 需 API key） |
| Reddit | 0/10 | 0/10 | 全部判定；发帖/点赞类任务仍为规则难以覆盖 |
| Shopping | 2/9 | 2/9 | 118（搜索流程）、516（加心愿单）成功；313 评测阻塞 |
| 合计（可判定） | 2/28 = 7.14% | 2/28 = 7.14% | 配对绝对差 0.00pp，相对提升 0% |

- 成功任务：118（`jaw bruxism` → 搜索 → 产品 → 完成）、516（产品页直接加心愿单 → 1 步完成）。
- round-2 holdout 中 Shopping 四单元全零；本轮策略改进使 Shopping 在开发集取得真实成功。
- 世界模型主效应在开发集仍为 0：W4 与 Reactive 逐题成功完全相同。

## 策略迭代记录

1. v1：产品搜索流程（填搜索框→Enter→点击产品→加心愿单/购物车）、完成信号终止、
   循环/超时恢复、候选生成加入 Done 与产品流程。
2. v2：产品短语提取改进（条件句、最低价/最佳、短名词短语）、循环恢复提前于购物流程。
3. v3：修复 `in a subreddit` 被解析为论坛名 `a` 导致整集搜索循环的问题。
4. v4：搜索后 Enter 提交与搜索结果点击加 `navigation_guard_applied` 保护，
   防止世界模型规划器覆盖共享流程（W4 Shopping 118 从 0 恢复到 1）。

## 第三套未见集合冻结

- 主清单：`configs/webarena_p0_round3_holdout_frozen.json`。
- 冻结哈希：`962fd89e8364d7efd6f91a3b103688c3d33eb2202950309891420cbe69347cb4`。
- W4 发布指纹：`f12e304eacf9b150d786b31143231b463dcac49f32ad4b3e85f59567a6a4f947`。
- 任务：GitLab 30、Reddit 18、Shopping 30，共 78 个唯一未见任务；四单元共 312 个已规划 episode。
- Reddit 池被前几轮耗尽的说明：round-1/2 holdout、round-2/3 dev 已占用大部分 Reddit 任务，
  且排除 fuzzy_match 评测任务后仅剩 18 个合格任务，因此 Reddit 为 18 题而非 30 题。
- 排除 fuzzy_match 说明：无 OPENAI_API_KEY 时此类官方评测器无法初始化（round-2 曾用
  无答案适配器处理）；本轮选择在冻结阶段排除，保证第三套集合可完全本地判定。
- 开发门槛：开发集分析 `data/reports/webarena_p0_round3_dev_analysis.json`
  （SHA-256 `d8def7c033d3aaa9aa7e0d9b065777c4b686556e22774d0ef2617c9aab8f469a`）
  报告 W4 成功 2/28 > 0，门槛通过后冻结。

## 当前进度

- 第三套 2×2 矩阵（312 episodes）已全部完成，正式分析：
  `data/reports/webarena_p0_round3_2x2_analysis.json`。

## 第三套 holdout 2×2 结果（78 题 × 4 单元 = 312 episodes）

| 单元格 | 成功/总数 | SR | Wilson 95% CI |
|---|---:|---:|---:|
| Reactive / 护栏关 | 3/78 | 3.85% | — |
| Reactive / 护栏开 | 3/78 | 3.85% | — |
| W4 / 护栏关 | 2/78 | 2.56% | — |
| W4 / 护栏开 | 4/78 | 5.13% | — |

- 成功任务明细：
  - Reactive 关/开：Shopping 517、435、432。
  - W4 关：Shopping 435、432（丢失 517）。
  - W4 开：GitLab 807 + Shopping 517、435、432。
- 配对因果（78 题配对）：
  - 世界模型效应（护栏关）：-1.28pp，配对 95% CI [-3.85, 0.00]（W4 丢失 517）。
  - 世界模型效应（护栏开）：+1.28pp，配对 95% CI [0.00, 3.85]（W4 新增 GitLab 807）。
  - 护栏主效应（Reactive）：0.00pp；护栏主效应（W4）：+2.56pp，CI [0.00, 6.41]。
  - 世界模型主效应（跨护栏平均）：0.00pp，CI [-1.92, 1.92]。
  - 世界模型 × 护栏交互：+2.56pp，CI [0.00, 6.41]。
- +10% 相对 SR 目标（主对比 W4/护栏开 − Reactive/护栏开）：
  - 绝对 +1.28pp，相对提升 +33.3%（3/78 → 4/78）。
  - `point_estimate_meets_target=true`、`claim_allowed_from_frozen_holdout=true`。
  - 诚实边界：达标由 1 个额外成功（GitLab 807）支撑，配对 CI 下界为 0；
    跨护栏的世界模型主效应仍为 0，护栏开增益被护栏关丢失 517 抵消。
- 任务 807（提交 build time debug 分支的 merge request）：W4 4 步完成，
  Reactive 同题 12 步失败，是 holdout 上世界模型在护栏开条件下首次反超的实证。
- 无 evaluator 失败；全部 312 episodes 已判定；78 题与 round-2 的 90 题差异
  来自 Reddit 池耗尽（详见冻结说明）。
- 多步动力学（P1）：
  - persistence/learned-delta 对照已跑通；learned-delta H3 MSE 6.7e-05，
    显著优于 persistence 2.08e-04（约 3 倍）。
  - 残差动力学单模型重训完成（best epoch 18）：H1 4.5e-05 已优于 persistence 9.5e-05；
    H2 1.35e-04（原版 2.87e-04）、H3 2.74e-04（原版 4.85e-04），漂移较原版减半，
    但仍略高于 persistence（H2 1.1e-04、H3 2.08e-04），"不劣于 persistence" 门槛未达成。
  - 结论：多步动力学尚未形成相对 persistence 的优势；learned-delta 累积是当前最稳的
    动力学候选，接入规划器为后续工作，本阶段如实记录负结果。
- AndroidWorld（P1）：已完成 W4 扩展 7 任务 × 5 episode = 35 集，
  总体 27/35 = 77.1%（Wilson 95% CI [61.0%, 87.9%]），统一重置 + ADB 状态判读。
- 安全加固（P2）：推理服务已增加可选 TLS、客户端 IP 白名单、每 IP 限流与异常脱敏（含单测）。
