# P0 反事实规模与集成排序修复

## 目标

- 从 100 对扩展到 3,600 对同状态、真实环境执行的事实/反事实配对。
- 覆盖 30 个 MiniWoB 任务和 3 类干预：困难错误目标、错误动作类型、不存在目标。
- 测试集至少保留 200 个有效非平局配对；配对跨 split 泄漏为 0。
- 世界模型联合优化原多任务损失和 RankNet 配对排序损失。
- 三模型集成权重只在验证集上拟合；测试集仅做最终验收。

## 一键运行

GPU 服务器项目目录：`/root/autodl-tmp/agent_world_model_phase2`

```bash
bash scripts/run_counterfactual_p0.sh 2>&1 | tee artifacts/phase2/counterfactual_p0_run.log
```

采集阶段是浏览器/CPU 密集型，五次训练和集成评测使用 CUDA。

## 验收门槛

- `counterfactual_scale_1000 = true`
- `counterfactual_test_informative_200 = true`
- `counterfactual_tie_rate_le_20pct = true`
- `no_counterfactual_pair_leakage = true`
- `no_counterfactual_group_leakage = true`
- 集成 Pairwise Accuracy、NDCG@2 不低于最佳单模型
- 集成 Mean Decision Regret 不高于最佳单模型
- 配对 Bootstrap 95% CI 满足 2 个百分点非劣界

如果集成在验证集上不占优，生产方法自动回退为最佳单模型；测试集不会用于调权。
