# WebArena environment

## Verified local environment

The local WSL environment currently provides a real WebArena Reddit service:

- Site: `http://127.0.0.1:9999`
- Environment controller: `http://127.0.0.1:9998`
- BrowserGym task package: `browsergym-webarena==0.14.3`
- Environment package: `webarena-verified==1.2.3`
- Fixed test task: `browsergym/webarena.27`

The fixed-task test has passed both before and after a full Reddit container
reset:

```text
Reset succeeded.
Reward: 1.0
Terminated: True
Truncated: False
WebArena fixed-task evaluation passed.
```

## Commands

Start or check the Reddit environment:

```bash
cd ~/agent_world_model
./scripts/start_webarena.sh
```

Run the BrowserGym reset/action/evaluator smoke test:

```bash
cd ~/agent_world_model
source .venv/bin/activate
source .env.webarena
python test_webarena.py
```

Collect one lightweight Reddit state transition with pruned AXTree and DOM:

```bash
cd ~/agent_world_model
source .venv/bin/activate
source .env.webarena
python scripts/collect_webarena_trajectory.py
```

Run the complete fixed phase-one acceptance suite:

```bash
cd ~/agent_world_model
source .venv/bin/activate
source .env
source .env.webarena
python scripts/run_phase1_baseline.py --suite all
```

The JSONL output is written under `data/trajectories/`; the latest suite report is
`data/reports/phase1_latest.json`. Screenshot pixel arrays are intentionally
omitted, and the state encoder is CPU-only, so the baseline remains suitable for
this laptop.

Reset Reddit to its original populated state:

```bash
cd ~/agent_world_model
./scripts/reset_webarena_reddit.sh
```

## Full benchmark capacity requirement

This computer does not currently have enough safe free disk space for every
WebArena site. The remaining deployment includes Shopping, Shopping Admin,
GitLab, Wikipedia, and Map. Wikipedia and Map alone require approximately
100 GB and 60 GB of external data, in addition to all Docker images.

Use the official WebArena AMI on a server with the recommended resources before
replacing the `todo` values in `.env.webarena` with the remaining site URLs.

The phase-one local acceptance therefore uses the real Reddit service plus the
official evaluator task `browsergym/webarena.27`. It does not claim coverage of
the undeployed Shopping, Shopping Admin, GitLab, Wikipedia or Map services.
