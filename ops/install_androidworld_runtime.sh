#!/usr/bin/env bash
set -euo pipefail

SDK_ROOT="${ANDROID_SDK_ROOT:-/root/autodl-tmp/android-sdk}"
RUNTIME_ROOT="${ANDROIDWORLD_RUNTIME_ROOT:-/root/autodl-tmp/androidworld-runtime}"
AVD_NAME="${ANDROIDWORLD_AVD_NAME:-AndroidWorldAvd}"
TOOLS_ZIP="$RUNTIME_ROOT/commandlinetools-linux-11076708_latest.zip"
SDKMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
AVDMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/avdmanager"
EMULATOR="$SDK_ROOT/emulator/emulator"

mkdir -p "$SDK_ROOT/cmdline-tools/latest" "$RUNTIME_ROOT"

if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    adb ffmpeg openjdk-17-jre-headless unzip wget \
    libasound2 libdrm2 libgbm1 libnss3 libpulse0 libxcomposite1 \
    libxcursor1 libxdamage1 libxfixes3 libxi6 libxkbcommon0 libxrandr2 \
    libxshmfence1 libxtst6
fi

if [[ ! -x "$SDKMANAGER" ]]; then
  wget -c "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" -O "$TOOLS_ZIP"
  mkdir -p "$RUNTIME_ROOT/commandlinetools-unpack"
  unzip -o "$TOOLS_ZIP" -d "$RUNTIME_ROOT/commandlinetools-unpack"
  cp -a "$RUNTIME_ROOT/commandlinetools-unpack/cmdline-tools/." "$SDK_ROOT/cmdline-tools/latest/"
fi

export ANDROID_SDK_ROOT="$SDK_ROOT"
export PATH="$SDK_ROOT/cmdline-tools/latest/bin:$SDK_ROOT/emulator:$SDK_ROOT/platform-tools:$PATH"

yes | "$SDKMANAGER" --licenses >/dev/null || true
"$SDKMANAGER" \
  "platform-tools" \
  "emulator" \
  "platforms;android-33" \
  "build-tools;33.0.2" \
  "system-images;android-33;google_apis;x86_64"

if ! "$EMULATOR" -list-avds 2>/dev/null | grep -Fxq "$AVD_NAME"; then
  echo no | "$AVDMANAGER" create avd \
    --force \
    --name "$AVD_NAME" \
    --device pixel_6 \
    --package "system-images;android-33;google_apis;x86_64"
fi

echo "ANDROID_SDK_ROOT=$SDK_ROOT"
echo "AVD_NAME=$AVD_NAME"
"$SDK_ROOT/platform-tools/adb" version | head -n 1
"$SDK_ROOT/emulator/emulator" -version | head -n 1
