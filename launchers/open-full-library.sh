#!/bin/sh
# Knowledge Arc: open the full library in the web browser.
# On the drive this file is arc/open-full-library.sh. Linux: run
# `sh arc/open-full-library.sh` from the drive. Mac: double-click
# "2 Open full library (Mac).command", which runs this file.
# It works from inside arc/, so its paths have no arc/ prefix.
# Starts the Kiwix server from this drive (only this computer can see it),
# then opens the browser. Closing this window stops the library.
# With --share (arc/Share over Wi-Fi (Mac).command, or
# `sh arc/open-full-library.sh --share` on Linux), phones and computers on
# the same network can reach it too.
# NOT YET TESTED on a Mac or on Linux (20 Nov 2026).

cd "$(dirname "$0")" || exit 1
ADDRESS=127.0.0.1
if [ "$1" = "--share" ]; then
  ADDRESS=all
  shift
fi
PORT=8642
URL="http://127.0.0.1:$PORT/"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  KIWIX=software/mac/kiwix-arm64/kiwix-serve ;;
  Darwin-*)      KIWIX=software/mac/kiwix-x86_64/kiwix-serve ;;
  Linux-x86_64)  KIWIX=software/linux/kiwix/kiwix-serve ;;
  *)             KIWIX="" ;;
esac

echo
echo "  KNOWLEDGE ARC: FULL LIBRARY"
echo "  ==========================="
echo

if [ -z "$KIWIX" ] || [ ! -f "$KIWIX" ]; then
  echo "  There is no library program on this drive for this computer ($(uname -sm))."
  echo "  Use \"1 START-HERE\" at the top of the drive instead."
  exit 1
fi

# Every library package on the drive.
set --
for d in site collections; do
  for f in "$d"/*.zim; do
    [ -f "$f" ] && set -- "$@" "$f"
  done
done
if [ $# -eq 0 ]; then
  echo "  No library packages were found on this drive. Use \"1 START-HERE\"."
  exit 1
fi

echo "  Opening $# collections. Your web browser will open by itself."
echo
echo "  KEEP THIS WINDOW OPEN while you read."
echo "  When you have finished, close this window."
echo
echo "  If the browser does not open, type this address in it: $URL"
echo

if [ "$ADDRESS" = all ]; then
  echo "  SHARING OVER WI-FI. On a phone or another computer connected to the"
  echo "  same Wi-Fi, open the web browser and type one of these addresses:"
  if [ "$(uname -s)" = Darwin ]; then
    ifconfig 2>/dev/null | awk '/inet / {print $2}'
  else
    hostname -I 2>/dev/null | tr ' ' '\n'
  fi | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | grep -v '^127\.' | sort -u |
    while read -r ip; do echo "      http://$ip:$PORT/"; done
  echo "  The computer may ask whether to allow kiwix-serve to accept incoming"
  echo "  connections: choose Allow. Without that, phones cannot connect."
  echo
fi

# The library's home page (one search box for everything), built with the drive.
if [ -f system/library-home.html ]; then
  set -- -c system/library-home.html "$@"
fi

# -i 127.0.0.1  only this computer can reach it (-i all when sharing)
# -b            links to the internet show a clear "not available" page
# -k            a damaged package is skipped instead of stopping everything
"$KIWIX" -i "$ADDRESS" -p "$PORT" -b -k "$@" >"${TMPDIR:-/tmp}/knowledge-arc.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null' EXIT INT TERM HUP

# Wait until the library answers (up to a minute); without curl (some Linux
# systems), just give it 3 seconds.
if command -v curl >/dev/null 2>&1; then
  i=0
  while [ "$i" -lt 60 ]; do
    curl -s -o /dev/null "$URL" 2>/dev/null && break
    kill -0 "$PID" 2>/dev/null || break
    sleep 1
    i=$((i + 1))
  done
else
  sleep 3
fi

# The drive's own Firefox, in a fresh temporary profile; else the computer's
# own browser. Mac: Firefox runs from Mozilla's disk image, opened read-only.
PROF=$(mktemp -d "${TMPDIR:-/tmp}/knowledge-arc-firefox.XXXXXX")
cp software/firefox-user.js "$PROF/user.js" 2>/dev/null
FF=""
if [ "$(uname -s)" = Darwin ]; then
  for dmg in software/mac/firefox-*.dmg; do
    [ -f "$dmg" ] || continue
    MNT="${TMPDIR:-/tmp}/knowledge-arc-firefox-app"
    mkdir -p "$MNT"
    hdiutil attach -nobrowse -readonly -mountpoint "$MNT" "$dmg" >/dev/null 2>&1 &&
      FF="$MNT/Firefox.app/Contents/MacOS/firefox"
    break
  done
elif [ -f software/linux/firefox/firefox ]; then
  FF=software/linux/firefox/firefox
fi
if [ -n "$FF" ]; then
  "$FF" -no-remote -profile "$PROF" "$URL" >/dev/null 2>&1 &
elif [ "$(uname -s)" = Darwin ]; then
  open "$URL"
else
  xdg-open "$URL" >/dev/null 2>&1 || echo "  Open $URL in the web browser."
fi

wait "$PID"
echo
echo "  The library has stopped. If it stopped by itself, it may already be"
echo "  open in another window: try $URL in the browser."
echo "  Details: ${TMPDIR:-/tmp}/knowledge-arc.log"
