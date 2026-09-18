"""
inmet_core.py — lógica de acesso à API do INMET (sem interface).
"""
from datetime import date, timedelta

import pandas as pd
import requests

BASE_URL = "https://apitempo.inmet.gov.br"
LIMITE_DIAS = 180  # a API recusa períodos longos (~6 meses por requisição)

# Colunas de texto/identificação: não devem ser convertidas para número
COLUNAS_TEXTO = {"CD_ESTACAO", "DC_NOME", "UF", "DT_MEDICAO", "HR_MEDICAO"}


class ErroINMET(Exception):
    """Erro próprio: deixa a interface distinguir falha da API de bug no código."""


# ---------------------------------------------------------------------------
# Lista de estações (endpoint aberto, não exige token)
# ---------------------------------------------------------------------------
def listar_estacoes(uf: str | None = None) -> pd.DataFrame:
    """Baixa o catálogo de estações automáticas do INMET."""
    try:
        resp = requests.get(f"{BASE_URL}/estacoes/T", timeout=60)
        resp.raise_for_status()  # levanta erro se status não for 2xx
    except requests.RequestException as e:
        raise ErroINMET(f"Não foi possível obter a lista de estações: {e}") from e

    df = pd.DataFrame(resp.json())
    colunas = ["CD_ESTACAO", "DC_NOME", "SG_ESTADO", "CD_SITUACAO",
               "VL_LATITUDE", "VL_LONGITUDE", "DT_INICIO_OPERACAO"]
    # Mantém só as colunas que existirem (protege contra mudanças na API)
    df = df[[c for c in colunas if c in df.columns]]
    for col in ["VL_LATITUDE", "VL_LONGITUDE"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if uf:
        df = df[df["SG_ESTADO"] == uf]
    return df.sort_values(["SG_ESTADO", "DC_NOME"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Dados das estações (exige token)
# ---------------------------------------------------------------------------
def dividir_periodo(inicio: date, fim: date, passo: int = LIMITE_DIAS):
    """Quebra [inicio, fim] em blocos de até `passo` dias."""
    blocos = []
    atual = inicio
    while atual <= fim:
        bloco_fim = min(atual + timedelta(days=passo - 1), fim)
        blocos.append((atual, bloco_fim))
        atual = bloco_fim + timedelta(days=1)
    return blocos


def montar_url(codigo: str, inicio: date, fim: date, token: str | None = None) -> str:
    if token:
        return f"{BASE_URL}/token/estacao/{inicio}/{fim}/{codigo}/{token}"
    return f"{BASE_URL}/estacao/{inicio}/{fim}/{codigo}"


def baixar_bloco(codigo: str, inicio: date, fim: date, token: str | None = None) -> pd.DataFrame:
    url = montar_url(codigo, inicio, fim, token)
    try:
        resp = requests.get(url, timeout=60)
    except requests.RequestException as e:
        raise ErroINMET(f"Falha de conexão com o INMET: {e}") from e

    if resp.status_code == 204:  # requisição ok, mas sem dados
        return pd.DataFrame()
    if resp.status_code in (401, 403):
        raise ErroINMET("Acesso negado (401/403): token ausente ou inválido.")
    if resp.status_code != 200:
        raise ErroINMET(f"API respondeu {resp.status_code}: {resp.text[:200]}")

    try:
        dados = resp.json()
    except ValueError:
        raise ErroINMET(f"Resposta não é JSON: {resp.text[:200]}")

    if not isinstance(dados, list):
        raise ErroINMET(f"Resposta inesperada: {str(dados)[:200]}")
    return pd.DataFrame(dados)


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """A API devolve tudo como texto; convertemos as medições para número."""
    for col in df.columns:
        if col not in COLUNAS_TEXTO:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def baixar_periodo(codigo: str, inicio: date, fim: date, token: str | None = None) -> pd.DataFrame:
    if inicio > fim:
        raise ValueError("Data inicial é posterior à final.")
    codigo = codigo.strip().upper()

    partes = [baixar_bloco(codigo, i, f, token) for i, f in dividir_periodo(inicio, fim)]
    partes = [p for p in partes if not p.empty]
    if not partes:
        raise ErroINMET(
            "A API não retornou dados. Causas prováveis: token ausente/inválido, "
            "estação fora do catálogo do INMET (ex.: CEMADEN) ou período sem medições."
        )
    return limpar(pd.concat(partes, ignore_index=True))


if __name__ == "__main__":
    # Teste da lista (funciona sem token): python inmet_core.py
    estacoes = listar_estacoes("RS")
    print(estacoes.shape)
    print(estacoes.head(10).to_string())