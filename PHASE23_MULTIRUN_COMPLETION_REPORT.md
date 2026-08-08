# 阶段二、阶段三多次训练完善报告

生成日期：2026-08-08

## 结论

本轮按照《大创申报书 33.0》中阶段二、阶段三的要求，完成了五次独立世界模型训练、三模型校准集成、三次动态结构对齐训练、W0–W3 决策阶梯、H=1/2/3 消融、覆盖率—风险分析、观察反事实排序和真实 WebArena Reddit 在线贯通。阶段二测试门槛 12/12 通过，阶段三工程验收门槛 6/6 通过。

模型在校准、进度/奖励回归和任务—GUI 结构对齐方面明显改善；但集成模型没有提高小样本观察反事实排序，真实 Reddit/WebArena 的 5 个固定任务仍为 0% 自主成功率。上述负面结果均原样保留，没有使用测试集调参。

## 申报书要求映射

| 申报书要求 | 本轮实现 | 状态 |
|---|---|---|
| 动作条件一步世界模型 | 预测下一状态、进度、奖励、任务信号、风险和终止 | 完成 |
| symlog/symexp 稳定训练 | 进度与奖励头使用 symlog 训练、symexp 解码 | 完成 |
| 三个随机种子以上 | 训练种子 17、29、42、73、101 | 完成 |
| 不确定性与校准 | 三模型集成、温度缩放、ECE/Brier/NLL/AURC | 完成 |
| 动态任务—GUI 结构对齐 | 8 维结构特征 + 三种子 MLP 排序器 | 完成 |
| 短期/长期分支和有限步前瞻 | W0–W3、H=1/2/3、beam search、安全降级 | 完成 |
| 观察反事实排序 | 100 对同状态替代动作，报告 Pairwise/NDCG/RankFlip | 完成但样本不足 |
| 在线调用 | GPU HTTP 推理服务 + SSH 转发 + 本机 WebArena | 已贯通，SR 未提升 |

## 阶段二：多次训练与集成

数据集包含 3,333 条转移、1,550 个 episode、30 个任务；训练/验证/测试按 episode 切分为 2,342/476/515，无 episode 泄漏。观察反事实为 100 对，严重失败正例 175 条。

五次独立训练按验证集选择分排序：

| 变体 | 种子 | 最佳 epoch | 验证选择分 |
|---|---:|---:|---:|
| risk_balanced_b | 101 | 28 | 0.8118 |
| base_a | 17 | 36 | 0.8058 |
| base_b | 42 | 35 | 0.8058 |
| risk_balanced_a | 29 | 35 | 0.8022 |
| regularized | 73 | 40 | 0.7990 |

仅使用验证集选择种子 101、17、42 组成三模型集成，并在验证集拟合逐标签温度。测试集结果：

| 指标 | 原单模型 | 新集成 | 变化 |
|---|---:|---:|---:|
| 风险 ECE | 0.0266 | 0.0104 | 改善 60.9% |
| 进度 MAE | 0.0612 | 0.0543 | 改善 11.3% |
| 奖励 MAE | 0.0620 | 0.0564 | 改善 9.0% |
| 状态变化 F1 | 0.9887 | 0.9914 | 提升 |
| 风险 AUROC | 0.9936 | 0.9942 | 提升 |
| 风险 F1 | 0.9074 | 0.9049 | 略降 |

最佳单模型种子 101 的风险 F1 为 0.9273；因此单模型保留为分类 champion，集成用于校准、不确定性和规划安全门控。

## 阶段三：结构对齐与有限步决策

动态结构对齐器以任务文本、元素名称/角色、AXTree 深度、任务阶段和历史重复等 8 个特征训练。测试集 Top-1 从规则基线 63.9% 提升到 82.9%，MRR 从 0.8156 提升到 0.9054，Recall@3 保持 100%。

515 条独立测试样本的 W0–W3 评测中，原始状态匹配率、候选合法率、安全动作 Recall@k、解释完整率和有限步合规率均达到 100%。W3 危险动作规避率为 66.5%，平均置信度 0.690，端到端推理平均/P95 为 20.59/64.03 ms。

H=1/2/3 动作一致率分别为 35.3%/23.9%/21.2%，平均延迟分别为 5.32/13.58/34.45 ms。多步想象在当前启发式数据上会累积偏差，因此 W3 采用置信度自适应视野，不把更深 rollout 默认视为更好。

## 在线与反事实结果

真实 Reddit/WebArena 固定任务 27–31 已通过 SSH 转发调用 GPU 集成模型，共执行 30 个动作，动作执行率 100%，无运行失败；5 个任务自主成功率仍为 0%。这证明在线链路已贯通，但当前规则候选/世界模型尚不具备可靠的信息检索、答案生成与终止策略。

观察反事实测试的有效配对很少：最佳单模型配对准确率 61.5%、NDCG@2 0.8580；集成模型配对准确率 53.8%、NDCG@2 0.8297。该负面结果说明需要扩充同状态受控替代动作，而不是继续在测试集上调权。

## 交付物

- `artifacts/phase2/multiseed/`：五个独立世界模型检查点。
- `artifacts/phase2/world_model_ensemble_p1.json`：三模型集成清单与温度参数。
- `artifacts/phase3/structure_aligner_best.pt`：结构对齐最佳检查点。
- `data/reports/phase2_multiseed_ensemble_gpu.json`：五次训练、选择与稳定性报告。
- `data/reports/phase2_ensemble_evaluation_test_gpu.json`：阶段二集成测试报告。
- `data/reports/phase3_structure_alignment_gpu.json`：结构对齐训练报告。
- `data/reports/phase3_counterfactual_ranking_gpu.json`：观察反事实排序报告。
- `data/reports/phase3_evaluation_ensemble_gpu.json`：W0–W3 和 H=1/2/3 完整评测。
- `data/reports/webarena_phase3_online_evaluation_gpu.json`：真实 WebArena 在线报告。
- `output/phase23_dashboard.html`：本地自包含结果看板。
- `site/`：已通过构建、测试和视觉验收的 Sites 站点源码。
- GPU 服务器目录：`/root/autodl-tmp/agent_world_model_phase2`。

## 尚未解决的问题

1. P0：真实 WebArena 自主成功率仍为 0%，完整多站点部署和相对 SR +10% 属于阶段四。
2. P0：观察反事实规模仅 100 对，测试有效配对过少，集成排序没有改善。
3. P1：当前数据源仍以 MiniWoB 与启发式标签为主，需要增加人工核验和 WebArena 受控候选结果。
4. P1：H=2/3 累积模型偏差，需要更多多步真实轨迹与终止/破坏性操作样本。
5. P2：AndroidWorld 仅完成适配和预检，尚缺 ADB、模拟器和真实运行包。
6. 外部阻塞：GitHub 连接器无账号、仓库无 remote；Sites 创建调用未返回项目 ID，暂未能完成远程发布。

## 复现命令

```bash
python scripts/train_phase2_multiseed.py --config configs/phase2_world_model_multiseed.json --device cuda
python scripts/train_structure_alignment.py --config configs/phase3_structure_alignment.json --device cuda
python scripts/evaluate_counterfactual_ranking.py --dataset-dir data/phase2_p1 --device cuda
python scripts/evaluate_phase3_planner.py --config configs/phase3_planner.json --dataset-dir data/phase2_p1 --device cuda
python scripts/serve_phase3_inference.py --ensemble-manifest artifacts/phase2/world_model_ensemble_p1.json --alignment-checkpoint artifacts/phase3/structure_aligner_best.pt --planning-config configs/phase3_planner.json --device cuda
```
