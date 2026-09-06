#!/bin/sh
# Create a self-signed macOS code-signing identity for the DNTLS launcher.
#
# The Local Trust Resolver accepts any validly signed image whose signer the
# attestation names, so a self-signed certificate is enough for development
# and demos. The identity lives in its own keychain under contrib/dntls/ca
# and is added to the user's keychain search list.
#
# Usage: signing-identity.sh [DAYS]   (default 365)
set -eu
days="${1:-365}"
dir="$(cd "$(dirname "$0")" && pwd)/ca"
mkdir -p "$dir"
kc="$dir/dntls-launcher.keychain-db"
pw="$(openssl rand -hex 16)"
cn="dntls-electrum-launcher-$(openssl rand -hex 4)"

security delete-keychain "$kc" 2>/dev/null || true
security create-keychain -p "$pw" "$kc"
security set-keychain-settings -u -t 21600 "$kc"
security unlock-keychain -p "$pw" "$kc"
orig=$(security list-keychains -d user | tr -d '" ')
# shellcheck disable=SC2086
security list-keychains -d user -s "$kc" $orig

cat > "$dir/ext.cnf" <<EOF
[req]
distinguished_name = dn
x509_extensions = v3
prompt = no
[dn]
CN = $cn
[v3]
keyUsage = critical, digitalSignature
extendedKeyUsage = critical, codeSigning
EOF
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$dir/key.pem" -out "$dir/cert.pem" \
  -days "$days" -subj "/CN=$cn" -config "$dir/ext.cnf" 2>/dev/null
openssl pkcs12 -export -legacy -inkey "$dir/key.pem" -in "$dir/cert.pem" -out "$dir/cert.p12" -passout pass:x
security import "$dir/cert.p12" -k "$kc" -P x -T /usr/bin/codesign -A
security set-key-partition-list -S "apple-tool:,apple:,codesign:" -s -k "$pw" "$kc" >/dev/null
printf '%s\n' "$cn" > "$dir/cn.txt"
printf '%s\n' "$kc" > "$dir/keychain.txt"
printf '%s\n' "$pw" > "$dir/password.txt"
chmod 600 "$dir"/*.pem "$dir"/*.p12 "$dir/password.txt"
echo "signing identity: $cn"
echo "keychain: $kc"
