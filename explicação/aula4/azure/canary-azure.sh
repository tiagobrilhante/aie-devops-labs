#!/usr/bin/env bash
# Aula 4 no Azure: canary com deployment slots do App Service (o equivalente ao alias ponderado do Lambda).
#
#   Lambda (roteiro)                         App Service (aqui)
#   versão imutável publicada            →   slot "canary" com o pacote e o MODELO_VERSAO da candidata
#   alias producao com peso 90/10        →   az webapp traffic-routing set --distribution canary=10
#   promover (100% na nova)              →   traffic-routing clear + slot swap (o código e as configs trocam)
#   rollback (100% na estável)           →   traffic-routing clear (0% no canary)
#
# Precisa de: az login, artefatos/modelo.joblib (python classificador/treino.py) e o plano S1 (slots não
# existem no B1). Rode da raiz do repositório:
#
#   explicação/aula4/azure/canary-azure.sh criar
#   explicação/aula4/azure/canary-azure.sh publicar <slot> <versao> <erro_simulado>
#   explicação/aula4/azure/canary-azure.sh trafego <peso>          # 0.1 = 10% no canary; 0 = limpa
#   explicação/aula4/azure/canary-azure.sh analisar [requisicoes]
#   explicação/aula4/azure/canary-azure.sh promover
#   explicação/aula4/azure/canary-azure.sh apagar
set -euo pipefail

GRUPO="${GRUPO:-rg-aie-canary-brazilsouth}"
REGIAO="${REGIAO:-brazilsouth}"
PLANO="${PLANO:-plano-canary-s1}"
APP_ARQ="$(dirname "$0")/app.nome"
APP="${APP:-$(cat "$APP_ARQ" 2>/dev/null || echo "classificador-canary-$RANDOM")}"
URL="https://$APP.azurewebsites.net/"

pacote() {
  local dir; dir=$(mktemp -d)
  cp classificador/servico.py classificador/texto.py "$(dirname "$0")/app_http.py" "$dir/"
  mkdir -p "$dir/artefatos" && cp artefatos/modelo.joblib "$dir/artefatos/"
  printf 'scikit-learn==1.6.1\njoblib==1.4.2\nscipy==1.15.3\ngunicorn==23.0.0\n' > "$dir/requirements.txt"
  (cd "$dir" && zip -qr pacote.zip .) && echo "$dir/pacote.zip"
}

case "${1:-}" in
  criar)
    echo "$APP" > "$APP_ARQ"
    az group create -n "$GRUPO" -l "$REGIAO" -o none
    az appservice plan create -g "$GRUPO" -n "$PLANO" -l "$REGIAO" --is-linux --sku S1 -o none
    az webapp create -g "$GRUPO" -p "$PLANO" -n "$APP" --runtime "PYTHON:3.12" -o none
    az webapp config set -g "$GRUPO" -n "$APP" -o none \
      --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 120 app_http:app"
    az webapp config appsettings set -g "$GRUPO" -n "$APP" -o none --settings \
      SCM_DO_BUILD_DURING_DEPLOYMENT=true WEBSITES_PORT=8000 MODELO_VERSAO=v1 ERRO_SIMULADO=0
    az webapp deployment slot create -g "$GRUPO" -n "$APP" --slot canary --configuration-source "$APP" -o none
    echo "✅ $APP (S1, $REGIAO) com o slot canary · $URL"
    ;;
  publicar)  # publicar <slot: producao|canary> <versao> <erro_simulado>
    slot="$2"; versao="$3"; erro="${4:-0}"
    "$0" codigo "$slot"
    "$0" versao "$slot" "$versao" "$erro"
    ;;
  codigo)  # codigo <slot>: só o pacote (deploy assíncrono + espera o build terminar)
    slot="$2"; alvo=""; [ "$slot" = canary ] && alvo="--slot canary"
    # --async: o build do scikit-learn no S1 passa do tempo do gateway do Kudu (504 depois de ~10 min).
    # Nada de "appsettings set" logo antes: ele reinicia o contêiner do Kudu e MATA o build
    # ("Deployment has been stopped due to SCM container restart").
    # shellcheck disable=SC2086  # $alvo vazio ou "--slot canary" (array vazio + set -u quebra no bash 3.2 do macOS)
    az webapp deploy -g "$GRUPO" -n "$APP" $alvo --src-path "$(pacote)" --type zip --async true -o none
    sleep 15
    for _ in $(seq 1 60); do
      # shellcheck disable=SC2086
      st=$(az webapp log deployment list -g "$GRUPO" -n "$APP" $alvo --query "[0].[status,complete]" -o tsv 2>/dev/null | paste -sd/ -)
      echo "  $(date -u +%T)Z deploy do slot $slot: status/completo = $st"
      case "$st" in 4/[Tt]rue) break ;; 3/[Tt]rue) echo "❌ deploy falhou"; exit 1 ;; esac
      sleep 20
    done
    ;;
  versao)  # versao <slot> <versao> <erro>: muda as configurações DEPOIS do build e espera o app responder com elas
    slot="$2"; versao="$3"; erro="${4:-0}"; alvo=""; host="$APP"
    [ "$slot" = canary ] && alvo="--slot canary" && host="$APP-canary"
    # MODELO_VERSAO e ERRO_SIMULADO NÃO são "slot settings": viajam com o código no swap, como uma versão do Lambda
    # shellcheck disable=SC2086
    az webapp config appsettings set -g "$GRUPO" -n "$APP" $alvo -o none \
      --settings MODELO_VERSAO="$versao" ERRO_SIMULADO="$erro"
    for _ in $(seq 1 30); do
      r=$(curl -s --max-time 60 "https://$host.azurewebsites.net/" || true)
      echo "  $(date -u +%T)Z $host: ${r:-sem resposta}"
      [[ "$r" == *"\"versao\": \"$versao\""* ]] && echo "✅ slot $slot: versão $versao, erro simulado $erro" && exit 0
      sleep 15
    done
    echo "❌ o slot $slot não respondeu com a versão $versao"; exit 1
    ;;
  trafego)   # trafego <peso>  (0 limpa: 100% na produção)
    if [ "$2" = 0 ]; then az webapp traffic-routing clear -g "$GRUPO" -n "$APP" -o none
    else az webapp traffic-routing set -g "$GRUPO" -n "$APP" --distribution canary="$(python3 -c "print(round($2*100))")" -o none; fi
    az webapp show -g "$GRUPO" -n "$APP" --query "siteConfig.experiments.rampUpRules[].{slot:name, percentual:reroutePercentage}" -o table
    ;;
  analisar)
    .venv/bin/python classificador/deploy/canary_check.py "$URL" --requisicoes "${2:-300}"
    ;;
  promover)
    az webapp traffic-routing clear -g "$GRUPO" -n "$APP" -o none
    az webapp deployment slot swap -g "$GRUPO" -n "$APP" --slot canary --target-slot production -o none
    echo "✅ swap feito: a candidata agora é a produção"
    ;;
  apagar)
    az group delete -n "$GRUPO" --yes && rm -f "$APP_ARQ" && echo "✅ grupo $GRUPO apagado"
    ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
