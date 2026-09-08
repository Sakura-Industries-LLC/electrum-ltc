# DNTLS build of Electrum-LTC

Development environment and release pipeline for the DNTLS build. The
behaviour itself is the `dntls` plugin under `electrum/plugins/dntls`: names
ending in `.dntls` resolve in the pay-to field through the Local Trust
Resolver, and Tools → Publish address to DNTLS identity… proposes this
program's receive address on one of the user's names.

## How the resolver identifies the program

The Local Trust Resolver identifies a program by registration, not by its
binary. The first time the plugin needs a consented route, it generates a
six-character confirmation code, shows it in Electrum-LTC, and sends
`POST /v1/register` with the label `Electrum-LTC`. The resolver opens a
"Program request" prompt showing the same code together with what macOS
reports about the process (application, executable, signer). The user allows
it only if both codes match; the resolver returns a bearer credential, which
the plugin stores at `<data dir>/dntls-resolver.token` and sends on every
later request. Removing the registration on the resolver's Programs page
makes the next consented call register again.

Code signing therefore does not gate anything, but it is still worth having:
the prompt names a recognized signer for the notarized release, and an
unsigned development build shows "nobody signed the program".

## Development (macOS)

Requirements: CPython 3.12, Homebrew `secp256k1`, Go (for libmwebd), and read
access to the `dntls-testnet` repository for `sdk/python` (a sibling checkout
is used when present, otherwise the commit in `sdk-commit.txt` is fetched).

```sh
contrib/dntls/build.sh                     # venv, deps, libsecp256k1, libmwebd, SDK
contrib/dntls/run.sh -D ~/electrum-dntls   # Electrum-LTC on Litecoin testnet
```

Environment overrides: `PYTHON`, `DNTLS_SDK_PATH` (see the script header).

## Release

The signed, notarized macOS build ships from
`.github/workflows/dntls-release.yml`. Push a tag:

```sh
git tag -a -m "…" electrum-dntls/v0.2.0 && git push origin electrum-dntls/v0.2.0
```

The workflow builds the app with `contrib/osx/make_osx.sh` on `macos-14`,
signs it with the org's Developer ID certificate through
`contrib/osx/sign_osx.sh` (bundle identifier `net.dntls.electrum-ltc`),
notarizes and staples both the app and the disk image, checks the signature,
signs the checksums with keyless cosign, and hands the bundle to the release
suite's `publish-object-store` workflow. The Portal's Downloads page then
offers `electrum-ltc-dntls_<version>_macos_arm64.dmg` to signed-in testnet
users. Prerelease versions are refused by the publisher, so a tag such as
`electrum-dntls/v0.2.0-rc.1` rehearses everything except the upload.

The Python SDK is not on PyPI. The release build installs it from
`dntls-testnet` at the commit in `sdk-commit.txt`, with `--no-deps`; its
dependencies come from `contrib/deterministic-build/requirements-dntls.txt`.
Move both together.
