#!/bin/sh
# Knowledge Arc: the portable Python that make-arc.command uses when this
# computer has no Python 3.11 or newer (Mac or Linux). Nothing is installed:
# the Python is unpacked into the user's cache folder,
#   Mac    ~/Library/Caches/knowledge-arc/python-<version>
#   Linux  ~/.cache/knowledge-arc/python-<version>
# and deleting that folder removes it. Not next to the recipe: on an exFAT
# drive it could not be unpacked (exFAT has no symbolic links). The file to
# fetch and its sha-256 fingerprint are pinned in scripts/portable-python.txt;
# a file that doesn't match is not used. Needs curl or wget, and tar.
#
#   sh scripts/get-python.sh              fetch it if needed; print its path
#   sh scripts/get-python.sh --installed  print its path only if already there
# The path is the only thing on stdout; messages go to stderr.

here=$(cd "$(dirname "$0")" && pwd)
pins="$here/portable-python.txt"

fail() {
    echo >&2
    echo "Could not fetch a portable Python: $1" >&2
    exit 1
}

# pin <key>: the rest of that line of the pin file. Trailing characters
# outside the pinned values' alphabet are dropped: a recipe copied from a
# Windows checkout has CRLF line endings.
pin() {
    awk -v k="$1" '{sub(/[^0-9A-Za-z._+-]+$/,"")} $1==k{$1=""; print substr($0, 2)}' "$pins"
}
release=$(pin release)
version=$(pin version)

case "$(uname -s)" in
    Darwin) os=mac; base="$HOME/Library/Caches/knowledge-arc" ;;
    Linux)  os=linux; base="${XDG_CACHE_HOME:-$HOME/.cache}/knowledge-arc" ;;
    *)      fail "there is none for this system ($(uname -s))." ;;
esac
target="$base/python-$version"
python="$target/bin/python3"
if [ -x "$python" ]; then
    echo "$python"
    exit 0
fi
[ "${1:-}" = --installed ] && exit 1

case "$(uname -m)" in
    x86_64|amd64)  arch=x86_64 ;;
    arm64|aarch64) if [ "$os" = mac ]; then arch=arm64; else arch=aarch64; fi ;;
    *)             fail "there is none for this processor ($(uname -m))." ;;
esac
if [ "$os" = linux ] && ldd --version 2>&1 | grep -qi musl; then
    fail "there is none for this Linux (musl, such as Alpine). Install python3 with its package manager."
fi

line=$(pin "$os-$arch")
[ -n "$line" ] || fail "scripts/portable-python.txt has no line for $os-$arch."
sha=${line%% *}
name=${line#* }
url="https://github.com/astral-sh/python-build-standalone/releases/download/$release/$(printf '%s' "$name" | sed 's/+/%2B/g')"
mkdir -p "$base" || fail "could not make the folder $base."
part="$base/$name.part"

if command -v curl >/dev/null 2>&1; then
    fetch="curl -fsSL --retry 3 -o"
elif command -v wget >/dev/null 2>&1; then
    fetch="wget -q -O"
else
    fail "neither curl nor wget is installed."
fi
{
    echo
    echo "This computer has no Python 3.11 or newer. Fetching a portable Python $version"
    echo "(about 25-36 MB, once; nothing is installed) ..."
} >&2
$fetch "$part" "$url" || { rm -f "$part"; fail "the download failed. Check the internet connection and try again."; }
got=$( (sha256sum "$part" 2>/dev/null || shasum -a 256 "$part") | cut -d' ' -f1)
if [ "$got" != "$sha" ]; then
    rm -f "$part"
    fail "the downloaded file does not match its fingerprint (sha-256), so it was not used."
fi
tmp="$target.part"
rm -rf "$tmp"
mkdir -p "$tmp" && tar -xzf "$part" -C "$tmp" || { rm -rf "$tmp"; fail "the downloaded file could not be unpacked."; }
mv "$tmp/python" "$target" && rm -rf "$tmp" "$part" || fail "could not move it into $target."
echo "The portable Python that Knowledge Arc's make-arc fetched. Delete this folder to remove it." \
    > "$target/knowledge-arc-portable.txt"
echo "Python $version is ready in $target (delete that folder to remove it)." >&2
echo "$python"
