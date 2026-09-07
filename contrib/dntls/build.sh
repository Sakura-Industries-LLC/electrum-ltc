#!/bin/sh
# Build the attested Electrum-LTC launcher for the DNTLS demo (macOS).
#
# Produces contrib/dntls/venv/bin/electrum-dntls: a code-signed launcher that
# embeds CPython and carries a DNTLS program attestation for the name in
# DNTLS_PROGRAM_DATA_DIR (default: electrum-ltc.dntls). Run the wallet with
# contrib/dntls/run.sh.
#
# Steps: create the venv and install Electrum-LTC with its GUI deps, place a
# loadable libsecp256k1, install the DNTLS Python SDK, then build the launcher
# twice: a provisional signed image is measured by `dntls attest macos`, and
# the marker it prints is compiled into the final image, which is signed again.
#
# Environment:
#   PYTHON                 CPython 3.12 with a shared libpython (default: python3.12)
#   DNTLS_CLI              dntls CLI with `attest` (default: dntls)
#   DNTLS_PROGRAM_DATA_DIR data dir holding the program's identity (default:
#                          ~/tmp/electrum-dntls-data)
#   DNTLS_SDK_PATH         path to dntls-testnet/sdk/python (default: sibling
#                          checkout at ../../../testnet/sdk/python, or, when
#                          that is absent, the commit pinned in
#                          contrib/dntls/sdk-commit.txt fetched from GitHub)
#   SIGN_IDENTIFIER        codesign identifier (default: net.dntls.electrum-ltc)
set -eu

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
venv="$here/venv"
ca="$here/ca"
python="${PYTHON:-python3.12}"
dntls="${DNTLS_CLI:-dntls}"
program_data="${DNTLS_PROGRAM_DATA_DIR:-$HOME/tmp/electrum-dntls-data}"
sdk="${DNTLS_SDK_PATH:-$root/../testnet/sdk/python}"
sdk_commit="$(tr -d '[:space:]' < "$here/sdk-commit.txt")"
identifier="${SIGN_IDENTIFIER:-net.dntls.electrum-ltc}"

[ -f "$ca/cn.txt" ] || { echo "no signing identity; run contrib/dntls/signing-identity.sh first" >&2; exit 1; }
cn="$(cat "$ca/cn.txt")"
keychain="$(cat "$ca/keychain.txt")"
security unlock-keychain -p "$(cat "$ca/password.txt")" "$keychain"

prefix="$("$python" -c 'import sys; print(sys.prefix)')"
pyver="$("$python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
[ -f "$prefix/lib/libpython$pyver.dylib" ] || { echo "$python has no shared libpython (build CPython with --enable-shared)" >&2; exit 1; }

echo "==> virtual environment"
[ -d "$venv" ] || "$python" -m venv "$venv"
"$venv/bin/pip" install -q --upgrade pip
ELECTRUM_ECC_DONT_COMPILE=1 "$venv/bin/pip" install -q "$root[gui,crypto]"
if [ -d "$sdk" ]; then
  "$venv/bin/pip" install -q -e "$sdk"
else
  # No sibling checkout: take the same commit the release build uses. This
  # needs read access to the private dntls-testnet repository.
  "$venv/bin/pip" install -q \
    "git+ssh://git@github.com/Sakura-Industries-LLC/dntls-testnet@${sdk_commit}#subdirectory=sdk/python"
fi

echo "==> libsecp256k1"
# electrum-ecc 0.0.7 looks for ABI versions <= 6 next to itself; Homebrew's
# secp256k1 0.8 ships ABI 7 with the same entry points this wallet uses.
secp="$(brew --prefix secp256k1 2>/dev/null)/lib/libsecp256k1.7.dylib"
[ -f "$secp" ] || { echo "brew install secp256k1 first" >&2; exit 1; }
ecc_dir="$("$venv/bin/python" -c 'import importlib.util; print(importlib.util.find_spec("electrum_ecc").submodule_search_locations[0])')"
rm -f "$ecc_dir/libsecp256k1.6.dylib"
cp "$secp" "$ecc_dir/libsecp256k1.6.dylib"

echo "==> libmwebd"
# Electrum-LTC loads libmwebd from the electrum package directory and exits
# when it is missing. Build it from contrib/mwebd (Go, c-shared).
if [ ! -f "$root/electrum/libmwebd.0.dylib" ]; then
  (cd "$root/contrib/mwebd" && CGO_ENABLED=1 go build -buildmode=c-shared -ldflags="-s -w" -o "$root/electrum/libmwebd.0.dylib" .)
fi

build() {
  # build DEST [MARKER]
  if [ -n "${2:-}" ]; then
    set -- "$1" "-DDNTLS_MARKER=\"$2\""
  else
    set -- "$1" "-DDNTLS_MARKER=\"unset\""
  fi
  clang -O1 -o "$1" "$here/launcher.c" \
    -I"$prefix/include/python$pyver" \
    -L"$prefix/lib" "-lpython$pyver" -ldl \
    -Wl,-rpath,"$prefix/lib" -framework CoreFoundation \
    "$2"
  # No hardened runtime: library validation would reject libpython and the
  # PyQt extension modules, which are signed by other parties.
  codesign -f -s "$cn" --keychain "$keychain" -i "$identifier" --timestamp=none "$1"
}

echo "==> provisional launcher"
tmp="$(mktemp -d)"
build "$tmp/launcher"

echo "==> attestation"
marker="$("$dntls" --data-dir "$program_data" attest macos "$tmp/launcher" \
  | "$venv/bin/python" -c 'import json, sys; print(json.load(sys.stdin)["marker"])')"
[ -n "$marker" ] || { echo "attest printed no marker" >&2; exit 1; }

echo "==> attested launcher"
build "$venv/bin/electrum-dntls" "$marker"
rm -rf "$tmp"

"$venv/bin/electrum-dntls" -c 'import sys, electrum, dntls_sdk; print("python", sys.version.split()[0], "electrum", electrum.version.ELECTRUM_VERSION, "at", sys.executable)'
codesign -dv "$venv/bin/electrum-dntls" 2>&1 | sed -n '/^Identifier=/p'
echo "built $venv/bin/electrum-dntls"
