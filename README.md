# Agent 世界模型决策优化

本仓库实现《大创申报书 33.0》中的前三个阶段，当前重点交付为阶段二“动作条件世界模型”和阶段三“候选动作前瞻决策”。正式实验环境为 AutoDL RTX 4090、PyTorch 2.1.2+cu121、CUDA 12.1。

## 当前完成状态

- 数据集：3,333 条状态转移、1,550 个 episode、30 个任务，按 episode 切分为 2,342/476/515。
- 阶段二：五次独立训练，验证集选择三个成员，逐标签温度校准和不确定性集成。
- 阶段三：动态任务—GUI 结构对齐、W0–W3 决策阶梯、H=1/2/3 有限步消融和置信度安全降级。
- 观察反事实：100 对同状态替代动作，报告 Pairwise/NDCG/RankFlip/Regret。
- 在线贯通：本机真实 WebArena Reddit 通过 SSH 转发调用 GPU Agent，30/30 动作执行成功；5 个固定任务自主成功率仍为 0%。
- 验收：阶段二 12/12 测试门槛通过，阶段三 6/6 工程门槛通过；44/44 GPU 单元测试通过。

完整结果请看：

- [阶段二、阶段三多次训练完善报告](PHASE23_MULTIRUN_COMPLETION_REPORT.md)
- `output/pdf/阶段二阶段三多次训练完善报告.pdf`
- `output/phase23_dashboard.html`

## 关键目录

```text
agent_world_model/                 核心编码器、世界模型、集成、结构对齐与规划器
artifacts/phase2/multiseed/        五个独立世界模型检查点
artifacts/phase3/                  结构对齐检查点
configs/                           训练与评测配置
data/phase2_p1/                    本地数据卡；完整数据同时保存在 GPU 服务器
data/reports/                      机器可读 JSON 证据
scripts/                           数据、训练、评测、在线服务和报告脚本
site/                              已通过构建和测试的 Sites 结果站点
tests/                             单元测试
```

GPU 服务器工作目录：

```text
/root/autodl-tmp/agent_world_model_phase2
```

## 复现

在项目根目录执行：

```bash
python scripts/train_phase2_multiseed.py \
  --config configs/phase2_world_model_multiseed.json \
  --device cuda

python scripts/train_structure_alignment.py \
  --config configs/phase3_structure_alignment.json \
  --device cuda

python scripts/evaluate_counterfactual_ranking.py \
  --dataset-dir data/phase2_p1 \
  --device cuda

python scripts/evaluate_phase3_planner.py \
  --config configs/phase3_planner.json \
  --dataset-dir data/phase2_p1 \
  --device cuda
```

启动 GPU 推理服务：

```bash
python scripts/serve_phase3_inference.py \
  --ensemble-manifest artifacts/phase2/world_model_ensemble_p1.json \
  --alignment-checkpoint artifacts/phase3/structure_aligner_best.pt \
  --planning-config configs/phase3_planner.json \
  --device cuda
```

## 结果边界

阶段二和阶段三的离线指标衡量预测、校准、候选覆盖、结构排序、危险动作规避和有限步规划，不等于完整 WebArena 在线任务成功率。观察反事实规模仍小，H=2/3 存在累积偏差，完整多站点 WebArena 与相对 SR +10% 应在阶段四独立验证。
