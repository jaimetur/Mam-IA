#!/bin/sh
# Puts the latest APK of the Android app on the NAS (from the rolling "android-latest" release, rebuilt by GitHub
# Actions on every change in android/), so the server serves it at /android.apk and the landing page shows its download
# button (/api/android says available: true). Usage: tools/deploy-android.sh   (after a push that changes android/)
set -eu
HOST=${MAMIA_HOST:-nas}
DATA=${MAMIA_DATA:-/volume1/docker/data/mamia}
cd "$(git rev-parse --show-toplevel)"
SHA=$(git rev-parse HEAD)
RID=""
for i in $(seq 1 30); do RID=$(gh run list --workflow android.yml --commit "$SHA" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true); [ -n "$RID" ] && break; sleep 5; done
if [ -n "$RID" ]; then gh run watch "$RID" --exit-status >/dev/null || { echo "The Android build $RID failed." >&2; exit 1; }; fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
gh release download android-latest -p mamia-android.apk -p android-build.txt -D "$TMP"
for f in mamia-android.apk android-build.txt; do
  ssh -o BatchMode=yes "$HOST" "mkdir -p $DATA/android && cat > $DATA/android/$f.tmp && mv $DATA/android/$f.tmp $DATA/android/$f && chmod 644 $DATA/android/$f" < "$TMP/$f"
done
echo "APK on the NAS: $(head -1 "$TMP/android-build.txt")"
sed -n 2p "$TMP/android-build.txt"
