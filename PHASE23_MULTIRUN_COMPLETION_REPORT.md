# 阶段二、阶段三多次训练最终完善报告

更新时间：2026-08-10
实验环境：AutoDL RTX 4090，PyTorch 2.1.2+cu121，CUDA 12.1

## 总结

本轮依据《大创申报书 33.0》完成了阶段二和阶段三的最终离线工程验收：观察反事实扩大到 3,600 对，数据质量门禁全部通过，完成五次多种子 GPU 训练并选择三个成员，阶段二独立测试以及阶段三反事实排序、真实连续 H=1/2/3 轨迹评估均通过既定门槛。

这些结果不等于 WebArena 在线成功率。本轮服务器没有 REDDIT、SHOPPING、GITLAB 等完整多站点环境变量，因此没有执行新的 WebArena 在线评测，也没有伪造成功率提升。

## 阶段二最终结果

| 项目 | 结果 |
|---|---:|
| 状态转移 / episode / 任务 | 13,348 / 5,930 / 30 |
| Train / Validation / Test | 9,388 / 2,017 / 1,943 |
| 有效观察反事实 | 3,600 对 |
| 有信息反事实 | 3,050 对（84.72%） |
| 采集失败 / 状态匹配率 | 0 / 100% |
| 五次训练 / 集成成员 | 5 / 3 |
| 测试状态变化 F1 | 98.69% |
| 测试任务信号 F1 | 98.90% |
| 测试风险 F1 / AUROC | 94.39% / 99.04% |
| 测试进度 MAE | 0.0992 |

最终选择 `rank_balanced_a`（seed 29）、`rank_regularized`（seed 73）和 `rank_base_a`（seed 17）。模型选择和校准只使用验证集，测试集只报告最终结果。

## 阶段三最终结果

反事实测试包含 477 个观察配对，其中 396 个有效配对。最佳单模型和校准集成的 Pairwise Accuracy 均为 97.73%，NDCG@2 均为 0.9916；集成没有带来准确率提升，但把平均决策遗憾从 0.0638 降到 0.0511。配对准确率差异 95% CI 为 [-1.01%, 1.01%]，因此生产方法仍按验证集选择单模型。

| H | 测试窗口 | Latent MSE | 余弦相似度 | 终止结尾 | 严重失败 |
|---|---:|---:|---:|---:|---:|
| 1 | 1,943 | 0.000173 | 0.9523 | 375 | 175 |
| 2 | 619 | 0.000287 | 0.9385 | 62 | 26 |
| 3 | 329 | 0.000485 | 0.9189 | 32 | 21 |

长视野测试共有 948 个窗口、94 个终止结尾和 47 个严重失败结尾，覆盖门槛全部通过。H3 MSE 虽通过预设的相对上限，但仍差于 persistence baseline，说明多步潜状态预测仍有改进空间。

## 已解决与未解决

已解决：

- P0 观察反事实规模从 100 对扩大到 3,600 个有效配对。
- P1 H2/H3 样本、终止和严重失败覆盖全部超过门槛。
- P1 完成五次多种子训练和最终独立测试。
- P1 阶段三反事实与多步离线验收通过。
- GitHub 分支、PR 和 Sites 私有项目已接通。

仍需处理：

- P0：部署完整 WebArena 多站点环境并做固定任务、预算和种子的在线重评；相对 SR +10% 属于阶段四。
- P1：500 条高风险、终止和严重失败样本已完成原始轨迹证据复核并以 `evidence_verified` 回写同规模数据视图；项目验收采用可复现证据复核，人工签字不是验收门槛。该来源仍保持为 `evidence_verified`，不伪称为 `human_verified`。
- P2：AndroidWorld 已补齐官方 AndroidWorld 0.1.0、ADB、Pixel 6 API 33 AVD、gRPC 8554 与运行手册；本机 WHPX 硬件加速模拟器上真实 `reset → action → state` 冒烟已通过（19 个无障碍 UI 元素），预检 `runtime_ready=true`。任务级首轮评测已完成并验证了「语义目标匹配优先」修正：阶段三规划器 open_chrome 0%→100%、整体 0%→33.3%（语义覆盖 5 次），反应式基线整体 11.1%（open_chrome 1/3，受转发器偶发抖动影响）；wifi 导航任务两条策略仍为 0%，策略可用性仍待提升，不能声称迁移完成。

## 证据文件

- `data/phase2_p2/dataset_card.json`
- `data/reports/phase2_counterfactual_collection_p2.json`
- `data/reports/phase2_p2_multiseed_ensemble_gpu.json`
- `data/reports/phase2_p2_ensemble_evaluation_test_gpu.json`
- `data/reports/phase3_counterfactual_ranking_p2_gpu.json`
- `data/reports/phase3_multistep_observed_p2_gpu.json`
- `data/reports/androidworld_preflight_latest.json`
- `output/pdf/阶段二阶段三最终进度与遗留问题报告_2026-08-10.pdf`
