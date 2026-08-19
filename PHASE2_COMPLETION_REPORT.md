# 阶段二完成报告：动作条件世界模型

更新日期：2026-08-08

## 结论

阶段二已按照新申报书完成：数据扩充、动作条件一步世界模型、下一状态/进度/奖励/风险/终止多任务预测、symlog/symexp、至少三个随机种子、概率校准、不确定性集成和候选动作 W0 重排。最终在 RTX 4090 上完成五次独立训练，阶段二验证集和测试集均为 12/12 门槛通过。

## 数据

> 历史说明：下表记录阶段二首次完成时的 P1 数据口径。项目随后在阶段二/三补强中扩展为
> 13,348 条转移、5,930 个 episode、3,600 对观察反事实，并重新完成五次多种子训练。
> 结题与最终指标应以 `PHASE23_MULTIRUN_COMPLETION_REPORT.md` 及
> `data/reports/phase2_p2_multiseed_ensemble_gpu.json` 为准。

| 指标 | 结果 |
|---|---:|
| 转移数 | 3,333 |
| episode 数 | 1,550 |
| 任务数 | 30 |
| train / validation / test | 2,342 / 476 / 515 |
| 观察反事实 | 100 对 |
| 严重失败正例 | 175 |
| episode 跨 split 泄漏 | 0 |

## 多次训练

完成种子 17、29、42、73、101 共五次独立训练。仅依据验证集选择种子 101、17、42 组成三模型集成，并在验证集拟合逐标签温度。

最佳单模型种子 101 的测试风险 F1 为 0.9273。校准集成的测试风险 F1 为 0.9049，但风险 ECE 从原单模型 0.0266 降至 0.0104，进度 MAE 从 0.0612 降至 0.0543，奖励 MAE 从 0.0620 降至 0.0564。因此保留种子 101 作为分类 champion，集成用于校准、不确定性和安全门控。

## 测试指标

| 指标 | 结果 |
|---|---:|
| 状态变化 F1 | 0.9914 |
| 任务信号 F1 | 0.9846 |
| 风险 F1 | 0.9049 |
| 风险 AUROC | 0.9942 |
| 风险 ECE | 0.0104 |
| 风险 Brier | 0.0121 |
| 风险 NLL | 0.0440 |
| 风险 AURC | 0.0039 |
| 进度 MAE | 0.0543 |
| 奖励 MAE | 0.0564 |

## 交付物

- `agent_world_model/phase2_ensemble.py`
- `configs/phase2_world_model_multiseed.json`
- `scripts/train_phase2_multiseed.py`
- `artifacts/phase2/multiseed/`
- `artifacts/phase2/world_model_ensemble_p1.json`
- `data/reports/phase2_multiseed_ensemble_gpu.json`
- `data/reports/phase2_ensemble_evaluation_test_gpu.json`

## 遗留问题（首次阶段验收时）

观察反事实只有 100 对，测试有效配对很少，集成排序没有超过最佳单模型；数据标签仍有较高启发式占比。下一步需要人工核验并扩充 WebArena 同状态受控替代动作。

上述“100 对”问题已在后续补强中解决为 3,600 对；它不再是最终结题状态。
