# WebArena 失败归因（动作级）

生成时间：2026-09-12T02:02:20+00:00

覆盖 episode 28 条，其中失败 23 条。分类由可观测轨迹字段推导：执行动作、decision 候选元数据、动作错误、访问 URL、是否提交答案。

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
| `loop_stall` | 循环/停滞 | 循环恢复（loop recovery） | 12 | 52.2% |
| `budget_exhausted` | 预算耗尽 | 候选优先级与探索效率 | 6 | 26.1% |
| `wrong_route` | 流程路径错误 | 站点流程知识（进入目标页面/流程） | 4 | 17.4% |
| `task_understanding` | 目标理解偏差 | 任务解析与子目标分解 | 1 | 4.3% |

## 模块工作量排序（按失败条数）

| 模块 | 失败条数 |
|---|---:|
| 循环恢复（loop recovery） | 12 |
| 候选优先级与探索效率 | 6 |
| 站点流程知识（进入目标页面/流程） | 4 |
| 任务解析与子目标分解 | 1 |

## 各单元格成功率

| 单元格 | 成功/总数 | 成功率 |
|---|---:|---:|
| r3dev-v7/gitlab/reactive/guard_off | 0/9 | 0.0% |
| r3dev-v7/reddit/reactive/guard_off | 1/10 | 10.0% |
| r3dev-v7/shopping/reactive/guard_off | 4/9 | 44.4% |

## 分站点失败类型分布

| 分组 | 循环/停滞 | 元素定位失败 | 动作执行失败 | 缺显式终止 | 表单/搜索流程不完整 | 流程路径错误 | 候选缺失/语义失配 | 预算耗尽 | 目标理解偏差 | 评测/环境异常 | 失败合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gitlab | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 2 | 1 | 0 | 9 |
| reddit | 5 | 0 | 0 | 0 | 0 | 1 | 0 | 3 | 0 | 0 | 9 |
| shopping | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 5 |

## 分轮次失败类型分布

| 分组 | 循环/停滞 | 元素定位失败 | 动作执行失败 | 缺显式终止 | 表单/搜索流程不完整 | 流程路径错误 | 候选缺失/语义失配 | 预算耗尽 | 目标理解偏差 | 评测/环境异常 | 失败合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| r3dev-v7 | 12 | 0 | 0 | 0 | 0 | 4 | 0 | 6 | 1 | 0 | 23 |

## 主类型 × 次级信号重叠

分类给每条失败 episode 一个**主类型**（阻塞症状），这里再看它同时具备哪些次级信号，用来区分「症状」和「根因」：例如 `loop_stall` 里有多大比例其实是在反复点击语义无关的控件。

| 主类型 | 失败条数 | 候选语义失配 | 存在重复动作 | 目标需要输入但从未输入 | 有动作报错 |
|---|---:|---:|---:|---:|---:|
| 循环/停滞 (`loop_stall`) | 12 | 0 (0%) | 10 (83%) | 6 (50%) | 3 (25%) |
| 流程路径错误 (`wrong_route`) | 4 | 0 (0%) | 1 (25%) | 2 (50%) | 2 (50%) |
| 预算耗尽 (`budget_exhausted`) | 6 | 0 (0%) | 0 (0%) | 3 (50%) | 5 (83%) |
| 目标理解偏差 (`task_understanding`) | 1 | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |

## 失败时高频点击的元素（每条约取前 3 个高频目标统计）

用于判断候选集合是否把无关控件排到了前面：


### 分站点高频误点元素


## 循环/停滞（`loop_stall`，12 条）

归属模块：循环恢复（loop recovery）

- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.484 · seed 0** （12 步，唯一 URL 2）
  - 目标：Jakub Klinkovský wants to check my dotfile configurations. Please invite him to the repo as a guest.
  - 证据：重复动作 4 步，唯一 URL 数 2
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103224Z_browsergym_webarena.484_seed0_70d62334.jsonl
- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.349 · seed 0** （12 步，唯一 URL 2）
  - 目标：Who else have access to my repo gimmiethat.space, show me their usernames
  - 证据：重复动作 3 步，唯一 URL 数 2
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103459Z_browsergym_webarena.349_seed0_b59c4b13.jsonl
- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.788 · seed 0** （12 步，唯一 URL 3）
  - 目标：Tell me the full name, gitlab account name, location and email address of the contributor who has the most commits to branch php52
  - 证据：重复动作 6 步，唯一 URL 数 3
  - 动作类型：{'scroll': 8, 'click': 4}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103817Z_browsergym_webarena.788_seed0_dccb140f.jsonl
- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.417 · seed 0** （12 步，唯一 URL 4）
  - 目标：Go to the merge request on 404 link I have to review, find if the author of the merge request responded at the end, and reply "Thank you" if he did. Otherwise remind him with a simple @.
  - 证据：重复动作 10 步，唯一 URL 数 4
  - 动作类型：{'fill': 6, 'keyboard_press': 6}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103923Z_browsergym_webarena.417_seed0_60eb3d5c.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.722 · seed 0** （12 步，唯一 URL 2）
  - 目标：Like all submissions created by Don_Gato1 in subreddit new york
  - 证据：重复动作 8 步，唯一 URL 数 2
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104138Z_browsergym_webarena.722_seed0_dae99611.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.631 · seed 0** （12 步，唯一 URL 2）
  - 目标：Ask for product recommendations for running shoes within a budget of $100 in r/sports
  - 证据：重复动作 9 步，唯一 URL 数 2
  - 动作类型：{'fill': 6, 'keyboard_press': 6}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104557Z_browsergym_webarena.631_seed0_7cba4a6d.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.632 · seed 0** （12 步，唯一 URL 2）
  - 目标：Ask for product recommendations for running shoes within a budget of $500 in r/sports
  - 证据：重复动作 9 步，唯一 URL 数 2
  - 动作类型：{'fill': 6, 'keyboard_press': 6}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104729Z_browsergym_webarena.632_seed0_90a50890.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.613 · seed 0** （12 步，唯一 URL 3）
  - 目标：Post a review of my recent reading "Love story" in the r/books with my comment "I cried".
  - 证据：重复动作 9 步，唯一 URL 数 3
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104900Z_browsergym_webarena.613_seed0_3d21a592.jsonl

## 流程路径错误（`wrong_route`，4 条）

归属模块：站点流程知识（进入目标页面/流程）

- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.593 · seed 0** （12 步，唯一 URL 4）
  - 目标：Create a milestone for the upcoming task of merging all branches to main starting on March 15, 2044 and ending on March 30, 2044
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/-/milestones', '/milestones']
  - 证据：末尾 URL http://localhost:8023/byteblaze/a11y-syntax-highlighting/-/issues
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103743Z_browsergym_webarena.593_seed0_318f3639.jsonl
- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.308 · seed 0** （12 步，唯一 URL 4）
  - 目标：Tell me who has made the most contributions, in terms of number of commits, to the primer/design project
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/commits', '/-/commits']
  - 证据：末尾 URL http://localhost:8023/primer/design
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103849Z_browsergym_webarena.308_seed0_79f173d7.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.628 · seed 0** （1 步，唯一 URL 2）
  - 目标：Create a discussion post about "long distance relationship" in a relevant subreddit and ask users for their opinions with the simple prompt, "your opinion"
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/user/', '/u/']
  - 证据：末尾 URL https://www.forbes.com/sites/jerylbrunner/2023/02/26/after-two-decades-and-38-childrens-books-lin-oliver-continues-her-thriving-collaboration-with-henry-winkler/?sh=7fd671c16e63
  - 动作类型：{'click': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104531Z_browsergym_webarena.628_seed0_9791b2ba.jsonl
- **r3dev-v7/shopping/reactive/guard_off · browsergym/webarena.657 · seed 0** （12 步，唯一 URL 4）
  - 目标：Fill the "contact us" form in the site for a refund on the speaker I bought, stating that it broke after just three days of use. Also, ensure to include the order number #148 and the product SKU. Don't submit yet, I will check.
  - 证据：整条轨迹从未到达目标流程页面（只在外围页面活动）
  - 证据：期望 URL 片段 ['/sales/order', '/order/', '/orders']
  - 证据：末尾 URL http://localhost:7770/nano-facial-mister-mini-facial-steamer-handy-moisturizing-mist-sprayer-atomization-skin-care-steamer-usb-rechargeable-you-may-receive-defective-products-please-feel-free-to-contact-us.html
  - 动作类型：{'scroll': 5, 'click': 5, 'fill': 1, 'keyboard_press': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/shopping/reactive/reactive/20260819T105304Z_browsergym_webarena.657_seed0_b424eaaa.jsonl

## 预算耗尽（`budget_exhausted`，6 条）

归属模块：候选优先级与探索效率

- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.172 · seed 0** （12 步，唯一 URL 6）
  - 目标：Tell me the full names of the repositories where I made contributions and they got no stars?
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 10, 'scroll': 2}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103427Z_browsergym_webarena.172_seed0_be90b602.jsonl
- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.743 · seed 0** （12 步，唯一 URL 5）
  - 目标：Create a new public project "web_arena" and add Abishek, Vinta as members
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 11, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103532Z_browsergym_webarena.743_seed0_ae3ce06d.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.404 · seed 0** （12 步，唯一 URL 4）
  - 目标：Upvote the newest post in books subreddit
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 9, 'fill': 1, 'keyboard_press': 1, 'scroll': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104301Z_browsergym_webarena.404_seed0_882904cc.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.621 · seed 0** （1 步，唯一 URL 2）
  - 目标：Ask for advice about cheat in a subreddit for relations
  - 证据：达到 1 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104454Z_browsergym_webarena.621_seed0_a694e11e.jsonl
- **r3dev-v7/reddit/reactive/guard_off · browsergym/webarena.602 · seed 0** （1 步，唯一 URL 2）
  - 目标：Post my question, "places for new drivers to learn driving in pittsburgh", in a subreddit where I'm likely to get an answer
  - 证据：达到 1 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/reddit/reactive/reactive/20260819T104544Z_browsergym_webarena.602_seed0_a9cb7487.jsonl
- **r3dev-v7/shopping/reactive/guard_off · browsergym/webarena.286 · seed 0** （12 步，唯一 URL 6）
  - 目标：Show the least expensive ssd hard drive with a minimum storage capacity of 1TB.
  - 证据：达到 12 步预算且从未提交答案
  - 证据：高频点击目标 []
  - 动作类型：{'click': 12}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/shopping/reactive/reactive/20260819T105621Z_browsergym_webarena.286_seed0_086fa2fa.jsonl

## 目标理解偏差（`task_understanding`，1 条）

归属模块：任务解析与子目标分解

- **r3dev-v7/gitlab/reactive/guard_off · browsergym/webarena.342 · seed 0** （2 步，唯一 URL 2）
  - 目标：List all opened issues that ask about OPT model related questions
  - 证据：动作可执行但未形成满足任务的完整操作序列
  - 动作类型：{'click': 1, 'send_msg_to_user': 1}
  - 轨迹：/home/filp/agent_world_model/data/trajectories_webarena_r3dev_v7/gitlab/reactive/reactive/20260819T103407Z_browsergym_webarena.342_seed0_c2d57127.jsonl

## 使用说明与局限

- 主类型是「阻塞症状 + 归属模块」，不是根因判定；判断优先级时结合上面的次级信号重叠表。
- 期望 URL 片段表 `SITE_EXPECTATIONS` 是人工维护的启发式规则，新增站点或新流程时补充对应措辞即可，不需要改分类逻辑。
- 分类只读取轨迹里的可观测字段（动作、decision 候选元数据、动作错误、URL、是否提交答案），不读取页面正文，也不做官方评测。
- `budget_exhausted` 是兜底类：动作本身看起来合理、没有明显循环或走错流程，但 12 步预算内没有形成完整操作序列。
- 建议工作流：每次改动策略后用 `--only-round round4` 重跑同一套报告，比较各类型条数与成功率的迁移；某个类型降到接近 0，说明对应模块修好了。
