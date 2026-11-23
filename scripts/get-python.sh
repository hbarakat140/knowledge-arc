#!/bin/sh
# Knowledge Arc: fetch the portable Python that make-arc.command uses when this
# computer has no Python 3.11 or newer (Mac or Linux). Nothing is installed:
# the Python is unpacked into the user's cache folder,
#   Mac    ~/Library/Caches/knowledge-arc/python-<version>
#   Linux  ~/.cache/knowledge-arc/python-<version>
# and deleting that folder removes it. Not next to the recipe: on an exFAT
# drive it could not be unpacked (exFAT has no symbolic links). The file to
# fetch and its sha-256 fingerprint are pinned in scripts/portable-python.txt;
# a file that doesn't match is not used. Needs curl or wget, and tar.
# Run by make-arc.command; exits 0 when the Python is ready.

here=$(cd "$(dirname "$0")" && pwd)
pins="$here/portable-python.txt"
release=$(awk '$1=="release"{print $2}' "$pins")
version=$(awk '$1=="version"{print $2}' "$pins")

fail() {
    echo
    echo "Could not fetch a portable Python: $1"
    exit 1
}

case "$(uname -s)" in
    Darwin) os=mac; base="$HOME/Library/Caches/knowledge-arc" ;;
    Linux)  os=linux; base="${XDG_CACHE_HOME:-$HOME/.cache}/knowledge-arc" ;;
    *)      fail "there is none for this system ($(uname -s))." ;;
esac
case "$(uname -m)" in
    x86_64|amd64)  arch=x86_64 ;;
    arm64|aarch64) if [ "$os" = mac ]; then arch=arm64; else arch=aarch64; fi ;;
    *)             fail "there is none for this processor ($(uname -m))." ;;
esac
if [ "$os" = linux ] && ldd --version 2>&1 | grep -qi musl; then
    fail "there is none for this Linux (musl, such as Alpine). Install python3 with its package manager."
fi

target="$base/python-$version"
[ -x "$target/bin/python3" ] && exit 0

line=$(awk -v k="$os-$arch" '$1==k{print $2, $3}' "$pins")
[ -n "$line" ] || fail "scripts/portable-python.txt has no line for $os-$arch."
sha=${line%% *}
name=${line#* }
url="https://github.com/astral-sh/python-build-standalone/releases/download/$release/$(printf '%s' "$name" | sed 's/+/%2B/g')"
mkdir -p "$base" || fail "could not make the folder $base."
part="$base/$name.part"

echo
echo "This computer has no Python 3.11 or newer. Fetching a portable Python $version"
echo "(about 25-36 MB, once; nothing is installed) ..."
if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 -o "$part" "$url" || { rm -f "$part"; fail "the download failed. Check the internet connection and try again."; }
elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$part" "$url" || { rm -f "$part"; fail "the download failed. Check the internet connection and try again."; }
else
    fail "neither curl nor wget is installed."
fi
if command -v sha256sum >/dev/null 2>&1; then
    got=$(sha256sum "$part" | cut -d' ' -f1)
else
    got=$(shasum -a 256 "$part" | cut -d' ' -f1)
fi
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
echo "Python $version is ready in $target"
echo "(delete that folder to remove it)."
