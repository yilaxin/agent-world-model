# 阶段一完成报告：环境、基线与状态表征

完成日期：2026-08-06（Asia/Shanghai）

## 结论

阶段一已经形成可重复运行、可记录、可评测的轻量 WebArena 基线闭环。当前电脑上
的真实 WebArena Reddit 服务可以初始化和重置，固定任务通过官方评测器；反应式
Agent、完整轨迹、DOM/AXTree 状态抽取与第一版状态编码器均已实现并通过测试。

## 完成内容

| 阶段要求 | 完成情况 | 验收证据 |
| --- | --- | --- |
| WebArena 环境 | 已完成（Reddit 单站轻量部署） | `browsergym/webarena.27` reset 成功，服务健康 |
| 反应式 Agent | 已完成 | `ReactiveAgent` 支持 input、scroll、click、back、answer |
| 轨迹日志 | 已完成 | JSONL schema v2 保存状态、动作、奖励、下一状态、done、评测信息与编码 |
| DOM 状态抽取 | 已完成 | 可见 DOM 与 Accessibility Tree 双通道抽取和任务相关剪枝 |
| 第一版状态编码器 | 已完成 | 任务、URL、标签页、AXTree、DOM、最近 5 步动作编码成 512 维 `z_t` |
| 固定评测入口 | 已完成 | `configs/phase1_baseline.json` 与 `scripts/run_phase1_baseline.py` |

## 实际运行结果

- 单元测试：13/13 通过。
- Python 语法编译：通过。
- Chromium/Playwright 无头浏览器：通过。
- BrowserGym 四动作链路：input → scroll → click → back 全部执行成功，
  输入值进入页面状态，点击进入第二页，返回动作回到起始页。
- MiniWoB `click-test`：奖励 1.0，成功终止，1 步完成。
- WebArena `webarena.27`：官方评测奖励 1.0，`terminated=True`，
  `truncated=False`，1 步完成。
- 阶段总报告：`data/reports/phase1_latest.json` 中 `all_passed=true`。

## 对队友代码的处理

队友压缩包中的反应式 Agent 分层思路可以继续参考，但原包不能直接作为当前阶段
入口：任务加载参数不一致、动作候选校验不完整、状态编码缺少表单值和最近动作，
且评测脚本会改写任务 URL。为避免把这些问题带入现有工程，本次保留其架构思想，
在正在使用的 WSL 项目中实现了更小、更可测试的基线闭环。

## 轻量化调整

- 只部署 WebArena Reddit 单站；未下载 Wikipedia、Map 等大体积数据。
- 浏览器全程 headless。
- 截图只记录形状和数据类型，不保存像素数组。
- AXTree/DOM 设置字符和行数上限，并删除高体积 DOM 属性。
- 状态编码使用确定性 CPU 特征哈希，512 维，不下载大模型，不使用 GPU。
- 固定 MiniWoB 与 WebArena 各一个验收任务，并限制最大步数，便于快速复现。
- 轨迹逐步写盘，避免长实验占用大量内存。

## 未做或受限项

- WebArena 的 Shopping、Shopping Admin、GitLab、Wikipedia、Map 尚未本地部署。
  其中 Wikipedia 和 Map 数据量很大，当前磁盘条件不适合完整本地部署。
- 当前阶段的 WebArena 成功用例是固定评测烟雾任务，使用已知答案验证环境、动作、
  轨迹和官方 evaluator 的闭环；它不是对任意 WebArena 任务的通用推理能力声明。
- 当前文件夹不是 Git 仓库，没有远程仓库，因此没有推送 GitHub 或创建 PR。
- 项目没有 `.openai/hosting.json`，且阶段一交付物不是网站，因此没有 Sites 部署。

以上限制均不影响阶段一“稳定运行并评测的基线系统”作为后续世界模型数据入口；
跨站全量评测和更强的自主推理策略应在资源充足时继续扩展。

## 复现命令

```bash
cd ~/agent_world_model
source .venv/bin/activate
source .env
source .env.webarena

python -m unittest discover -s tests -v
python scripts/smoke_phase1_actions.py
python scripts/run_phase1_baseline.py --suite all
```
