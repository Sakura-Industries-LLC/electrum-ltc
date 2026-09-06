# DNTLS demo launcher

Runs Electrum-LTC as an attested DNTLS program so the Local Trust Resolver can
identify it as `electrum-ltc.dntls` and ask the user for consent when the
wallet lists identities or publishes an address. The wallet-side behaviour is
the `dntls` plugin under `electrum/plugins/dntls`; this directory only makes
the process identifiable.

## Why a launcher

The resolver identifies a program by its main executable: the image must be
validly code-signed and carry exactly one attestation marker signed by the
program's DNTLS name. A Python interpreter cannot be attested that way. The
launcher is a few lines of C that embed CPython (`Py_BytesMain`) and hold the
marker as a string constant; placed in a virtual environment's `bin/` it acts
as that environment's Python, so `run_electrum` starts unchanged with the
signed launcher as the process image.

The launcher cannot use the hardened runtime: library validation would reject
libpython and the PyQt extension modules, which are signed by other parties.
The resolver therefore reports the program as not hardened, which only
disables open-ended ("forever") grants; timed grants work.

## Build (macOS)

Requirements: CPython 3.12 with a shared libpython, Homebrew `secp256k1`,
the `dntls` CLI with the `attest` command, a sibling `dntls-testnet` checkout
for `sdk/python`, and a data directory holding the program identity's
credentials (`dntls --data-dir DIR portal import electrum-ltc.dntls`).

```sh
contrib/dntls/signing-identity.sh          # once: self-signed signing identity
contrib/dntls/build.sh                     # venv, deps, two-pass signed build
contrib/dntls/run.sh -D ~/electrum-dntls   # Electrum-LTC on Litecoin testnet
```

`build.sh` builds a provisional signed launcher, measures it with
`dntls attest macos`, compiles the printed marker into the final launcher, and
signs that. Re-run it after changing the signing identity or the program
identity; the marker binds both.

Environment overrides: `PYTHON`, `DNTLS_CLI`, `DNTLS_PROGRAM_DATA_DIR`,
`DNTLS_SDK_PATH`, `SIGN_IDENTIFIER` (see the script header).

## Check

```sh
contrib/dntls/venv/bin/electrum-dntls -c 'from dntls_sdk.local import Client; print(Client().identities())'
```

The resolver shows a "Program request" prompt naming `electrum-ltc.dntls`;
allowing it returns the identities stored on this machine. An unattested
Python process gets `unverified` instead.
