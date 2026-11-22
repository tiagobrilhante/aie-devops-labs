#!/usr/bin/env bash
# Conta os motivos de rollback de um canary saudável (peso 10%) em N repetições.
set -u
PY=.venv/bin/python; N=${N:-50}
$PY classificador/deploy/alias_local.py --peso 0.1 --erro-canary 0 --porta 9081 >/dev/null & P=$!
trap 'kill $P 2>/dev/null' EXIT
sleep 2
for i in $(seq 1 "$N"); do
  $PY classificador/deploy/canary_check.py http://127.0.0.1:9081/ --requisicoes 300 2>&1 | grep "ROLLBACK" | sed -E "s/[0-9]+(\.[0-9]+)?%/X%/g; s/'[a-z]+'/'<rótulo>'/g"
done | sort | uniq -c | sort -rn
