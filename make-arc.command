#!/bin/sh
# Make your own Knowledge Arc (Mac or Linux): double-click this file, or run
# sh make-arc.command. It runs make-arc.py, which asks which drive and which edition.
# Python: the portable one if it was fetched before, else this computer's own
# if it is 3.11 or newer, else a portable Python fetched once by
# scripts/get-python.sh into the user's cache folder (nothing installed;
# delete that folder to remove it). Set ARC_PORTABLE_PYTHON=1 to use the
# portable one anyway.
cd "$(dirname "$0")" || exit 1
os=$(uname -s)

# minor <python>: its 3.x minor version, or nothing.
minor() {
    "$1" -c 'import sys; print(sys.version_info[1] if sys.version_info[0] == 3 else 0)' 2>/dev/null
}
# usable <name>: on the PATH, and not the Mac's stand-in python3 that only
# offers to install Apple's developer tools.
usable() {
    command -v "$1" >/dev/null 2>&1 || return 1
    if [ "$os" = Darwin ] && [ "$(command -v "$1")" = /usr/bin/python3 ] \
            && ! xcode-select -p >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

py=$(sh scripts/get-python.sh --installed 2>/dev/null)
old=""
if [ -z "$py" ] && [ -z "${ARC_PORTABLE_PYTHON:-}" ]; then
    for c in python3 python; do
        usable "$c" || continue
        m=$(minor "$c")
        [ -n "$m" ] || continue
        if [ "$m" -ge 11 ]; then py=$c; break; fi
        # 3.9 or 3.10 is kept as a fallback: it builds without search.
        if [ -z "$old" ] && [ "$m" -ge 9 ]; then old=$c; fi
    done
fi
[ -n "$py" ] || py=$(sh scripts/get-python.sh)
[ -n "$py" ] || py=$old
if [ -z "$py" ]; then
    echo
    echo "Python is needed to make an arc, and none could be fetched. Check the internet"
    echo "connection and run this again, or install Python 3.11 or newer from"
    echo "https://www.python.org/downloads/"
    exit 1
fi
exec "$py" make-arc.py "$@"
