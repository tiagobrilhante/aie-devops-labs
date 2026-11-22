#!/usr/bin/env bash
# Repete o canary_check N vezes contra alias_local em três cenários e conta os rollbacks.
set -u
PY=.venv/bin/python; N=${N:-50}
$PY classificador/deploy/alias_local.py --peso 0.1 --erro-canary 0   --porta 9078 >/dev/null & P1=$!
$PY classificador/deploy/alias_local.py --peso 0.3 --erro-canary 0   --porta 9080 >/dev/null & P3=$!
$PY classificador/deploy/alias_local.py --peso 0.1 --erro-canary 0.2 --porta 9079 >/dev/null & P2=$!
trap 'kill $P1 $P2 $P3 2>/dev/null' EXIT
sleep 2
for cfg in "9078 saudável,peso=10%" "9080 saudável,peso=30%" "9079 erro=20%,peso=10%"; do
  porta=${cfg%% *}; nome=${cfg#* }; rb=0; dist=0; err=0; uma=0
  for i in $(seq 1 "$N"); do
    out=$($PY classificador/deploy/canary_check.py "http://127.0.0.1:$porta/" --requisicoes 300 2>&1); rc=$?
    if [ $rc -ne 0 ]; then rb=$((rb+1))
      grep -q "previsões '" <<<"$out" && dist=$((dist+1))
      grep -q "taxa de erro" <<<"$out" && err=$((err+1))
      grep -q "Só uma versão" <<<"$out" && uma=$((uma+1))
    fi
  done
  echo "$nome: rollback em $rb/$N (motivo distribuição: $dist · erro: $err · só uma versão: $uma)"
done
