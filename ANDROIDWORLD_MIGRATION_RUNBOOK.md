# AndroidWorld small-scale migration runbook

AndroidWorld is a phase-two/three portability check, not the primary training
environment.  The official benchmark currently requires Python 3.11+, an
Android 13 / API 33 emulator, `adb`, and an emulator launched with the gRPC
forwarding flag `-grpc 8554`.

Official setup: <https://github.com/google-research/android_world#installation>

## 1. Pick the runtime topology

- If `scripts/androidworld_preflight.py` reports `/dev/kvm` and a working
  emulator, the benchmark can run on that Linux host.
- Most rented GPU containers do not expose nested virtualization.  In that
  case, run Android Studio/emulator on the Windows workstation and keep the
  world-model inference service on the GPU server.  The repository's
  `androidworld_adapter.py` converts the local UI hierarchy into the common
  state/action schema.
- The official Docker path is experimental and still requires privileged
  container support; it is not evidence of a completed migration until a real
  task result is recorded.

The AutoDL GPU container checked on 2026-08-10 exposes CPU virtualization flags
but not `/dev/kvm`, `/dev/binder*`, Docker, or a connected Android device.  It
can host the AndroidWorld Python/control stack and GPU inference, but it cannot
be treated as an accelerated emulator host.  Software emulation is retained as
a diagnostic-only fallback because it may be too slow for benchmark evidence.

The same container now has the official AndroidWorld 0.1.0 package, Android
SDK/emulator, a Pixel 6 Android 13/API 33 image and AVD installed under
`/root/autodl-tmp`.  A real software-emulated device reached `adb state=device`
and `sys.boot_completed=1`; API level, emulator gRPC 8554 and the Android guest
route to `10.0.2.2` passed the repository preflight.  This is runtime evidence,
not task-success evidence, because `/dev/kvm` is still unavailable.

On 2026-08-11 a real `reset -> action -> state` smoke passed on the software-
emulated device: `androidworld_smoke_latest.json` reports `status: passed`,
`real_environment_reset: true`, `real_action_executed: true`, and an
18-element accessibility tree (Phone, Messages, Chrome, Gmail, Search, Photos,
YouTube, Voice search, Google Lens, ...) was captured before and after the
`wait` action with SHA-256-verified screenshots.  Task-level baseline/planner
comparison remains blocked by the missing `/dev/kvm`, so the migration is not
yet called complete.

## 2. Native benchmark prerequisites

1. Create the official Pixel 6 Android 13 (API 33) AVD.
2. Launch it from the command line with `-no-snapshot -grpc 8554`.
3. Confirm `adb devices` reports exactly one target in state `device`.
4. Install `google-research/android_world` in a Python 3.11 environment.
5. Run the official first task with `--perform_emulator_setup` once so apps and
   permissions are installed.

Reproducible Linux preparation in this repository:

```bash
bash ops/install_androidworld_runtime.sh
ANDROIDWORLD_ALLOW_SOFTWARE_EMULATION=1 bash ops/start_androidworld_emulator.sh
python scripts/androidworld_preflight.py \
  --adb-path /root/autodl-tmp/android-sdk/platform-tools/adb
python scripts/androidworld_smoke.py \
  --adb-path /root/autodl-tmp/android-sdk/platform-tools/adb \
  --perform-emulator-setup
```

The `ALLOW_SOFTWARE` flag is only for diagnosing a host without KVM.  For a
real run, expose a KVM-capable Pixel 6/API 33 emulator and tunnel both its ADB
transport and gRPC port 8554 to the Python runtime.

If an API 33 emulator boots but `ip route get 10.0.2.2` reports that the network
is unreachable, inspect the single saved `AndroidWifi` profile before starting
AndroidWorld.  On the verified development AVD, the stale profile was repaired
by enabling root ADB, forgetting that exact network id and reconnecting the
open `AndroidWifi` network.  Re-run `androidworld_preflight.py` afterwards; do
not bypass its host-bridge route check.

Under TCG software emulation the lock screen can stay "showing" even when the
launcher is visible, which makes the accessibility framework return no root
node and crashes the AccessibilityForwarder service (uiautomator reports
"null root node").  On the verified AVD this was fixed once by:

```bash
adb root
adb shell locksettings set-disabled true
adb shell settings put secure lockscreen.disabled 1
adb shell wm dismiss-keyguard
adb shell settings put secure enabled_accessibility_services \
  com.google.androidenv.accessibilityforwarder/com.google.androidenv.accessibilityforwarder.AccessibilityForwarder
adb shell settings put secure accessibility_enabled 1
```

After that the forwarder service must be force-stopped and re-enabled so it
builds a fresh gRPC channel to the host a11y server (an ephemeral port
broadcast by `android_env`), and the smoke can capture a populated tree.

## 5. Task-level evaluation (local WHPX)

On the verified Windows workstation the emulator runs with WHPX hardware
acceleration (`emulator -accel-check` reports WHPX installed and usable), so
task-level runs no longer depend on a KVM host.  The AVD and SDK live under
ASCII-only paths (`C:\AndroidSdk`, `C:\AndroidUser\.android`) because the
emulator mangles non-ASCII user-home paths when spawning QEMU.

Run the deterministic task comparison (no LLM judge; success is read back from
Android settings / foreground activity via ADB):

```powershell
$env:PYTHONIOENCODING="utf-8"
& C:\Users\卢政坤\Android\androidworld-venv\Scripts\python.exe `
  scripts\evaluate_androidworld_tasks.py `
  --adb-path C:\AndroidSdk\platform-tools\adb.exe `
  --tasks wifi_on,wifi_off,open_chrome --episodes 3 --max-steps 10
```

Expanded results (2026-08-12, 7 tasks x 5 episodes, 10-step budget; the two
agents ran on separate fresh emulator boots):

| Task | Reactive baseline | Phase-3 planner |
|---|---:|---:|
| Overall success | 42.9% | 45.7% |
| open_chrome / open_gmail | 100% / 100% | 100% / 100% |
| open_photos | 0% | 100% |
| open_messages | 100% | 0% |
| open_calendar | 0% | 0% |
| wifi_on / wifi_off | 0% / 0% | 20% / 0% |
| Action execution rate | 100% | 100% |
| Avg steps | 10 | 10 |
| Forwarder recoveries | 0 | 2 |
| Sparse-state steps | 10 | 4 |

The planner runs with the opt-in `semantic_goal_priority` rule (an exact-name
candidate overrides the imagined world-model reranking when the goal names a
visible element).  Before that fix the planner failed even on open_chrome (0/3)
because its reranking chose Search over Chrome; after the fix it reaches 100%
on chrome/photos/gmail and completes wifi_on once (1/5).  Calendar remains a
gap for both (its launcher button is not on the default home page), and
Messages is a gap for the planner (12 semantic overrides still did not put the
app in the foreground).  The evaluator now restarts the accessibility
forwarder on failure and retries the episode up to three times; sparse-state
steps and recoveries are reported so environment flakiness is not attributed
to either policy.

Sequence-level Settings navigation (2026-08-12, 5 episodes per task, 12-step
budget) adds the explicit plan "open Settings -> Network & internet -> Internet
-> tap the Wi-Fi switch", with unknown-screen BACK unwinding and a no-repeat
guard on the toggled switch:

| wifi task | Without sequence | With sequence |
|---|---:|---:|
| wifi_on · reactive | 0% | 80% |
| wifi_off · reactive | 0% | 60% |
| wifi_on · phase3 | 20% | 60% |
| wifi_off · phase3 | 0% | 80% |

Run with `--settings-navigation`.  Remaining failures track the accessibility
forwarder's occasional sparse-tree hiccups (4-6 sparse steps and 0-1 recoveries
per task) rather than the navigation policy.

## 3. Evidence required before calling migration complete

- Save the preflight JSON with `runtime_ready: true`.
- Save `androidworld_smoke_latest.json` with a real reset and action execution.
- Run at least one deterministic task/seed with both the reactive baseline and
  the phase-three planner.
- Store the raw UI hierarchy, selected action, reward, terminal signal and task
  success for both runs.
- Report task success, action execution rate and average steps.  Adapter unit
  tests or a detected emulator alone are not a completed migration.
