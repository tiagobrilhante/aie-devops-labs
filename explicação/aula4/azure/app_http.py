"""Invólucro HTTP (WSGI) do classificador para o Azure App Service — Aula 4 sem AWS.

O servico.handler da Aula 2 recebe o EVENTO da Function URL do Lambda ({"body": "..."}).
Aqui cada requisição HTTP vira esse evento, sem mudar nada no serviço.

    gunicorn --bind=0.0.0.0:8000 app_http:app

POST /   {"texto": "..."}  →  o mesmo contrato do Lambda (rotulo, confianca, versao)
GET  /                     →  {"status": "ok", "versao": ...}  (health check)
"""

import json
import os
from pathlib import Path

os.environ.setdefault("MODELO_CAMINHO", str(Path(__file__).parent / "artefatos" / "modelo.joblib"))

import servico  # noqa: E402

_STATUS = {200: "200 OK", 400: "400 Bad Request", 500: "500 Internal Server Error"}


def app(environ, start_response):
    if environ["REQUEST_METHOD"] == "POST":
        tamanho = int(environ.get("CONTENT_LENGTH") or 0)
        corpo = environ["wsgi.input"].read(tamanho).decode("utf-8")
        resposta = servico.handler({"body": corpo})
    else:
        resposta = {"statusCode": 200, "body": json.dumps({"status": "ok", "versao": servico.VERSAO})}
    start_response(
        _STATUS.get(resposta["statusCode"], f"{resposta['statusCode']} Erro"),
        [("content-type", "application/json"), ("x-modelo-versao", servico.VERSAO)],
    )
    return [resposta["body"].encode("utf-8")]
