#!/bin/sh
# Make your own Knowledge Arc (Mac or Linux): double-click this file, or run
# sh make-arc.command. It runs make-arc.py, which asks which drive and which edition.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  python3 make-arc.py "$@"
else
  echo "Python 3 is needed to make an arc. Install it from https://www.python.org/downloads/"
fi
