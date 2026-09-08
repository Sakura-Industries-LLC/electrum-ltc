#!/bin/sh
# Set up a development environment for the DNTLS build of Electrum-LTC (macOS).
#
# Produces contrib/dntls/venv with Electrum-LTC, its GUI dependencies, a
# loadable libsecp256k1, libmwebd, and the DNTLS Python SDK. Run the app with
# contrib/dntls/run.sh. The Local Trust Resolver identifies the app by
# registration (a confirmation code the user approves), so nothing here is
# signed; the release build in .github/workflows/dntls-release.yml is.
#
# Environment:
#   PYTHON          CPython 3.12 (default: python3.12)
#   DNTLS_SDK_PATH  path to dntls-testnet/sdk/python (default: sibling checkout
#                   at ../../../testnet/sdk/python, or, when that is absent,
#                   the commit pinned in contrib/dntls/sdk-commit.txt fetched
#                   from GitHub)
set -eu

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
venv="$here/venv"
python="${PYTHON:-python3.12}"
sdk="${DNTLS_SDK_PATH:-$root/../testnet/sdk/python}"
sdk_commit="$(tr -d '[:space:]' < "$here/sdk-commit.txt")"

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

"$venv/bin/python" -c 'import sys, electrum, dntls_sdk; print("python", sys.version.split()[0], "electrum", electrum.version.ELECTRUM_VERSION)'
echo "ready: contrib/dntls/run.sh"
