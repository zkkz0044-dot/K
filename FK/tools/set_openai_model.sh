#!/bin/bash
set -euo pipefail
MODEL=${1:-}
[[ -n "$MODEL" ]] || { echo 'ERROR: model id required' >&2; exit 2; }
[[ "$MODEL" == gpt-* ]] || { echo 'ERROR: only gpt-* model ids are allowed' >&2; exit 3; }
[[ "$MODEL" =~ ^[A-Za-z0-9._:-]{1,64}$ ]] || { echo 'ERROR: invalid model id' >&2; exit 4; }
DIR=/root/K/FK/config
FILE="$DIR/openai-model.env"
install -d -m 755 "$DIR"
umask 022
tmp=$(mktemp "$DIR/.openai-model.XXXXXX")
printf 'OPENAI_MODEL=%s\n' "$MODEL" > "$tmp"
chmod 644 "$tmp"
mv -f "$tmp" "$FILE"
printf 'MODEL_CONFIGURED=%s\n' "$MODEL"
