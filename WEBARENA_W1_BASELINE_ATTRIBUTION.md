# WebArena 失败归因（动作级）

生成时间：2026-09-12T10:03:13+00:00

覆盖 episode 120 条，其中失败 117 条。分类由可观测轨迹字段推导：执行动作、decision 候选元数据、动作错误、访问 URL、是否提交答案。

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
| `loop_stall` | 循环/停滞 | 循环恢复（loop recovery） | 42 | 35.9% |
| `budget_exhausted` | 预算耗尽 | 候选优先级与探索效率 | 38 | 32.5% |
| `wrong_route` | 流程路径错误 | 站点流程知识（进入目标页面/流程） | 23 | 19.7% |
| `task_understanding` | 目标理解偏差 | 任务解析与子目标分解 | 6 | 5.1% |
| `missing_termination` | 缺显式终止 | 终止策略（观察态已满足但未提交答案） | 3 | 2.6% |
| `form_or_search_incomplete` | 表单/搜索流程不完整 | 表单与搜索模块（构造查询、提交、校验） | 3 | 2.6% |
| `action_execution` | 动作执行失败 | 动作执行鲁棒性（超时、重试、等待策略） | 2 | 1.7% |

## 模块工作量排序（按失败条数）

| 模块 | 失败条数 |
|---|---:|
| 循环恢复（loop recovery） | 42 |
| 候选优先级与探索效率 | 38 |
| 站点流程知识（进入目标页面/流程） | 23 |
| 任务解析与子目标分解 | 6 |
| 终止策略（观察态已满足但未提交答案） | 3 |
| 表单与搜索模块（构造查询、提交、校验） | 3 |
| 动作执行鲁棒性（超时、重试、等待策略） | 2 |

## 各单元格成功率

| 单元格 | 成功/总数 | 成功率 |
|---|---:|---:|
| w1-workingset/gitlab/reactive/guard_on | 0/69 | 0.0% |
| w1-workingset/shopping/reactive/guard_on | 3/51 | 5.9% |

## 分站点失败类型分布

| 分组 | 循环/停滞 | 元素定位失败 | 动作执行失败 | 缺显式终止 | 表单/搜索流程不完整 | 流程路径错误 | 候选缺失/语义失配 | 预算耗尽 | 目标理解偏差 | 评测/环境异常 | 失败合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gitlab | 34 | 0 | 1 | 3 | 0 | 6 | 0 | 22 | 3 | 0 | 69 |
| shopping | 8 | 0 | 1 | 0 | 3 | 17 | 0 | 16 | 3 | 0 | 48 |

## 分轮次失败类型分布

| 分组 | 循环/停滞 | 元素定位失败 | 动作执行失败 | 缺显式终止 | 表单/搜索流程不完整 | 流程路径错误 | 候选缺失/语义失配 | 预算耗尽 | 目标理解偏差 | 评测/环境异常 | 失败合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| w1-workingset | 42 | 0 | 2 | 3 | 3 | 23 | 0 | 38 | 6 | 0 | 117 |

## 主类型 × 次级信号重叠

分类给每条失败 episode 一个**主类型**（阻塞症状），这里再看它同时具备哪些次级信号，用来区分「症状」和「根因」：例如 `loop_stall` 里有多大比例其实是在反复点击语义无关的控件。

| 主类型 | 失败条数 | 候选语义失配 | 存在重复动作 | 目标需要输入但从未输入 | 有动作报错 |
|---|---:|---:|---:|---:|---:|
| 循环/停滞 (`loop_stall`) | 42 | 0 (0%) | 42 (100%) | 22 (52%) | 5 (12%) |
| 动作执行失败 (`action_execution`) | 2 | 0 (0%) | 2 (100%) | 0 (0%) | 2 (100%) |
| 缺显式终止 (`missing_termination`) | 3 | 0 (0%) | 3 (100%) | 0 (0%) | 3 (100%) |
| 表单/搜索流程不完整 (`form_or_search_incomplete`) | 3 | 0 (0%) | 3 (100%) | 3 (100%) | 0 (0%) |
| 流程路径错误 (`wrong_route`) | 23 | 0 (0%) | 14 (61%) | 6 (26%) | 5 (22%) |
| 预算耗尽 (`budget_exhausted`) | 38 | 0 (0%) | 0 (0%) | 29 (76%) | 19 (50%) |
| 目标理解偏差 (`task_understanding`) | 6 | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |

## 失败时高频点击的元素（每条约取前 3 个高频目标统计）

用于判断候选集合是否把无关控件排到了前面：


### 分站点高频误点元素


## 循环/停滞（`loop_stall`，42 条）

归属模块：循环恢复（loop recovery）

- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.106 · seed 1** （12 步，唯一 URL 2）
  - 目标：Display the list of issues in the umano/AndroidSlidingUpPanel repository that have labels related to BUG
  - 证据：重复动作 9 步，唯一 URL 数 2
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054720Z_browsergym_webarena.106_seed1_366f7650.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.106 · seed 2** （12 步，唯一 URL 2）
  - 目标：Display the list of issues in the umano/AndroidSlidingUpPanel repository that have labels related to BUG
  - 证据：重复动作 10 步，唯一 URL 数 2
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054754Z_browsergym_webarena.106_seed2_d5801e7f.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.294 · seed 0** （12 步，唯一 URL 2）
  - 目标：Show me the command to clone ChatGPT with SSH.
  - 证据：重复动作 6 步，唯一 URL 数 2
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055321Z_browsergym_webarena.294_seed0_82c69000.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.294 · seed 1** （12 步，唯一 URL 2）
  - 目标：Show me the command to clone ChatGPT with SSH.
  - 证据：重复动作 6 步，唯一 URL 数 2
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055353Z_browsergym_webarena.294_seed1_a27b047f.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.294 · seed 2** （12 步，唯一 URL 2）
  - 目标：Show me the command to clone ChatGPT with SSH.
  - 证据：重复动作 6 步，唯一 URL 数 2
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055425Z_browsergym_webarena.294_seed2_ee80d920.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.303 · seed 0** （12 步，唯一 URL 3）
  - 目标：How many commits did Kilian make durning 2023?
  - 证据：重复动作 6 步，唯一 URL 数 3
  - 动作类型：{'scroll': 8, 'click': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055457Z_browsergym_webarena.303_seed0_5b23f02d.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.303 · seed 1** （12 步，唯一 URL 3）
  - 目标：How many commits did Kilian make durning 2023?
  - 证据：重复动作 7 步，唯一 URL 数 3
  - 动作类型：{'scroll': 8, 'click': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055529Z_browsergym_webarena.303_seed1_039a8a38.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.303 · seed 2** （12 步，唯一 URL 3）
  - 目标：How many commits did Kilian make durning 2023?
  - 证据：重复动作 6 步，唯一 URL 数 3
  - 动作类型：{'scroll': 8, 'click': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055600Z_browsergym_webarena.303_seed2_1cb02c7b.jsonl

## 动作执行失败（`action_execution`，2 条）

归属模块：动作执行鲁棒性（超时、重试、等待策略）

- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.106 · seed 0** （12 步，唯一 URL 2）
  - 目标：Display the list of issues in the umano/AndroidSlidingUpPanel repository that have labels related to BUG
  - 证据：5/12 步动作执行报错，其中超时 5 步
  - 动作类型：{'click': 8, 'scroll': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054645Z_browsergym_webarena.106_seed0_9e5561f8.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.467 · seed 0** （12 步，唯一 URL 6）
  - 目标：Add HONGJ Hawaiian Beach Outfits Set for Mens, Summer Tropical Tree Printed Relaxed-fit Hawaii Shirts Shorts 2 Piece Suits to my wish list
  - 证据：4/12 步动作执行报错，其中超时 4 步
  - 动作类型：{'click': 6, 'scroll': 4, 'fill': 1, 'keyboard_press': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T072841Z_browsergym_webarena.467_seed0_3f2b796c.jsonl

## 缺显式终止（`missing_termination`，3 条）

归属模块：终止策略（观察态已满足但未提交答案）

- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.133 · seed 0** （12 步，唯一 URL 3）
  - 目标：How many commits did Eric make to a11yproject on 3/2?
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/commits', '/-/commits']，末尾 URL http://localhost:8023/byteblaze/dotfiles/-/commits/main
  - 动作类型：{'click': 8, 'scroll': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054959Z_browsergym_webarena.133_seed0_22024579.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.133 · seed 1** （12 步，唯一 URL 3）
  - 目标：How many commits did Eric make to a11yproject on 3/2?
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/commits', '/-/commits']，末尾 URL http://localhost:8023/byteblaze/dotfiles/-/commits/main
  - 动作类型：{'click': 9, 'scroll': 3}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055035Z_browsergym_webarena.133_seed1_56257d41.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.133 · seed 2** （12 步，唯一 URL 3）
  - 目标：How many commits did Eric make to a11yproject on 3/2?
  - 证据：轨迹结束在目标流程页面上，但从未显式提交答案
  - 证据：期望 URL 片段 ['/commits', '/-/commits']，末尾 URL http://localhost:8023/byteblaze/dotfiles/-/commits/main
  - 动作类型：{'click': 10, 'scroll': 2}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055111Z_browsergym_webarena.133_seed2_f10540ee.jsonl

## 表单/搜索流程不完整（`form_or_search_incomplete`，3 条）

归属模块：表单与搜索模块（构造查询、提交、校验）

- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.573 · seed 0** （12 步，唯一 URL 5）
  - 目标：I recently moved, my address is 987 Sycamore Circle, Philadelphia, PA, 19102, update my information on OneStopShopping accordingly
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:7770/customer/address/
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T074017Z_browsergym_webarena.573_seed0_d94bd004.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.573 · seed 1** （12 步，唯一 URL 5）
  - 目标：I recently moved, my address is 987 Sycamore Circle, Philadelphia, PA, 19102, update my information on OneStopShopping accordingly
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:7770/customer/address/
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T074244Z_browsergym_webarena.573_seed1_9036d1f3.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.573 · seed 2** （12 步，唯一 URL 5）
  - 目标：I recently moved, my address is 987 Sycamore Circle, Philadelphia, PA, 19102, update my information on OneStopShopping accordingly
  - 证据：轨迹停在需要输入的目标页面上，但从未执行 fill/type/select 也未回车提交
  - 证据：动作类型分布 {'click': 12}
  - 证据：末尾 URL http://localhost:7770/customer/address/
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T074511Z_browsergym_webarena.573_seed2_3d93c833.jsonl

## 流程路径错误（`wrong_route`，23 条）

归属模块：站点流程知识（进入目标页面/流程）

- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.132 · seed 0** （12 步，唯一 URL 3）
  - 目标：How many commits did kilian make to a11yproject on 3/5/2023?
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/commits', '/-/commits']
  - 证据：末尾 URL http://localhost:8023/byteblaze/dotfiles/-/wikis/home
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054828Z_browsergym_webarena.132_seed0_f97b43db.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.132 · seed 1** （12 步，唯一 URL 3）
  - 目标：How many commits did kilian make to a11yproject on 3/5/2023?
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/commits', '/-/commits']
  - 证据：末尾 URL http://localhost:8023/byteblaze/dotfiles/-/wikis/home
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054859Z_browsergym_webarena.132_seed1_52949c25.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.132 · seed 2** （12 步，唯一 URL 3）
  - 目标：How many commits did kilian make to a11yproject on 3/5/2023?
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/commits', '/-/commits']
  - 证据：末尾 URL http://localhost:8023/byteblaze/dotfiles/-/wikis/home
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T054929Z_browsergym_webarena.132_seed2_38023732.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.567 · seed 0** （12 步，唯一 URL 6）
  - 目标：Invite Jakub Klinkovský and Benoît Blanchon as collaborator to gimmiethat.space repo
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/project_members', '/-/project_members', '/members']
  - 证据：末尾 URL http://localhost:8023/help/user/packages/workflows/project_registry.md
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T062404Z_browsergym_webarena.567_seed0_286a11b8.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.567 · seed 1** （12 步，唯一 URL 6）
  - 目标：Invite Jakub Klinkovský and Benoît Blanchon as collaborator to gimmiethat.space repo
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/project_members', '/-/project_members', '/members']
  - 证据：末尾 URL http://localhost:8023/help/user/packages/workflows/project_registry.md
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T062532Z_browsergym_webarena.567_seed1_03e8cd7c.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.567 · seed 2** （12 步，唯一 URL 6）
  - 目标：Invite Jakub Klinkovský and Benoît Blanchon as collaborator to gimmiethat.space repo
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/project_members', '/-/project_members', '/members']
  - 证据：末尾 URL http://localhost:8023/help/user/packages/workflows/project_registry.md
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T062703Z_browsergym_webarena.567_seed2_7df77530.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.299 · seed 0** （12 步，唯一 URL 3）
  - 目标：Show the most recent cancelled order
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/sales/order', '/order/', '/orders']
  - 证据：末尾 URL http://localhost:7770/belle-of-the-ball-princess-sprinkle-mix-wedding-colorful-sprinkles-cake-cupcake-cookie-sprinkles-ice-cream-candy-sprinkles-yellow-gold-red-royal-red-rose-icing-flowers-decorating-sprinkles-8oz.html
  - 动作类型：{'click': 6, 'scroll': 6}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T072330Z_browsergym_webarena.299_seed0_eec73d5c.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.299 · seed 1** （12 步，唯一 URL 4）
  - 目标：Show the most recent cancelled order
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/sales/order', '/order/', '/orders']
  - 证据：末尾 URL http://localhost:7770/
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T072404Z_browsergym_webarena.299_seed1_3e28a018.jsonl

## 预算耗尽（`budget_exhausted`，38 条）

归属模块：候选优先级与探索效率

- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.170 · seed 0** （12 步，唯一 URL 6）
  - 目标：Tell me the full names of the repositories where I made contributions and they got the least stars?
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055147Z_browsergym_webarena.170_seed0_a58becbc.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.170 · seed 1** （12 步，唯一 URL 6）
  - 目标：Tell me the full names of the repositories where I made contributions and they got the least stars?
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055219Z_browsergym_webarena.170_seed1_83436919.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.170 · seed 2** （12 步，唯一 URL 6）
  - 目标：Tell me the full names of the repositories where I made contributions and they got the least stars?
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055250Z_browsergym_webarena.170_seed2_b12e0578.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.412 · seed 0** （12 步，唯一 URL 5）
  - 目标：Make the LICENSE of byteblaze/accessible-html-content-patterns to Apache License
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055834Z_browsergym_webarena.412_seed0_e6c972a9.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.412 · seed 1** （12 步，唯一 URL 5）
  - 目标：Make the LICENSE of byteblaze/accessible-html-content-patterns to Apache License
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T060005Z_browsergym_webarena.412_seed1_7d5a172c.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.412 · seed 2** （12 步，唯一 URL 5）
  - 目标：Make the LICENSE of byteblaze/accessible-html-content-patterns to Apache License
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T060135Z_browsergym_webarena.412_seed2_e26aa49f.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.419 · seed 0** （12 步，唯一 URL 2）
  - 目标：Set my gitlab status as Enjoying life.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T060729Z_browsergym_webarena.419_seed0_1c047b14.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.744 · seed 0** （12 步，唯一 URL 5）
  - 目标：Create a new public project "AutoAGI" and add primer as members
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T063013Z_browsergym_webarena.744_seed0_6def0871.jsonl

## 目标理解偏差（`task_understanding`，6 条）

归属模块：任务解析与子目标分解

- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.340 · seed 0** （2 步，唯一 URL 2）
  - 目标：List all opened issues that report bugs
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055802Z_browsergym_webarena.340_seed0_d1113ed7.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.340 · seed 1** （2 步，唯一 URL 2）
  - 目标：List all opened issues that report bugs
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055812Z_browsergym_webarena.340_seed1_5412078e.jsonl
- **w1-workingset/gitlab/reactive/guard_on · browsergym/webarena.340 · seed 2** （2 步，唯一 URL 2）
  - 目标：List all opened issues that report bugs
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/gitlab/reactive/reactive/20260912T055823Z_browsergym_webarena.340_seed2_23a5723b.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.192 · seed 0** （3 步，唯一 URL 3）
  - 目标：Tell me the total cost of my latest non-cancelled order?
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 2, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T071546Z_browsergym_webarena.192_seed0_1e280880.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.192 · seed 1** （3 步，唯一 URL 3）
  - 目标：Tell me the total cost of my latest non-cancelled order?
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 2, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T071559Z_browsergym_webarena.192_seed1_92e5eba0.jsonl
- **w1-workingset/shopping/reactive/guard_on · browsergym/webarena.192 · seed 2** （3 步，唯一 URL 3）
  - 目标：Tell me the total cost of my latest non-cancelled order?
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 2, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_w1_workingset/shopping/reactive/reactive/20260912T071613Z_browsergym_webarena.192_seed2_af37b06b.jsonl

## 使用说明与局限

- 主类型是「阻塞症状 + 归属模块」，不是根因判定；判断优先级时结合上面的次级信号重叠表。
- 期望 URL 片段表 `SITE_EXPECTATIONS` 是人工维护的启发式规则，新增站点或新流程时补充对应措辞即可，不需要改分类逻辑。
- 分类只读取轨迹里的可观测字段（动作、decision 候选元数据、动作错误、URL、是否提交答案），不读取页面正文，也不做官方评测。
- `budget_exhausted` 是兜底类：动作本身看起来合理、没有明显循环或走错流程，但 12 步预算内没有形成完整操作序列。
- 建议工作流：每次改动策略后用 `--only-round round4` 重跑同一套报告，比较各类型条数与成功率的迁移；某个类型降到接近 0，说明对应模块修好了。
