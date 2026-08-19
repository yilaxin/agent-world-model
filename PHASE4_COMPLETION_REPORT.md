# 阶段四完成报告：反馈优化和实验

更新时间：2026-08-13

## 结论

阶段四要求的预测误差计算、困难样本池、离线重训练、主实验、消融实验和少量 AndroidWorld 迁移均已完成。截图中遗留的 Reddit、Shopping、GitLab 多站在线链路也已打通，并生成 evaluator-backed 的正式逐步证据。

W4 发布模型以来源级 50% W3 + 50% priority W4 组成，六个成员的具体权重由验证集校准；所有发布选择均在验证集完成，独立测试集只评估一次。

## 反馈闭环与困难样本池

- 反馈样本池：9,388 条；完整观测动作对：2,538 对。
- 预测误差：均值 0.13763，P95 0.35938。
- regret 均值：0.73075。
- 反馈信号：rank flip 2、stall 5,309、结构错误 4,299。
- 反馈源：预测误差、动作排序遗憾、rank flip、停滞和任务—控件结构错配。

实现见 `agent_world_model/phase4_feedback.py`、`scripts/run_phase4_feedback.py` 和 `configs/phase4_feedback.json`。

## 主实验、消融和发布校准

在相同验证集上完成 uniform、prediction-error、priority、no-regret、no-rank-flip、no-stall、no-struct 等变体。原始 priority 模型在验证排序指标上最好，但未独立满足全部发布门槛；最终采用来源级 W3/W4 50/50 的保守集成，并在验证集内校准成员权重和温度。

W4 独立测试结果：

| 指标 | 结果 |
|---|---:|
| MSE | 0.002466 |
| cosine | 0.987656 |
| progress MAE | 0.094710 |
| reward MAE | 0.187387 |
| state delta F1 | 0.987414 |
| task signal F1 | 0.987614 |
| risk F1 | 0.941977 |
| risk ECE | 0.008960 |
| 有效动作对 | 396 |
| pairwise accuracy | 0.974747 |
| rank-flip rate | 0.025253 |
| regret | 0.056187 |

完整结果见 `data/reports/phase4_feedback_experiment_gpu.json`，发布清单见 `artifacts/phase4/world_model_ensemble_w4.json`。

## AndroidWorld 少量迁移

W4 在 7 个真实 AndroidWorld 任务、每任务 1 个 episode 上成功 5/7（71.4%），动作执行率 100%。失败项为 Wi-Fi 关闭与日历任务。该结果只用于少量迁移检查，不替代此前每任务 5 个 episode 的主评估，也不支持统计显著提升结论。

完整记录见 `data/reports/androidworld_task_eval_w4.json`。

## WebArena 三站在线回归

### 环境与协议

- 站点容器：WebArena Verified Reddit、Shopping、GitLab 镜像。
- 任务与判分：BrowserGym 注册的经典 WebArena 812 题数据和 evaluator。
- 冻结子集：每站 3 题，共 9 题；seed=0。
- 公平性：reactive 与 W4 都使用 12 步上限。
- 状态隔离：每个 mode 都从同一不可变镜像重建全新站点容器；不会继承另一 mode 的订阅或页面状态。
- 完整性：没有读取或注入 evaluator 预期答案；最终合并器会拒绝缺题、重复、failure、预算不一致、答案注入、轨迹缺失或 SHA-256 不一致。
- 可追溯性：六份单站原始报告和 18 条 JSONL 轨迹全部随仓库交付。

### 最终结果

| 方法 | 成功 | 成功率 | 动作执行率 | 平均步数 |
|---|---:|---:|---:|---:|
| Reactive + 共享导航护栏 | 9/9 | 100% | 95.83% | 2.67 |
| W4 + 共享导航护栏 | 9/9 | 100% | 100% | 2.56 |

逐站成功率均为 3/3。配对成功率差为 0 个百分点，baseline-only 与 W4-only success 都为 0。

正式汇总见 `data/reports/webarena_online_evaluation_w4.json`，源报告见 `data/reports/webarena_formal_*.json`，逐步轨迹见 `data/trajectories_webarena_formal_evidence/`。

### 科研边界

9 个任务在首次运行前已冻结，但随后使用这些同题的失败轨迹修复了通用可见控件导航规则。因此最终 9/9 必须表述为 **post-fix regression**，不能作为未见任务泛化成功率。

Reactive 与 W4 共享修复后的导航护栏，所以 0 个百分点差值不能隔离或证明世界模型的在线贡献。结果只证明真实三站环境、动作执行、状态闭环和 evaluator 判分链路已打通；它不是完整 812 题 benchmark，也没有达到原定相对 SR +10% 的增益目标。

## 可复现入口

离线反馈实验：

```powershell
python scripts/run_phase4_feedback.py --config configs/phase4_feedback.json
python scripts/calibrate_phase4_release.py
python scripts/evaluate_androidworld_tasks.py --ensemble-manifest artifacts/phase4/world_model_ensemble_w4.json
```

三站在线回归在装有 Docker、BrowserGym 和 WebArena Verified 的 WSL 环境中执行：

```bash
bash scripts/run_webarena_formal_site.sh gitlab
bash scripts/run_webarena_formal_site.sh reddit
bash scripts/run_webarena_formal_site.sh shopping
```

将六份原始报告和轨迹归档到工作区后，运行：

```powershell
python scripts/archive_webarena_formal_evidence.py --report <六份单站报告>
python scripts/combine_webarena_formal_reports.py --report <六份单站报告>
```

正式配置见 `configs/webarena_multisite_eval.json`；单站配置见 `configs/webarena_formal_{gitlab,reddit,shopping}.json`。
