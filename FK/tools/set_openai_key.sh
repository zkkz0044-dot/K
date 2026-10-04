#!/bin/bash
set -euo pipefail
SECRET_DIR=/root/K/FK/secrets
KEY_FILE="$SECRET_DIR/openai_api_key"
install -d -m 700 "$SECRET_DIR"
printf 'OpenAI API Key (input hidden): ' >&2
IFS= read -rs key
printf '\n' >&2
[[ "$key" == sk-* ]] || { echo 'ERROR: key format is not sk-*' >&2; unset key; exit 2; }
umask 077
tmp=$(mktemp "$SECRET_DIR/.openai_api_key.XXXXXX")
printf '%s\n' "$key" > "$tmp"
chmod 600 "$tmp"
mv -f "$tmp" "$KEY_FILE"
unset key
printf 'KEY_STORED=%s\n' "$KEY_FILE"
printf 'MODE=%s\n' "$(stat -c '%a' "$KEY_FILE")"
