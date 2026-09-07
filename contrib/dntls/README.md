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
the `dntls` CLI with the `attest` command, read access to the `dntls-testnet`
repository for `sdk/python` (a sibling checkout is used when present,
otherwise the commit in `sdk-commit.txt` is fetched), and a data directory
holding the program identity's credentials
(`dntls --data-dir DIR portal import electrum-ltc.dntls`).

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

## Release

The signed, notarized macOS build ships from
`.github/workflows/dntls-release.yml`. Push a tag:

```sh
git tag electrum-dntls/v0.1.0 && git push origin electrum-dntls/v0.1.0
```

The workflow builds the app with `contrib/osx/make_osx.sh` on `macos-14`,
signs it with the org's Developer ID certificate through
`contrib/osx/sign_osx.sh`, notarizes and staples both the app and the disk
image, checks the signature and the attestation marker, signs the checksums
with keyless cosign, and hands the bundle to the release suite's
`publish-object-store` workflow. The Portal's Downloads page then offers
`electrum-ltc-dntls_<version>_macos_arm64.dmg` to signed-in testnet users.
Prerelease versions are refused by the publisher.

Rehearse without publishing by dispatching the workflow ("Run workflow") with
a version and `publish` left false: everything up to and including the signed
assets runs, and nothing is uploaded. Dispatching from a tag ref additionally
runs the publisher in verify-only mode.

The wallet's Python SDK is not on PyPI. The release build installs it from
`dntls-testnet` at the commit in `sdk-commit.txt`, with `--no-deps`; its
dependencies come from `contrib/deterministic-build/requirements-dntls.txt`.
Move both together.

### The attestation marker

`attestation.marker` is the marker the release build compiles into the
PyInstaller bootloader, which is the shipped app's main executable
(`Electrum-LTC.app/Contents/MacOS/Electrum-LTC`). It was minted offline with
`dntls attest macos --identifier net.dntls.electrum-ltc` against a binary
signed by the org's Developer ID Application certificate, so it binds the name
`electrum-ltc.dntls` to the signer subject (Team ID `7MN6B2QY4W`, signing
identifier `net.dntls.electrum-ltc`) and to nothing else — not to a build, not
to a commit. CI holds no DNTLS key and cannot mint it, which is why it is
committed and only verified there.

Regenerate it only when that subject changes: a different Apple Team ID, or a
different `bundle_identifier` in `contrib/osx/pyinstaller.spec` (which is what
`codesign` uses as the signing identifier). Version bumps, dependency bumps and
code changes leave it valid. The marker for the local demo launcher above is a
separate one, minted for the self-signed identity in `ca/`.
