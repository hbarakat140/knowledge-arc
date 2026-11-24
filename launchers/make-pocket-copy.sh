#!/bin/sh
# Knowledge Arc: make a pocket copy of this library (the pocket edition) on a
# stick, a memory card or another drive. Mac: double-click
# "arc/Make a pocket copy (Mac).command". Linux: sh arc/system/make-pocket-copy.sh
# Uses only what comes with macOS and Linux: no internet, nothing installed.
# Nothing on this drive is changed.
#
# The list of the pocket copy's files is arc/pocket/arc/system/CHECKSUMS.sha256
# (made when this drive was built). Each file is taken from arc/pocket if it
# is there (the pocket edition's own pages and files), otherwise from this
# drive. Every file is checked on the copy afterwards.
#
#   sh make-pocket-copy.sh [TARGET-FOLDER] [--yes]

cd "$(dirname "$0")/../.." || exit 2
ROOT=$(pwd -P)
KIT=arc/pocket
LIST=$KIT/arc/system/CHECKSUMS.sha256
TARGET=""
YES=""
for a in "$@"; do
  case "$a" in
    --yes) YES=1 ;;
    *) TARGET=$a ;;
  esac
done

echo
echo "  MAKE A POCKET COPY"
echo "  =================="
echo "  The pocket edition of this library: every guide, the medical and repair"
echo "  collections, the most important Wikipedia articles and the programs, for a phone or a stick"
echo "  of 32 GB or more. Nothing on this drive is changed."
echo

if [ ! -f "$LIST" ]; then
  echo "  This drive has no pocket copy to make (the folder arc/pocket is missing)."
  echo "  A pocket copy is made from a copy of the library bigger than pocket."
  exit 2
fi

size() { stat -c %s "$1" 2>/dev/null || stat -f %z "$1"; }
sha_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -c1-64
  else shasum -a 256 "$1" | cut -c1-64; fi
}
source_of() { if [ -f "$KIT/$1" ]; then echo "$KIT/$1"; else echo "$1"; fi; }
gb() { awk -v b="$1" 'BEGIN { printf "%.1f GB", b / 1e9 }'; }

# Size of the copy, and every file present on this drive.
total=0; biggest=0; count=0; missing=0
while IFS= read -r line; do
  rel=${line#*  }
  src=$(source_of "$rel")
  if [ ! -f "$src" ]; then
    [ "$missing" -lt 10 ] && echo "    missing: $rel"
    missing=$((missing + 1)); continue
  fi
  s=$(size "$src"); total=$((total + s)); count=$((count + 1))
  [ "$s" -gt "$biggest" ] && biggest=$s
done < "$LIST"
if [ "$missing" -gt 0 ]; then
  echo "  $missing files of the pocket copy are missing from this drive."
  echo "  Check this drive first (sh arc/system/verify.sh) and repair it from another copy."
  exit 1
fi
echo "  The pocket copy: $count files, $(gb "$total")."
echo

# Where to.
if [ -z "$TARGET" ]; then
  echo "  Plug in the stick or memory card. Drives found:"
  for d in /Volumes/* /media/"$USER"/* /run/media/"$USER"/*; do
    [ -d "$d" ] || continue
    case "$ROOT/" in "$d"/*) continue ;; esac
    [ "$d" = "/Volumes/Macintosh HD" ] && continue
    echo "    $d"
  done
  printf "  Type (or drag here) the drive to copy to, then press Enter: "
  read -r TARGET
  TARGET=$(printf '%s' "$TARGET" | sed "s/^ *//; s/ *$//; s/^'//; s/'$//; s/\\\\ / /g")
fi
[ -n "$TARGET" ] || { echo "  No drive chosen."; exit 1; }
mkdir -p "$TARGET" 2>/dev/null
DEST=$(cd "$TARGET" 2>/dev/null && pwd -P) || { echo "  Cannot open $TARGET."; exit 1; }
case "$DEST/" in "$ROOT"/*) echo "  That is this drive (or a folder on it). Choose another drive."; exit 1 ;; esac
case "$ROOT/" in "$DEST"/*) echo "  That is this drive (or a folder on it). Choose another drive."; exit 1 ;; esac

# FAT32 cannot hold a file of 4 GB or more (the pocket Wikipedia is 5 GB).
mp=$(df -P "$DEST" | awk 'NR == 2 { s = $6; for (i = 7; i <= NF; i++) s = s " " $i; print s }')
if [ "$(uname -s)" = Darwin ]; then
  fs=$(mount | awk -v m="$mp" 'index($0, " on " m " (") { sub(/.* \(/, ""); sub(/,.*/, ""); print }')
else
  fs=$(awk -v m="$mp" '{ p = $2; gsub(/\\040/, " ", p) } p == m { print $3 }' /proc/mounts 2>/dev/null | tail -1)
fi
case "$fs" in
  msdos|vfat|fat|fat32|FAT32)
    if [ "$biggest" -ge 4294967295 ]; then
      echo "  $DEST is formatted FAT32, which cannot hold files of 4 GB or more."
      echo "  Format it as exFAT first. This ERASES it:"
      echo "    Mac: Disk Utility, select the drive, Erase, Format: ExFAT."
      echo "    Linux: the Disks program, Format Partition, type exFAT."
      exit 1
    fi ;;
esac

# Files already there with the same size are kept (a stopped copy carries on).
need=0
while IFS= read -r line; do
  rel=${line#*  }
  src=$(source_of "$rel")
  if [ ! -f "$DEST/$rel" ] || [ "$(size "$DEST/$rel")" != "$(size "$src")" ]; then
    need=$((need + $(size "$src")))
  fi
done < "$LIST"
free=$(( $(df -Pk "$DEST" | awk 'NR == 2 { print $4 }') * 1024 ))
if [ "$need" -gt "$free" ]; then
  echo "  Not enough room: the copy needs $(gb "$need") more, and $(gb "$free") is free."
  exit 1
fi
echo "  Copy $(gb "$need") to $DEST, then check every file."
if [ -z "$YES" ]; then
  printf "  Start? [Y/n] "
  read -r answer
  case "$answer" in ""|y|Y|yes|Yes) ;; *) echo "  Stopped."; exit 1 ;; esac
fi
echo "  Copying. This can take an hour or more; you can stop it and run it again later."

n=0
while IFS= read -r line; do
  rel=${line#*  }
  src=$(source_of "$rel")
  if [ ! -f "$DEST/$rel" ] || [ "$(size "$DEST/$rel")" != "$(size "$src")" ]; then
    mkdir -p "$(dirname "$DEST/$rel")" && cp "$src" "$DEST/$rel" || echo "    could not copy $rel"
  fi
  n=$((n + 1)); [ $((n % 100)) -eq 0 ] && echo "    $n of $count"
done < "$LIST"
mkdir -p "$DEST/arc/system" && cp "$LIST" "$DEST/arc/system/CHECKSUMS.sha256"

# Check every file on the copy; copy a damaged one once more.
echo "  Checking the copy."
bad=0
while IFS= read -r line; do
  sha=${line%%  *}; rel=${line#*  }
  if [ ! -f "$DEST/$rel" ] || [ "$(sha_of "$DEST/$rel")" != "$sha" ]; then
    mkdir -p "$(dirname "$DEST/$rel")" && cp "$(source_of "$rel")" "$DEST/$rel"
    if [ "$(sha_of "$DEST/$rel")" != "$sha" ]; then
      echo "    did not copy correctly: $rel"; bad=$((bad + 1))
    fi
  fi
done < "$LIST"

echo
if [ "$bad" -eq 0 ]; then
  echo "  ALL GOOD: the pocket copy is ready, $count files checked."
  echo "  On a computer, open \"1 START-HERE\" on it. On an Android phone, install the"
  echo "  Kiwix app from arc/software/android on the copy and open the .zim files in it."
  exit 0
fi
echo "  PROBLEM: $bad files did not copy correctly. The stick may be failing, or this"
echo "  drive has a damaged file: run sh arc/system/verify.sh on it, then try again."
exit 1
