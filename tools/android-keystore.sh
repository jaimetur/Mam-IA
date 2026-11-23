#!/bin/sh
# Creates the signing key of the Mam-IA Android app (the "upload key" of Google Play) and stores it in the GitHub
# secrets the Android workflow uses. Run it ONCE, yourself, on your computer: keep the .jks file and its password in a
# safe place (a password manager); every version of the app must be signed with this same key.
#   tools/android-keystore.sh [path/to/mamia-upload.jks]
set -eu
KS=${1:-"$HOME/mamia-upload.jks"}
ALIAS=mamia
command -v keytool >/dev/null || { echo "keytool not found: install a JDK (brew install openjdk@17)."; exit 1; }
command -v gh >/dev/null || { echo "gh not found: brew install gh && gh auth login"; exit 1; }
if [ -e "$KS" ]; then echo "$KS already exists: not overwritten."; else
  printf "Password for the new key (at least 6 characters): "; stty -echo; read -r PW; stty echo; echo
  keytool -genkeypair -v -keystore "$KS" -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 10000 \
    -storepass "$PW" -keypass "$PW" -dname "CN=Mam-IA"
fi
[ -n "${PW:-}" ] || { printf "Password of %s: " "$KS"; stty -echo; read -r PW; stty echo; echo; }
cd "$(git rev-parse --show-toplevel)"
base64 < "$KS" | tr -d '\n' | gh secret set ANDROID_KEYSTORE_B64
printf %s "$PW" | gh secret set ANDROID_KEYSTORE_PASSWORD
printf %s "$ALIAS" | gh secret set ANDROID_KEY_ALIAS
printf %s "$PW" | gh secret set ANDROID_KEY_PASSWORD
echo "Done: the next build of the app is signed with $KS. Keep that file and its password safe."
