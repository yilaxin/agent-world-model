# 轨迹日志、状态抽取与第一版编码器

阶段一的数据链路由三个可复用模块组成：

- `agent_world_model/state.py`：从 BrowserGym observation 抽取页面元数据、
  Accessibility Tree 和可见 DOM，并按交互性、任务关键词和上下文剪枝。
- `agent_world_model/encoder.py`：把任务、URL、页面标题、标签页、最近 5 步动作、
  AXTree 和 DOM 组合成结构化文本，再编码为确定性的 512 维 `z_t`。
- `agent_world_model/trajectory.py`：以 JSONL 流式写入完整状态转移。

## 轻量化设置

- 默认只保存截图尺寸和数据类型，不保存截图像素。
- Accessibility Tree 最多保留 16,000 字符或 220 行。
- DOM 最多保留 24,000 字符或 320 行。
- 优先保留交互控件、带 BrowserGym ID 的节点、任务关键词和相邻上下文。
- DOM 中的 `style`、`class`、`src`、`srcset` 和 `data-*` 属性会被移除。
- 编码器使用 CPU 特征哈希，不下载语言模型、不依赖显卡或 PyTorch。
- JSONL 每完成一步就刷新到磁盘，不在内存中积累整个实验。

## 轨迹 schema v2

每行是一条完整的 `(s_t, a_t, r_t, s_{t+1}, done_t)`：

```text
state
action
next_state
reward
terminated
truncated
done
info
decision
encoded_state
encoded_next_state
```

`state` 与 `next_state` 包含任务、URL、标题、标签页、动作错误、截图元数据、
剪枝后的 AXTree/DOM；`encoded_state` 与 `encoded_next_state` 保存 512 维向量、
编码器版本、最近 5 步动作和可追溯 ID。

## 运行完整阶段一基线

```bash
cd ~/agent_world_model
source .venv/bin/activate
source .env
source .env.webarena
python scripts/run_phase1_baseline.py --suite all
```

结果写入：

```text
data/trajectories/*.jsonl
data/reports/phase1_latest.json
data/reports/phase1_actions_latest.json
```

## 单独采集

```bash
# MiniWoB 反应式点击任务
python scripts/collect_miniwob_trajectory.py

# WebArena 固定评测任务（先 source .env.webarena）
python scripts/collect_webarena_trajectory.py
```

## 测试

```bash
python -m unittest discover -s tests -v
python scripts/smoke_phase1_actions.py
```

第二条命令会在真实 BrowserGym 页面中依次执行输入、滚动、点击、返回，并把四步
都写入同一条可训练轨迹。
