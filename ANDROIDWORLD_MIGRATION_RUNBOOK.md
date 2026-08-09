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

## 2. Native benchmark prerequisites

1. Create the official Pixel 6 Android 13 (API 33) AVD.
2. Launch it from the command line with `-no-snapshot -grpc 8554`.
3. Confirm `adb devices` reports exactly one target in state `device`.
4. Install `google-research/android_world` in a Python 3.11 environment.
5. Run the official first task with `--perform_emulator_setup` once so apps and
   permissions are installed.

## 3. Evidence required before calling migration complete

- Save the preflight JSON with `runtime_ready: true`.
- Run at least one deterministic task/seed with both the reactive baseline and
  the phase-three planner.
- Store the raw UI hierarchy, selected action, reward, terminal signal and task
  success for both runs.
- Report task success, action execution rate and average steps.  Adapter unit
  tests or a detected emulator alone are not a completed migration.
