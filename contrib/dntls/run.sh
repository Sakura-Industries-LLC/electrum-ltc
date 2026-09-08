#!/bin/sh
# Run the DNTLS build of Electrum-LTC on Litecoin testnet from the development
# environment. Extra arguments are passed to run_electrum (for example -D DATA_DIR).
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
python="$here/venv/bin/python"
[ -x "$python" ] || { echo "no environment; run contrib/dntls/build.sh first" >&2; exit 1; }
exec "$python" "$root/run_electrum" --testnet "$@"
