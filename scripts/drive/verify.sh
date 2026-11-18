#!/bin/sh
# Checks every file on this drive against 99_SYSTEM/CHECKSUMS.sha256.
# Run from a terminal:  sh /path/to/drive/99_SYSTEM/verify.sh
# Works on Linux (sha256sum) and Mac (shasum). Nothing to install.

cd "$(dirname "$0")/.." || exit 2
list=99_SYSTEM/CHECKSUMS.sha256
[ -f "$list" ] || { echo "CHECKSUMS.sha256 is missing. Cannot check this drive."; exit 2; }

echo "Checking every file on this drive. On a large drive this can take an hour or more."
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -c --quiet "$list"
else
    shasum -a 256 -c --quiet "$list"
fi
status=$?
echo
if [ "$status" -eq 0 ]; then
    echo "ALL GOOD: $(wc -l < "$list" | tr -d ' ') files are intact."
else
    echo "PROBLEM: the files listed above are damaged or missing. Replace them from another copy of the drive."
fi
exit "$status"
