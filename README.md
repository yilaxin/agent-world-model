# Agent 世界模型决策优化

本仓库实现《大创申报书 33.0》的阶段一至阶段四。当前交付包含动作条件世界模型、候选动作前瞻决策、反馈困难样本池、离线重训练、主实验/消融、真实三站 WebArena 回归和少量 AndroidWorld 迁移。离线训练环境为 AutoDL RTX 4090、PyTorch 2.1.2+cu121、CUDA 12.1；在线站点与浏览器评测在本机 WSL/Docker CPU 环境运行。

## 最终完成状态

- 数据集：13,348 条状态转移、5,930 个 episode、30 个任务，按 episode 切分为 9,388 / 2,017 / 1,943，无 episode 泄漏。
- 观察反事实：3,600 对全部有效，其中 3,050 对有信息，采集失败为 0，状态匹配率 100%。
- 阶段二：完成五次多种子 GPU 训练，验证集选择三个成员；独立测试状态变化 F1 98.69%、任务信号 F1 98.90%、风险 F1 94.39%、风险 AUROC 99.04%，12 项门禁全部通过。
- 阶段三反事实：测试集 477 个观察配对，其中 396 个有效配对；最佳单模型与集成 Pairwise Accuracy 均为 97.73%，集成平均决策遗憾从 0.0638 降到 0.0511。
- 阶段三多步：独立测试 H2=619、H3=329，长视野终止=94、严重失败=47，全部覆盖门禁通过。
- 阶段四反馈：困难样本池 9,388 条，完成预测误差、regret、rank flip、stall 与结构错误反馈；8 个主实验/消融变体完成离线重训练与验证集选型。
- W4 独立测试：MSE 0.002466、pairwise accuracy 97.47%、regret 0.05619、risk F1 94.20%、ECE 0.00896；W3/W4 来源权重各占 50%，成员权重经验证集校准。
- 多步动力学（第三轮）：direct-residual 状态/动作头 H2 MSE 5.52e-05、H3 MSE 7.97e-05，优于 persistence（H2 1.10e-04、H3 2.08e-04），2,891 个连续窗口及终止/严重失败覆盖门禁全部通过；接入在线规划器前仍需独立 WebArena 开发集回归。
- WebArena P0 未见任务（三轮）：Round-1 冻结 90 题 × 4 单元（360 episodes）四单元均 0/90；Round-2 90 题 × 4 单元 W4−Reactive 为 0.00pp；Round-3 冻结 78 题 × 4 单元（312 episodes），Reactive 3/78（3.85%）、W4+护栏 4/78（5.13%），主对比相对 +33.3%（点估计达到申报书 +10% 目标，配对 CI 下界为 0，跨护栏世界模型主效应仍为 0）。早期三站 9 题 9/9 仍只作 post-fix 回归历史对照。
- WebArena P0 第四轮（2026-09-12 完成）：GitLab/Shopping 各 40 个冻结未见任务 × 3 seed × 4 单元 = 960 episodes，评测器异常 0 条。两站两护栏下 W4 与 Reactive 的成功率完全一致（护栏关 0/120 vs 0/120、9/120 vs 9/120；护栏开 2/120 vs 2/120、9/120 vs 9/120），**配对提升 0.00 个百分点，95% CI [0.00, 0.00]**（240 个配对单元），护栏效应 +0.83pp（CI [0.00, +0.83]）。世界模型重排改变了执行动作，但未改变任何一个 episode 的成败——主效应连续第三轮为 0，验收目标仍未达成。详见 [P0_ROUND4_STATUS.md](P0_ROUND4_STATUS.md)。
- AndroidWorld 迁移（第三轮）：W4 在 7 个任务 × 5 episode = 35 集上完成 27/35（77.1%，Wilson 95% CI [61.0%, 87.9%]），动作执行率 100%；仍属少量迁移检查。
- 安全：Codex Security 完成 53 个运行时文件复核；4 个中危候选全部修复（checkpoint 安全加载、非回环 token/TLS 强制、CSV 公式中和、单动作解析），相关测试 31 项通过。

完整结果：

- [阶段二、阶段三多次训练完善报告](PHASE23_MULTIRUN_COMPLETION_REPORT.md)
- [阶段四反馈优化与实验报告](PHASE4_COMPLETION_REPORT.md)
- [WebArena P0 未见任务 2×2 验收报告](P0_WEBARENA_COMPLETION_REPORT.md)
- [WebArena P0 验收 PDF](output/pdf/WebArena_P0未见任务2x2验收报告_2026-08-14.pdf)
- [第三轮补充报告 PDF](output/pdf/大创第三轮补充报告_2026-08-16.pdf)
- [项目完整总结与结题评估 PDF](output/pdf/大创项目完整总结与结题评估_2026-08-15.pdf)
- [WebArena 失败归因（动作级，W1 基线策略工作的输入）](WEBARENA_FAILURE_ATTRIBUTION.md)
- [WebArena P0 第四轮验收状态](P0_ROUND4_STATUS.md)
- `data/reports/phase4_feedback_experiment_gpu.json`
- `data/reports/webarena_online_evaluation_w4.json`
- `data/reports/webarena_p0_round3_2x2_analysis.json`
- `data/reports/phase3_multistep_direct_residual_round3_gpu.json`
- `output/pdf/阶段二阶段三最终进度与遗留问题报告_2026-08-10.pdf`
- 私有看板：`agent-world-model-phase23-lzk.zhengkunlu4.chatgpt.site`

## 关键目录

```text
agent_world_model/                 核心编码器、世界模型、集成、结构对齐与规划器
artifacts/phase2/                  世界模型检查点与集成清单（完整模型在 GPU 服务器）
artifacts/phase3/                  结构对齐检查点
configs/                           数据、训练与评测配置
data/phase2_p2/                    最终数据卡
data/reports/                      最终机器可读 JSON 证据（含原始单站报告及其 SHA-256）
data/trajectories_webarena_formal_evidence/  18 条正式 WebArena 逐步轨迹
data/trajectories_webarena_p0_evidence/      P0 最终分析白名单引用的 360 条逐步轨迹
scripts/                           数据、训练、评测、在线服务和报告脚本
site/                              Sites 私有结果看板
tests/                             单元测试
```

最终 PDF 可由 `scripts/build_final_project_summary_pdf.py` 从本地 JSON 证据重新生成。

GPU 服务器工作目录：

```text
/root/autodl-tmp/agent_world_model_phase23_latest
```

## 统一复现

在安装 BrowserGym、Playwright、PyTorch 与 CUDA 的 GPU 环境中执行：

```bash
set -a
source .env
set +a
bash scripts/run_phase23_improvement.sh
```

脚本依次执行采集、质量门禁、五次多种子训练、三成员集成、阶段二独立测试、阶段三反事实排序与真实连续轨迹 H=1/2/3 评估。阶段四离线反馈实验使用 `scripts/run_phase4_feedback.py`；WebArena 真实三站运行使用 `scripts/run_webarena_formal_site.sh`，随后由严格合并器生成最终报告。

## 主要证据

- `data/phase2_p2/dataset_card.json`
- `data/reports/phase2_counterfactual_collection_p2.json`
- `data/reports/phase2_p2_multiseed_ensemble_gpu.json`
- `data/reports/phase2_p2_ensemble_evaluation_test_gpu.json`
- `data/reports/phase3_counterfactual_ranking_p2_gpu.json`
- `data/reports/phase3_multistep_observed_p2_gpu.json`
- `data/reports/androidworld_preflight_latest.json`
- `data/reports/phase4_feedback_experiment_gpu.json`
- `data/reports/androidworld_task_eval_w4.json`
- `data/reports/webarena_online_evaluation_w4.json`

## 结果边界

阶段二至阶段四的离线指标衡量预测、校准、反事实排序与有限步轨迹漂移，不等于完整 WebArena 在线任务成功率。三站 9 题结果是使用同题失败反馈修复后的回归；P0 三轮冻结未见集合中，Round-3 主对比（W4+护栏 vs Reactive+护栏）点估计相对 +33.3%（3/78 → 4/78），达到申报书相对 +10% 目标，但该增益仅由 1 个额外成功支撑，配对 CI 下界为 0，跨护栏的世界模型主效应仍为 0，不能视为稳健结论。该 78 题仍不是完整 812 题 benchmark。AndroidWorld 27/35 同样只作少量迁移检查。
