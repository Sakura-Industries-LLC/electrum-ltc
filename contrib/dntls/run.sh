#!/bin/sh
# Run Electrum-LTC through the attested DNTLS launcher on Litecoin testnet.
# Extra arguments are passed to run_electrum (for example -D DATA_DIR).
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
launcher="$here/venv/bin/electrum-dntls"
[ -x "$launcher" ] || { echo "no launcher; run contrib/dntls/build.sh first" >&2; exit 1; }
exec "$launcher" "$root/run_electrum" --testnet "$@"
