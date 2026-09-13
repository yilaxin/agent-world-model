# WebArena 失败归因（动作级）

生成时间：2026-09-12T01:56:18+00:00

覆盖 episode 1565 条，其中失败 1508 条。分类由可观测轨迹字段推导：执行动作、decision 候选元数据、动作错误、访问 URL、是否提交答案。

复现（在 WSL 中，轨迹与报告位于评测仓库）：

```bash
python3 scripts/attribute_webarena_failures.py \
  --report-dir data/reports \
  --output-json data/reports/webarena_failure_attribution.json \
  --output-markdown WEBARENA_FAILURE_ATTRIBUTION.md \
  --output-html WEBARENA_FAILURE_ATTRIBUTION.html
```

迭代单个轮次时加 `--only-round round4`，单站点加 `--only-site gitlab`；报告尚未生成的格子可用 `--corpus-dir data/trajectories_...` 直接扫轨迹目录。

## 失败类型分布

| 类型 | 说明 | 归属模块 | 数量 | 占比 |
|---|---|---|---:|---:|
| `loop_stall` | 循环/停滞 | 循环恢复（loop recovery） | 408 | 27.1% |
| `wrong_route` | 流程路径错误 | 站点流程知识（进入目标页面/流程） | 353 | 23.4% |
| `budget_exhausted` | 预算耗尽 | 候选优先级与探索效率 | 299 | 19.8% |
| `candidate_missing` | 候选缺失/语义失配 | 候选生成（候选集合未包含目标元素） | 227 | 15.1% |
| `missing_termination` | 缺显式终止 | 终止策略（观察态已满足但未提交答案） | 83 | 5.5% |
| `form_or_search_incomplete` | 表单/搜索流程不完整 | 表单与搜索模块（构造查询、提交、校验） | 66 | 4.4% |
| `action_execution` | 动作执行失败 | 动作执行鲁棒性（超时、重试、等待策略） | 51 | 3.4% |
| `task_understanding` | 目标理解偏差 | 任务解析与子目标分解 | 12 | 0.8% |
| `element_location` | 元素定位失败 | 候选生成与元素定位（AXTree/DOM 剪枝、grounding） | 9 | 0.6% |

## 模块工作量排序（按失败条数）

| 模块 | 失败条数 |
|---|---:|
| 循环恢复（loop recovery） | 408 |
| 站点流程知识（进入目标页面/流程） | 353 |
| 候选优先级与探索效率 | 299 |
| 候选生成（候选集合未包含目标元素） | 227 |
| 终止策略（观察态已满足但未提交答案） | 83 |
| 表单与搜索模块（构造查询、提交、校验） | 66 |
| 动作执行鲁棒性（超时、重试、等待策略） | 51 |
| 任务解析与子目标分解 | 12 |
| 候选生成与元素定位（AXTree/DOM 剪枝、grounding） | 9 |

## 各单元格成功率

| 单元格 | 成功/总数 | 成功率 |
|---|---:|---:|
| round2/gitlab/reactive/guard_off | 1/28 | 3.6% |
| round2/gitlab/reactive/guard_on | 1/28 | 3.6% |
| round2/gitlab/world-model/guard_off | 1/28 | 3.6% |
| round2/gitlab/world-model/guard_on | 1/28 | 3.6% |
| round2/reddit/reactive/guard_off | 0/29 | 0.0% |
| round2/reddit/reactive/guard_on | 1/29 | 3.4% |
| round2/reddit/world-model/guard_off | 0/29 | 0.0% |
| round2/reddit/world-model/guard_on | 0/10 | 0.0% |
| round2/shopping/reactive/guard_off | 0/21 | 0.0% |
| round2/shopping/reactive/guard_on | 0/21 | 0.0% |
| round2/shopping/world-model/guard_off | 0/21 | 0.0% |
| round2/shopping/world-model/guard_on | 0/21 | 0.0% |
| round3/gitlab/reactive/guard_off | 0/30 | 0.0% |
| round3/gitlab/reactive/guard_on | 0/30 | 0.0% |
| round3/gitlab/world-model/guard_off | 0/30 | 0.0% |
| round3/gitlab/world-model/guard_on | 1/30 | 3.3% |
| round3/reddit/reactive/guard_off | 0/18 | 0.0% |
| round3/reddit/reactive/guard_on | 0/18 | 0.0% |
| round3/reddit/world-model/guard_off | 0/18 | 0.0% |
| round3/reddit/world-model/guard_on | 0/18 | 0.0% |
| round3/shopping/reactive/guard_off | 3/30 | 10.0% |
| round3/shopping/reactive/guard_on | 3/30 | 10.0% |
| round3/shopping/world-model/guard_off | 2/30 | 6.7% |
| round3/shopping/world-model/guard_on | 3/30 | 10.0% |
| round4/gitlab/reactive/guard_off | 0/120 | 0.0% |
| round4/gitlab/reactive/guard_on | 2/120 | 1.7% |
| round4/gitlab/world-model/guard_off | 0/120 | 0.0% |
| round4/gitlab/world-model/guard_on | 2/120 | 1.7% |
| round4/shopping/reactive/guard_off | 9/120 | 7.5% |
| round4/shopping/reactive/guard_on | 9/120 | 7.5% |
| round4/shopping/world-model/guard_off | 9/120 | 7.5% |
| round4/shopping/world-model/guard_on | 9/120 | 7.5% |

## 分站点失败类型分布

| 分组 | 循环/停滞 | 元素定位失败 | 动作执行失败 | 缺显式终止 | 表单/搜索流程不完整 | 流程路径错误 | 候选缺失/语义失配 | 预算耗尽 | 目标理解偏差 | 评测/环境异常 | 失败合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gitlab | 207 | 9 | 43 | 47 | 48 | 142 | 92 | 104 | 11 | 0 | 703 |
| reddit | 77 | 0 | 4 | 0 | 2 | 6 | 41 | 38 | 0 | 0 | 168 |
| shopping | 124 | 0 | 4 | 36 | 16 | 205 | 94 | 157 | 1 | 0 | 637 |

## 分轮次失败类型分布

| 分组 | 循环/停滞 | 元素定位失败 | 动作执行失败 | 缺显式终止 | 表单/搜索流程不完整 | 流程路径错误 | 候选缺失/语义失配 | 预算耗尽 | 目标理解偏差 | 评测/环境异常 | 失败合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| round2 | 96 | 0 | 8 | 7 | 12 | 55 | 54 | 52 | 4 | 0 | 288 |
| round3 | 87 | 0 | 11 | 15 | 10 | 60 | 49 | 68 | 0 | 0 | 300 |
| round4 | 225 | 9 | 32 | 61 | 44 | 238 | 124 | 179 | 8 | 0 | 920 |

## 主类型 × 次级信号重叠

分类给每条失败 episode 一个**主类型**（阻塞症状），这里再看它同时具备哪些次级信号，用来区分「症状」和「根因」：例如 `loop_stall` 里有多大比例其实是在反复点击语义无关的控件。

| 主类型 | 失败条数 | 候选语义失配 | 存在重复动作 | 目标需要输入但从未输入 | 有动作报错 |
|---|---:|---:|---:|---:|---:|
| 循环/停滞 (`loop_stall`) | 408 | 12 (3%) | 402 (99%) | 130 (32%) | 52 (13%) |
| 元素定位失败 (`element_location`) | 9 | 0 (0%) | 9 (100%) | 0 (0%) | 9 (100%) |
| 动作执行失败 (`action_execution`) | 51 | 13 (25%) | 15 (29%) | 30 (59%) | 51 (100%) |
| 缺显式终止 (`missing_termination`) | 83 | 6 (7%) | 40 (48%) | 0 (0%) | 36 (43%) |
| 表单/搜索流程不完整 (`form_or_search_incomplete`) | 66 | 3 (5%) | 9 (14%) | 66 (100%) | 27 (41%) |
| 流程路径错误 (`wrong_route`) | 353 | 124 (35%) | 121 (34%) | 170 (48%) | 72 (20%) |
| 候选缺失/语义失配 (`candidate_missing`) | 227 | 227 (100%) | 26 (11%) | 92 (41%) | 71 (31%) |
| 预算耗尽 (`budget_exhausted`) | 299 | 0 (0%) | 80 (27%) | 136 (45%) | 125 (42%) |
| 目标理解偏差 (`task_understanding`) | 12 | 0 (0%) | 0 (0%) | 0 (0%) | 1 (8%) |

## 失败时高频点击的元素（每条约取前 3 个高频目标统计）

用于判断候选集合是否把无关控件排到了前面：

- `Merge requests` × 112
- `Help` × 102
- `D` × 90
- `Image` × 73
- `\ue622 Cell Phones & Accessories` × 72
- `My Account` × 71
- `My Wish List` × 68
- `\ue622 Grocery & Gourmet Food` × 64
- `\ue622 Patio, Lawn & Garden` × 56
- `Commits` × 53
- `To-Do List` × 49
- `A` × 42
- `E` × 41
- `My Downloadable Products` × 38
- `\ue622 Video Games` × 35
- `Commits feed` × 31
- `Details` × 31
- `\ue622 Office Products` × 31
- `2,320 Commits` × 30
- `Reviews (12)` × 29
- `Create new...` × 26
- `Home` × 26
- `Food & Beverage Gifts( 1086 item )` × 25
- `Byte Blaze` × 24
- `Repository` × 24

### 分站点高频误点元素

- **gitlab**：`Merge requests`×112、`Help`×102、`D`×90、`Commits`×53、`To-Do List`×49、`A`×42、`E`×41、`Commits feed`×31、`2,320 Commits`×30、`Create new...`×26、`Byte Blaze`×24、`Repository`×24
- **reddit**：`Submissions`×19、`Search query`×16、`Post`×10、`Filter on: Featured`×9、`Upvote`×9、`Downvote`×8、`Comments`×8、`Apprehensive-Rest470`×7、`books`×6、`Bans`×6、`RunDNA`×5、`DIY`×5
- **shopping**：`Image`×73、`\ue622 Cell Phones & Accessories`×72、`My Account`×71、`My Wish List`×68、`\ue622 Grocery & Gourmet Food`×64、`\ue622 Patio, Lawn & Garden`×56、`My Downloadable Products`×38、`\ue622 Video Games`×35、`Details`×31、`\ue622 Office Products`×31、`Reviews (12)`×29、`Home`×26

## 循环/停滞（`loop_stall`，408 条）

归属模块：循环恢复（loop recovery）

- **round2/gitlab/reactive/guard_off · browsergym/webarena.524 · seed 0** （12 步，唯一 URL 2）
  - 目标：Star the top eight most stared repos in Gitlab
  - 证据：重复动作 3 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T133435Z_browsergym_webarena.524_seed0_998a9d38.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.181 · seed 0** （12 步，唯一 URL 2）
  - 目标：Open my latest created issue that has theme editor in its title to check if it is closed
  - 证据：重复动作 4 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134150Z_browsergym_webarena.181_seed0_30d46d51.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.306 · seed 0** （12 步，唯一 URL 3）
  - 目标：How many commits did Anthony make between 08/2022-09/2022?
  - 证据：重复动作 7 步，唯一 URL 数 3
  - 动作类型：{'scroll': 8, 'click': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134526Z_browsergym_webarena.306_seed0_64ae5ac8.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.537 · seed 0** （12 步，唯一 URL 2）
  - 目标：Follow ['Jakub Klinkovsk', 'convexegg', 'Vinta Chen', 'yjlou', 'Abishek S'] on Gitlab
  - 证据：重复动作 4 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134718Z_browsergym_webarena.537_seed0_266a319d.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.481 · seed 0** （12 步，唯一 URL 2）
  - 目标：Abishek wants to check my dotfile configurations. Please invite him to the repo as a guest.
  - 证据：重复动作 5 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135017Z_browsergym_webarena.481_seed0_8dc6c60e.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.669 · seed 0** （12 步，唯一 URL 2）
  - 目标：Open a new issue to discuss the implementation of dark mode
  - 证据：重复动作 4 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135150Z_browsergym_webarena.669_seed0_7123bb55.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.485 · seed 0** （12 步，唯一 URL 2）
  - 目标：Vinta wants to check my dotfile configurations. Please invite him to the repo as a guest.
  - 证据：重复动作 5 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135556Z_browsergym_webarena.485_seed0_3ecc6167.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.397 · seed 0** （12 步，唯一 URL 2）
  - 目标：Fork MetaSeq.
  - 证据：重复动作 10 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135904Z_browsergym_webarena.397_seed0_36e0ba5e.jsonl

## 元素定位失败（`element_location`，9 条）

归属模块：候选生成与元素定位（AXTree/DOM 剪枝、grounding）

- **round4/gitlab/reactive/guard_off · browsergym/webarena.207 · seed 2** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric and Kilian make on 1/3/2023 in total?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_off/reactive/20260819T120646Z_browsergym_webarena.207_seed2_adc2c12a.jsonl
- **round4/gitlab/reactive/guard_off · browsergym/webarena.206 · seed 0** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric make on 3/2?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_off/reactive/20260819T124507Z_browsergym_webarena.206_seed0_95866776.jsonl
- **round4/gitlab/reactive/guard_off · browsergym/webarena.206 · seed 1** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric make on 3/2?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_off/reactive/20260819T124545Z_browsergym_webarena.206_seed1_ece4280f.jsonl
- **round4/gitlab/reactive/guard_off · browsergym/webarena.206 · seed 2** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric make on 3/2?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_off/reactive/20260819T124622Z_browsergym_webarena.206_seed2_8ca2f5a2.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.207 · seed 0** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric and Kilian make on 1/3/2023 in total?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T162558Z_browsergym_webarena.207_seed0_7970c769.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.207 · seed 1** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric and Kilian make on 1/3/2023 in total?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T162632Z_browsergym_webarena.207_seed1_7bc196c3.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.207 · seed 2** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric and Kilian make on 1/3/2023 in total?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T162705Z_browsergym_webarena.207_seed2_ef5361dd.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.206 · seed 0** （12 步，唯一 URL 2）
  - 目标：How many commits did Eric make on 3/2?
  - 证据：3/12 步元素无效、缺失或已脱离页面
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T170057Z_browsergym_webarena.206_seed0_b5ae3d7e.jsonl

## 动作执行失败（`action_execution`，51 条）

归属模块：动作执行鲁棒性（超时、重试、等待策略）

- **round2/gitlab/reactive/guard_off · browsergym/webarena.411 · seed 0** （12 步，唯一 URL 7）
  - 目标：Make the LICENSE of byteblaze/cloud-to-butt to MIT license.
  - 证据：4/12 步动作执行报错，其中超时 4 步
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T133605Z_browsergym_webarena.411_seed0_e6874f33.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.811 · seed 0** （12 步，唯一 URL 4）
  - 目标：Assign the issue regarding 404 in a11yproject to myself.
  - 证据：4/12 步动作执行报错，其中超时 4 步
  - 动作类型：{'click': 12}
  - 高频点击：['0', 'Issue', 'New issue', 'Merge requests', 'Assign to me', 'Issues']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T181756Z_browsergym_webarena.811_seed0_71aca881.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.135 · seed 0** （12 步，唯一 URL 4）
  - 目标：How many commits did Eric and Kilian make to a11yproject on 1/3/2023?
  - 证据：4/12 步动作执行报错，其中超时 4 步
  - 动作类型：{'click': 12}
  - 高频点击：['Create new...', 'Merge requests', 'Packages and registries', '0', 'New issue', 'Byte Blaze']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T182231Z_browsergym_webarena.135_seed0_6b24779f.jsonl
- **round2/gitlab/world-model/guard_on · browsergym/webarena.135 · seed 0** （12 步，唯一 URL 4）
  - 目标：How many commits did Eric and Kilian make to a11yproject on 1/3/2023?
  - 证据：4/12 步动作执行报错，其中超时 4 步
  - 动作类型：{'click': 12}
  - 高频点击：['Create new...', 'Merge requests', 'Packages and registries', '0', 'New issue', 'Byte Blaze']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_on/world-model/20260814T185810Z_browsergym_webarena.135_seed0_68c1857d.jsonl
- **round2/reddit/reactive/guard_on · browsergym/webarena.641 · seed 0** （12 步，唯一 URL 4）
  - 目标：Post a notice on a virtual meetup for Harry Potter enthusiasts on July 8th in the books subreddit
  - 证据：8/12 步动作执行报错，其中超时 8 步
  - 动作类型：{'click': 10, 'fill': 1, 'keyboard_press': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/reddit/reactive_guard_on/reactive/20260814T113903Z_browsergym_webarena.641_seed0_e3c2d2ba.jsonl
- **round2/reddit/reactive/guard_on · browsergym/webarena.642 · seed 0** （12 步，唯一 URL 3）
  - 目标：Post a notice on a virtual meetup for Big little lies enthusiasts on Sep 10th in the books subreddit
  - 证据：11/12 步动作执行报错，其中超时 11 步
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/reddit/reactive_guard_on/reactive/20260814T114246Z_browsergym_webarena.642_seed0_1c9977b7.jsonl
- **round2/reddit/world-model/guard_on · browsergym/webarena.641 · seed 0** （12 步，唯一 URL 4）
  - 目标：Post a notice on a virtual meetup for Harry Potter enthusiasts on July 8th in the books subreddit
  - 证据：8/12 步动作执行报错，其中超时 8 步
  - 动作类型：{'click': 10, 'fill': 1, 'keyboard_press': 1}
  - 高频点击：['Search query']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/reddit/world-model_guard_on/world-model/20260814T131958Z_browsergym_webarena.641_seed0_91f0f5bd.jsonl
- **round2/reddit/world-model/guard_on · browsergym/webarena.642 · seed 0** （12 步，唯一 URL 3）
  - 目标：Post a notice on a virtual meetup for Big little lies enthusiasts on Sep 10th in the books subreddit
  - 证据：11/12 步动作执行报错，其中超时 11 步
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/reddit/world-model_guard_on/world-model/20260814T132457Z_browsergym_webarena.642_seed0_aa1df1e2.jsonl

## 缺显式终止（`missing_termination`，83 条）

归属模块：终止策略（观察态已满足但未提交答案）

- **round2/gitlab/reactive/guard_off · browsergym/webarena.341 · seed 0** （12 步，唯一 URL 5）
  - 目标：List all opened issues requesting new features
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/-/issues', '/issues']，末尾 URL http://localhost:8023/dashboard/issues?assignee_username=byteblaze
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T133746Z_browsergym_webarena.341_seed0_70ef698e.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.811 · seed 0** （12 步，唯一 URL 3）
  - 目标：Assign the issue regarding 404 in a11yproject to myself.
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/-/issues', '/issues']，末尾 URL http://localhost:8023/byteblaze/dotfiles/-/issues/new
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T133821Z_browsergym_webarena.811_seed0_093a31a7.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.341 · seed 0** （12 步，唯一 URL 5）
  - 目标：List all opened issues requesting new features
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/-/issues', '/issues']，末尾 URL http://localhost:8023/dashboard/issues?assignee_username=byteblaze
  - 动作类型：{'click': 12}
  - 高频点击：['Issues', 'All 66', 'To-Do List', 'Select project to create issue', 'Byte Blaze / gimmiethat.space']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T181716Z_browsergym_webarena.341_seed0_24010a45.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.663 · seed 0** （12 步，唯一 URL 5）
  - 目标：Open an issue to ask their plan on supporting Llama and other llama family models in metaseq.
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/issues/new', '/-/issues/new', '/-/issues']，末尾 URL http://localhost:8023/dashboard/issues?assignee_username=byteblaze
  - 动作类型：{'click': 12}
  - 高频点击：['Merge requests', 'Byte Blaze', 'Packages and registries', 'D', 'Create new...', 'New issue']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T182310Z_browsergym_webarena.663_seed0_72b60a12.jsonl
- **round2/shopping/reactive/guard_off · browsergym/webarena.521 · seed 0** （12 步，唯一 URL 7）
  - 目标：Subscribe to the newsletter of OneStopMarket
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/customer', '/account', '/newsletter']，末尾 URL http://localhost:7770/newsletter/manage/
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/shopping/reactive_guard_off/reactive/20260814T145933Z_browsergym_webarena.521_seed0_9312f9db.jsonl
- **round2/shopping/reactive/guard_on · browsergym/webarena.521 · seed 0** （12 步，唯一 URL 7）
  - 目标：Subscribe to the newsletter of OneStopMarket
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/customer', '/account', '/newsletter']，末尾 URL http://localhost:7770/newsletter/manage/
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/shopping/reactive_guard_on/reactive/20260814T152200Z_browsergym_webarena.521_seed0_9058f681.jsonl
- **round2/shopping/world-model/guard_off · browsergym/webarena.277 · seed 0** （12 步，唯一 URL 8）
  - 目标：Search for "batteries for iphone 13"
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/catalogsearch', '/search']，末尾 URL http://localhost:7770/catalogsearch/result/index/?q=iphone&product_list_dir=asc
  - 动作类型：{'click': 10, 'fill': 2}
  - 高频点击：['iphone', '\\ue615 Search', '\\ue614 Set Ascending Direction', 'Search', 'iphone 14', '\\ue622 Video Games']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/shopping/world-model_guard_off/world-model/20260814T194223Z_browsergym_webarena.277_seed0_c0184b69.jsonl
- **round3/gitlab/world-model/guard_off · browsergym/webarena.447 · seed 0** （12 步，唯一 URL 5）
  - 目标：Assign the issue regarding linking to an accessibility statement in a11y-webring.club to Rohan.
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/-/issues', '/issues']，末尾 URL http://localhost:8023/byteblaze/a11y-syntax-highlighting/-/issues/1
  - 动作类型：{'click': 12}
  - 高频点击：['Issue actions', 'A', 'Add LICENSE', 'To-Do List', 'Issue #1', 'Close issue']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round3_holdout/gitlab/world-model_guard_off/world-model/20260815T124549Z_browsergym_webarena.447_seed0_c9b6db3b.jsonl

## 表单/搜索流程不完整（`form_or_search_incomplete`，66 条）

归属模块：表单与搜索模块（构造查询、提交、校验）

- **round2/gitlab/reactive/guard_off · browsergym/webarena.477 · seed 0** （12 步，唯一 URL 5）
  - 目标：Set up a new, empty repository with the name awesome_program_aided_reasoning?
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/projects/new#create_from_template
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134557Z_browsergym_webarena.477_seed0_a2f34ec0.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.416 · seed 0** （12 步，唯一 URL 4）
  - 目标：Go to the merge request on wcag I have to review, find if the author of the merge request responded at the end, and reply "Thank you" if he did. Otherwise remind him with a simple @.
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/dashboard/merge_requests?reviewer_username=byteblaze
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135726Z_browsergym_webarena.416_seed0_4cec9831.jsonl
- **round2/gitlab/reactive/guard_on · browsergym/webarena.477 · seed 0** （12 步，唯一 URL 5）
  - 目标：Set up a new, empty repository with the name awesome_program_aided_reasoning?
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/projects/new#create_from_template
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_on/reactive/20260814T141947Z_browsergym_webarena.477_seed0_f9ba1ebf.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.181 · seed 0** （12 步，唯一 URL 8）
  - 目标：Open my latest created issue that has theme editor in its title to check if it is closed
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/dashboard/issues?assignee_username=byteblaze
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'D', 'Merge requests', 'Byte Blaze', 'Milestones', 'Closed 2']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T182114Z_browsergym_webarena.181_seed0_6d6127a9.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.802 · seed 0** （12 步，唯一 URL 9）
  - 目标：create a new group "coding_friends" with members qhduan, Agnes-U
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/groups/new#create-group-pane
  - 动作类型：{'click': 12}
  - 高频点击：['New group', 'Create group Assemble related projects together and grant members access to several projects at once.', 'D', '.github', 'Unverified', 'workflows']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T182348Z_browsergym_webarena.802_seed0_94328e8c.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.800 · seed 0** （12 步，唯一 URL 8）
  - 目标：create a new group "x-lab" with members JonasVautherin, dilipchandima, dawiss1337, bmyun, DCMJY
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/groups/new#
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'To-Do List', 'New group', 'A', 'Add LICENSE', 'Group']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T184137Z_browsergym_webarena.800_seed0_c27491fb.jsonl
- **round2/gitlab/world-model/guard_on · browsergym/webarena.802 · seed 0** （12 步，唯一 URL 9）
  - 目标：create a new group "coding_friends" with members qhduan, Agnes-U
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/groups/new#create-group-pane
  - 动作类型：{'click': 12}
  - 高频点击：['New group', 'Create group Assemble related projects together and grant members access to several projects at once.', 'D', '.github', 'Unverified', 'workflows']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_on/world-model/20260814T185923Z_browsergym_webarena.802_seed0_426c3d5b.jsonl
- **round2/gitlab/world-model/guard_on · browsergym/webarena.800 · seed 0** （12 步，唯一 URL 8）
  - 目标：create a new group "x-lab" with members JonasVautherin, dilipchandima, dawiss1337, bmyun, DCMJY
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:8023/groups/new#
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'To-Do List', 'New group', 'A', 'Add LICENSE', 'Group']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_on/world-model/20260814T191622Z_browsergym_webarena.800_seed0_d7a33088.jsonl

## 流程路径错误（`wrong_route`，353 条）

归属模块：站点流程知识（进入目标页面/流程）

- **round2/gitlab/reactive/guard_off · browsergym/webarena.135 · seed 0** （12 步，唯一 URL 5）
  - 目标：How many commits did Eric and Kilian make to a11yproject on 1/3/2023?
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/commits', '/-/commits']
  - 证据：末尾 URL http://localhost:8023/help/user/packages/package_registry/index
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134303Z_browsergym_webarena.135_seed0_5e23e7b4.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.663 · seed 0** （12 步，唯一 URL 5）
  - 目标：Open an issue to ask their plan on supporting Llama and other llama family models in metaseq.
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/issues/new', '/-/issues/new', '/-/issues']
  - 证据：末尾 URL http://localhost:8023/help/user/packages/package_registry/index
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134334Z_browsergym_webarena.663_seed0_abf95a8f.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.802 · seed 0** （12 步，唯一 URL 4）
  - 目标：create a new group "coding_friends" with members qhduan, Agnes-U
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/groups/new']
  - 证据：末尾 URL http://localhost:8023/projects/new#create_from_template
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134405Z_browsergym_webarena.802_seed0_c9281e9b.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.392 · seed 0** （12 步，唯一 URL 4）
  - 目标：Post "Good idea" for the merge request related to color ulitity in a11yproject.com project
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/-/merge_requests', '/merge_requests']
  - 证据：末尾 URL http://localhost:8023/a11yproject/a11yproject.com
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134844Z_browsergym_webarena.392_seed0_841e4e69.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.800 · seed 0** （12 步，唯一 URL 4）
  - 目标：create a new group "x-lab" with members JonasVautherin, dilipchandima, dawiss1337, bmyun, DCMJY
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/groups/new']
  - 证据：末尾 URL http://localhost:8023/projects/new#create_from_template
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T140031Z_browsergym_webarena.800_seed0_8449ae6d.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.665 · seed 0** （12 步，唯一 URL 3）
  - 目标：Open an issue to request adding support for MT theme editor in a11y-syntax-highlighting.
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/issues/new', '/-/issues/new', '/-/issues']
  - 证据：末尾 URL http://localhost:8023/aklsh/empathy-prompts/-/commit/3d54c962b3b5874ef102d9338223bc3d010ddf59
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T140324Z_browsergym_webarena.665_seed0_52948ed4.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.178 · seed 0** （12 步，唯一 URL 3）
  - 目标：Open my latest created issue that has better in its title to check if it is closed
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/-/issues', '/issues']
  - 证据：末尾 URL http://localhost:8023/byteblaze/empathy-prompts/-/commit/3d54c962b3b5874ef102d9338223bc3d010ddf59
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T140436Z_browsergym_webarena.178_seed0_760ae51c.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.804 · seed 0** （12 步，唯一 URL 5）
  - 目标：Assign the issue regarding flash alerts to myself and primer.
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/-/issues', '/issues']
  - 证据：末尾 URL http://localhost:8023/help/user/packages/package_registry/index
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T140510Z_browsergym_webarena.804_seed0_dcd42e4b.jsonl

## 候选缺失/语义失配（`candidate_missing`，227 条）

归属模块：候选生成（候选集合未包含目标元素）

- **round2/gitlab/world-model/guard_off · browsergym/webarena.524 · seed 0** （12 步，唯一 URL 6）
  - 目标：Star the top eight most stared repos in Gitlab
  - 证据：0/12 步所选动作与当前子目标意图不兼容，9/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 8, 'reactive': 4}
  - 证据：高频点击目标 ['Help', 'D', 'Star', 'Merge requests']
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'D', 'Star', 'Merge requests', 'Byte Blaze', 'Milestones']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T181351Z_browsergym_webarena.524_seed0_70105e4c.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.411 · seed 0** （12 步，唯一 URL 5）
  - 目标：Make the LICENSE of byteblaze/cloud-to-butt to MIT license.
  - 证据：0/12 步所选动作与当前子目标意图不兼容，6/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 7, 'reactive': 5}
  - 证据：高频点击目标 ['LICENSE', 'Add a link (Ctrl+K)', 'D', 'MIT License']
  - 动作类型：{'click': 12}
  - 高频点击：['LICENSE', 'Add a link (Ctrl+K)', 'D', 'MIT License', 'Add license', 'Write']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T181527Z_browsergym_webarena.411_seed0_c1f823aa.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.422 · seed 0** （12 步，唯一 URL 6）
  - 目标：Set my gitlab status as Out of Office.
  - 证据：0/12 步所选动作与当前子目标意图不兼容，6/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 7, 'reactive': 5}
  - 证据：高频点击目标 ['Mark as done', 'A', 'Find file', 'Issues']
  - 动作类型：{'click': 12}
  - 高频点击：['Mark as done', 'A', 'Find file', 'Issues', 'To-Do List', 'To Do 0']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T181931Z_browsergym_webarena.422_seed0_c48bb242.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.537 · seed 0** （12 步，唯一 URL 7）
  - 目标：Follow ['Jakub Klinkovsk', 'convexegg', 'Vinta Chen', 'yjlou', 'Abishek S'] on Gitlab
  - 证据：0/12 步所选动作与当前子目标意图不兼容，11/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 8, 'reactive': 4}
  - 证据：高频点击目标 ['To Do 0', 'A', 'Find file', 'Issues']
  - 动作类型：{'click': 12}
  - 高频点击：['To Do 0', 'A', 'Find file', 'Issues', 'Merge requests', 'To-Do List']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T182726Z_browsergym_webarena.537_seed0_4392ab7c.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.418 · seed 0** （12 步，唯一 URL 8）
  - 目标：Set my gitlab status as Busy.
  - 证据：0/12 步所选动作与当前子目标意图不兼容，8/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 7, 'reactive': 5}
  - 证据：高频点击目标 ['Help', 'A', 'CONTRIBUTING', 'To-Do List']
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'A', 'CONTRIBUTING', 'To-Do List', 'To Do 0', 'Done 7']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T183518Z_browsergym_webarena.418_seed0_913bc236.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.397 · seed 0** （12 步，唯一 URL 7）
  - 目标：Fork MetaSeq.
  - 证据：0/12 步所选动作与当前子目标意图不兼容，9/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 8, 'reactive': 4}
  - 证据：高频点击目标 ['Help', 'To-Do List', 'A', 'Fork']
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'To-Do List', 'A', 'Fork', 'Fork project', 'Issues']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T184010Z_browsergym_webarena.397_seed0_d946a147.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.448 · seed 0** （12 步，唯一 URL 8）
  - 目标：set the homepage URL on my GitLab profile to https://egg.tart.com
  - 证据：0/12 步所选动作与当前子目标意图不兼容，6/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 7, 'reactive': 5}
  - 证据：高频点击目标 ['Help', 'A', 'CONTRIBUTING', 'To-Do List']
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'A', 'CONTRIBUTING', 'To-Do List', 'Use GitLab', 'Analyze GitLab usage']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T184312Z_browsergym_webarena.448_seed0_8698b1c1.jsonl
- **round2/gitlab/world-model/guard_off · browsergym/webarena.293 · seed 0** （12 步，唯一 URL 6）
  - 目标：Show me the command to clone Super_Awesome_Robot with SSH.
  - 证据：0/12 步所选动作与当前子目标意图不兼容，10/12 步语义重叠为 0
  - 证据：候选来源分布 {'structure': 9, 'reactive': 3}
  - 证据：高频点击目标 ['Help', 'D', 'Clone', 'Merge requests']
  - 动作类型：{'click': 12}
  - 高频点击：['Help', 'D', 'Clone', 'Merge requests', 'Byte Blaze', 'Edit profile']
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_off/world-model/20260814T184458Z_browsergym_webarena.293_seed0_82da44a7.jsonl

## 预算耗尽（`budget_exhausted`，299 条）

归属模块：候选优先级与探索效率

- **round2/gitlab/reactive/guard_off · browsergym/webarena.422 · seed 0** （12 步，唯一 URL 3）
  - 目标：Set my gitlab status as Out of Office.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T133947Z_browsergym_webarena.422_seed0_212290ad.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.136 · seed 0** （12 步，唯一 URL 4）
  - 目标：How many commits did Steven Woodson make to a11y-webring.club on 2/6/2023?
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T134227Z_browsergym_webarena.136_seed0_60d66f82.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.755 · seed 0** （12 步，唯一 URL 5）
  - 目标：Create a private HTML repository called "web_agent_index" using the right template to speed up development.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135221Z_browsergym_webarena.755_seed0_7acb8a62.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.418 · seed 0** （12 步，唯一 URL 3）
  - 目标：Set my gitlab status as Busy.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T135432Z_browsergym_webarena.418_seed0_5ee73eee.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.448 · seed 0** （12 步，唯一 URL 3）
  - 目标：set the homepage URL on my GitLab profile to https://egg.tart.com
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T140200Z_browsergym_webarena.448_seed0_8b22ce92.jsonl
- **round2/gitlab/reactive/guard_off · browsergym/webarena.293 · seed 0** （12 步，唯一 URL 3）
  - 目标：Show me the command to clone Super_Awesome_Robot with SSH.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_off/reactive/20260814T140357Z_browsergym_webarena.293_seed0_6d6fce2d.jsonl
- **round2/gitlab/reactive/guard_on · browsergym/webarena.411 · seed 0** （12 步，唯一 URL 7）
  - 目标：Make the LICENSE of byteblaze/cloud-to-butt to MIT license.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_on/reactive/20260814T141019Z_browsergym_webarena.411_seed0_122dfac2.jsonl
- **round2/gitlab/reactive/guard_on · browsergym/webarena.422 · seed 0** （12 步，唯一 URL 3）
  - 目标：Set my gitlab status as Out of Office.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_on/reactive/20260814T141338Z_browsergym_webarena.422_seed0_ab3044f3.jsonl

## 目标理解偏差（`task_understanding`，12 条）

归属模块：任务解析与子目标分解

- **round2/gitlab/reactive/guard_on · browsergym/webarena.341 · seed 0** （2 步，唯一 URL 2）
  - 目标：List all opened issues requesting new features
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_on/reactive/20260814T141159Z_browsergym_webarena.341_seed0_aebd8024.jsonl
- **round2/gitlab/reactive/guard_on · browsergym/webarena.669 · seed 0** （2 步，唯一 URL 2）
  - 目标：Open a new issue to discuss the implementation of dark mode
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/reactive_guard_on/reactive/20260814T142543Z_browsergym_webarena.669_seed0_d286fcff.jsonl
- **round2/gitlab/world-model/guard_on · browsergym/webarena.341 · seed 0** （2 步，唯一 URL 2）
  - 目标：List all opened issues requesting new features
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_on/world-model/20260814T185329Z_browsergym_webarena.341_seed0_e2253851.jsonl
- **round2/gitlab/world-model/guard_on · browsergym/webarena.669 · seed 0** （2 步，唯一 URL 2）
  - 目标：Open a new issue to discuss the implementation of dark mode
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round2_holdout/gitlab/world-model_guard_on/world-model/20260814T190744Z_browsergym_webarena.669_seed0_846d6f1e.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.46 · seed 1** （3 步，唯一 URL 3）
  - 目标：Check out the most recent open issues
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 2, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T153758Z_browsergym_webarena.46_seed1_d655fc37.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.670 · seed 0** （2 步，唯一 URL 2）
  - 目标：Open a new issue to discuss the implementation of default plugins for .zsh
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T164404Z_browsergym_webarena.670_seed0_c33a9330.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.670 · seed 1** （2 步，唯一 URL 2）
  - 目标：Open a new issue to discuss the implementation of default plugins for .zsh
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T164414Z_browsergym_webarena.670_seed1_5e312909.jsonl
- **round4/gitlab/reactive/guard_on · browsergym/webarena.670 · seed 2** （2 步，唯一 URL 2）
  - 目标：Open a new issue to discuss the implementation of default plugins for .zsh
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_p0_round4_holdout/gitlab/reactive_guard_on/reactive/20260830T164423Z_browsergym_webarena.670_seed2_5668e45a.jsonl

## 使用说明与局限

- 主类型是「阻塞症状 + 归属模块」，不是根因判定；判断优先级时结合上面的次级信号重叠表。
- 期望 URL 片段表 `SITE_EXPECTATIONS` 是人工维护的启发式规则，新增站点或新流程时补充对应措辞即可，不需要改分类逻辑。
- 分类只读取轨迹里的可观测字段（动作、decision 候选元数据、动作错误、URL、是否提交答案），不读取页面正文，也不做官方评测。
- `budget_exhausted` 是兜底类：动作本身看起来合理、没有明显循环或走错流程，但 12 步预算内没有形成完整操作序列。
- 建议工作流：每次改动策略后用 `--only-round round4` 重跑同一套报告，比较各类型条数与成功率的迁移；某个类型降到接近 0，说明对应模块修好了。
