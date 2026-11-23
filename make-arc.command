#!/bin/sh
# Make your own Knowledge Arc (Mac or Linux): double-click this file, or run
# sh make-arc.command. It runs make-arc.py, which asks which drive and which edition.
# Python: this computer's own if it is 3.11 or newer; otherwise a portable
# Python fetched once by scripts/get-python.sh into the user's cache folder
# (nothing installed; delete that folder to remove it). Set
# ARC_PORTABLE_PYTHON=1 to use the portable one anyway.
cd "$(dirname "$0")" || exit 1

version=$(awk '$1=="version"{print $2}' scripts/portable-python.txt)
case "$(uname -s)" in
    Darwin) cache="$HOME/Library/Caches/knowledge-arc" ;;
    *)      cache="${XDG_CACHE_HOME:-$HOME/.cache}/knowledge-arc" ;;
esac
portable="$cache/python-$version/bin/python3"

# at_least <python> <minor>: that Python is 3.<minor> or newer.
at_least() {
    "$1" -c "import sys; sys.exit(sys.version_info < (3, $2))" >/dev/null 2>&1
}
# usable <name>: on the PATH, and not the Mac's stand-in python3 that only
# offers to install Apple's developer tools.
usable() {
    command -v "$1" >/dev/null 2>&1 || return 1
    if [ "$(uname -s)" = Darwin ] && [ "$(command -v "$1")" = /usr/bin/python3 ] \
            && ! xcode-select -p >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

py=""
old=""
if [ ! -x "$portable" ] && [ -z "${ARC_PORTABLE_PYTHON:-}" ]; then
    for c in python3 python; do
        usable "$c" || continue
        if at_least "$c" 11; then py=$c; break; fi
        # 3.9 or 3.10 is kept as a fallback: it builds without search.
        if [ -z "$old" ] && at_least "$c" 9; then old=$c; fi
    done
fi
if [ -z "$py" ] && [ ! -x "$portable" ]; then
    sh scripts/get-python.sh
fi
if [ -z "$py" ] && [ -x "$portable" ]; then py=$portable; fi
if [ -z "$py" ]; then py=$old; fi
if [ -z "$py" ]; then
    echo
    echo "Python is needed to make an arc, and none could be fetched. Check the internet"
    echo "connection and run this again, or install Python 3.11 or newer from"
    echo "https://www.python.org/downloads/"
    exit 1
fi
exec "$py" make-arc.py "$@"
