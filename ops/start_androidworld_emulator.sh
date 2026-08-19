#!/usr/bin/env bash
set -euo pipefail

SDK_ROOT="${ANDROID_SDK_ROOT:-/root/autodl-tmp/android-sdk}"
RUNTIME_ROOT="${ANDROIDWORLD_RUNTIME_ROOT:-/root/autodl-tmp/androidworld-runtime}"
AVD_NAME="${ANDROIDWORLD_AVD_NAME:-AndroidWorldAvd}"
BOOT_TIMEOUT="${ANDROIDWORLD_BOOT_TIMEOUT:-900}"
CPU_CORES="${ANDROIDWORLD_CPU_CORES:-4}"
ALLOW_SOFTWARE="${ANDROIDWORLD_ALLOW_SOFTWARE_EMULATION:-0}"
KEEP_ON_TIMEOUT="${ANDROIDWORLD_KEEP_ON_TIMEOUT:-0}"
EMULATOR="$SDK_ROOT/emulator/emulator"
ADB="$SDK_ROOT/platform-tools/adb"
LOG="$RUNTIME_ROOT/emulator.log"
PID_FILE="$RUNTIME_ROOT/emulator.pid"

mkdir -p "$RUNTIME_ROOT"
export ANDROID_SDK_ROOT="$SDK_ROOT"
export PATH="$SDK_ROOT/emulator:$SDK_ROOT/platform-tools:$PATH"

if [[ -e /dev/kvm ]]; then
  ACCEL=(-accel on)
elif [[ "$ALLOW_SOFTWARE" == "1" ]]; then
  ACCEL=(-accel off)
  echo "WARNING: /dev/kvm is unavailable; using slow software emulation for smoke testing."
else
  echo "ERROR: /dev/kvm is unavailable. Set ANDROIDWORLD_ALLOW_SOFTWARE_EMULATION=1 only for a slow smoke attempt." >&2
  exit 2
fi

"$ADB" devices | awk '/^emulator-/{print $1}' | while read -r serial; do
  "$ADB" -s "$serial" emu kill || true
done

nohup "$EMULATOR" \
  -avd "$AVD_NAME" \
  -no-window \
  -no-snapshot \
  -noaudio \
  -no-boot-anim \
  -memory 2048 \
  -cores "$CPU_CORES" \
  -gpu swiftshader_indirect \
  -grpc 8554 \
  -no-metrics \
  "${ACCEL[@]}" >"$LOG" 2>&1 &
echo $! >"$PID_FILE"

deadline=$((SECONDS + BOOT_TIMEOUT))
while (( SECONDS < deadline )); do
  if [[ "$("$ADB" -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
    "$ADB" -s emulator-5554 shell settings put global window_animation_scale 0.0
    "$ADB" -s emulator-5554 shell settings put global transition_animation_scale 0.0
    "$ADB" -s emulator-5554 shell settings put global animator_duration_scale 0.0
    "$ADB" -s emulator-5554 shell svc wifi enable || true
    network_deadline=$((SECONDS + 120))
    while (( SECONDS < network_deadline )); do
      if "$ADB" -s emulator-5554 shell ip route get 10.0.2.2 2>/dev/null | grep -q '10.0.2.2'; then
        break
      fi
      sleep 5
    done
    if ! "$ADB" -s emulator-5554 shell ip route get 10.0.2.2 2>/dev/null | grep -q '10.0.2.2'; then
      echo "ERROR: emulator booted but AndroidWifi has no route to 10.0.2.2; repair the saved AndroidWifi profile before AndroidWorld." >&2
      exit 3
    fi
    "$ADB" devices -l
    echo "AndroidWorld emulator booted successfully."
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "ERROR: emulator exited before boot. See $LOG" >&2
    tail -n 80 "$LOG" >&2
    exit 1
  fi
  sleep 5
done

echo "ERROR: emulator did not boot within ${BOOT_TIMEOUT}s. See $LOG" >&2
tail -n 80 "$LOG" >&2
if [[ "$KEEP_ON_TIMEOUT" != "1" ]]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
fi
exit 1
