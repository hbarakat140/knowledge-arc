#!/bin/sh
# Knowledge Arc for Mac: make a pocket copy of this library on a stick or a
# memory card. On the drive this file is "arc/Make a pocket copy (Mac).command".
# Double-click it. It runs arc/system/make-pocket-copy.sh (also the Linux way:
# sh arc/system/make-pocket-copy.sh). See arc/system/MAINTENANCE.txt.
exec sh "$(dirname "$0")/system/make-pocket-copy.sh" "$@"
