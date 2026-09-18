
"""
app.py — interface. Rode com: streamlit run app.py
"""
import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

from inmet_core import ErroINMET, baixar_periodo, listar_estacoes
import pydeck as pdk

load_dotenv()  # lê o arquivo .env e coloca INMET_TOKEN nas variáveis de ambiente

st.set_page_config(page_title="Download de dados INMET", layout="wide")

# O Streamlit re-executa o script inteiro a cada clique. Sem cache, a lista
# (~260 KB) seria baixada de novo a cada interação. ttl=86400 -> renova 1x/dia.
@st.cache_data(ttl=86400, show_spinner="Carregando lista de estações...")
def carregar_estacoes():
    return listar_estacoes("RS")


def mapa_estacoes(df, codigo_sel):
    """Monta um mapa com todas as estações; a selecionada fica em destaque."""
    dados = df.dropna(subset=["VL_LATITUDE", "VL_LONGITUDE"]).copy()  # sem coordenada não há ponto
    selecionada = dados["CD_ESTACAO"] == codigo_sel
 
    # Colunas de estilo: cor em RGB e raio em metros, definidos por linha
    dados["cor"] = [[220, 40, 40] if s else [40, 100, 200] for s in selecionada]
    dados["raio"] = [7000 if s else 3500 for s in selecionada]
    dados = dados.sort_values("raio")  # a selecionada é desenhada por último (fica por cima)
 
    camada = pdk.Layer(
        "ScatterplotLayer",
        data=dados,
        get_position="[VL_LONGITUDE, VL_LATITUDE]",  # pydeck espera longitude primeiro
        get_fill_color="cor",
        get_radius="raio",
        radius_min_pixels=4,  # garante que o ponto não suma ao afastar o zoom
        pickable=True,        # habilita o tooltip ao passar o mouse
    )
    centro = dados[dados["CD_ESTACAO"] == codigo_sel]
    vista = pdk.ViewState(
        latitude=float(centro["VL_LATITUDE"].iloc[0]),
        longitude=float(centro["VL_LONGITUDE"].iloc[0]),
        zoom=6,
    )
    return pdk.Deck(
        layers=[camada],
        initial_view_state=vista,
        map_style="light",  # mapa base Carto, não exige chave de acesso
        tooltip={"text": "{DC_NOME} ({CD_ESTACAO})"},
    )
 
 
st.title("Download de dados INMET")

st.info(
    "**Como usar:**\n\n"
    "1. Selecione a estação na lista. O mapa serve apenas para conferir a "
    "localização, o nome e o código das estações (passe o mouse sobre os pontos).\n"
    "2. Defina as datas de início e de fim.\n"
    "3. Clique em **Baixar** e, em seguida, em **Salvar CSV**.\n\n"
    "Os horários dos dados estão em UTC (horário local = UTC − 3)."
)
 
try:
    estacoes = carregar_estacoes()
except ErroINMET as e:
    st.error(str(e))
    st.stop()
 
esq, direita = st.columns([1, 1])  # duas colunas de mesma largura
 

# ---------------- Coluna esquerda: escolhas ----------------
with esq:
    so_operantes = st.checkbox("Mostrar apenas estações operantes", value=True)
    filtro = estacoes
    if so_operantes and "CD_SITUACAO" in filtro.columns:
        filtro = filtro[filtro["CD_SITUACAO"] == "Operante"]
 
    opcoes = {f"{r.DC_NOME} ({r.CD_ESTACAO})": r.CD_ESTACAO for r in filtro.itertuples()}
    if not opcoes:
        st.warning("Nenhuma estação encontrada com esse filtro.")
        st.stop()
    rotulo = st.selectbox("Estação", list(opcoes))
    codigo = opcoes[rotulo]
 
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Início", date.today() - timedelta(days=30), format="DD/MM/YYYY")
    fim = c2.date_input("Fim", date.today(), format="DD/MM/YYYY")
 
    token = os.getenv("INMET_TOKEN")
    if token:
        st.caption("Token carregado do arquivo .env.")
    else:
        st.warning("Token não encontrado no .env — o download de dados deve falhar.")
 
    clicou = st.button("Baixar")
 
# ---------------- Coluna direita: mapa ----------------
with direita:
    st.pydeck_chart(mapa_estacoes(filtro, codigo))
    st.caption("Vermelho: estação selecionada. Passe o mouse para ver o nome.")
 
# ---------------- Resultado (largura total) ----------------
if clicou:
    try:
        with st.spinner("Consultando a API do INMET..."):
            df = baixar_periodo(codigo, inicio, fim, token)
    except (ErroINMET, ValueError) as e:
        st.error(str(e))
        st.stop()
 
    st.success(f"{len(df)} registros baixados.")
    st.caption("Atenção: HR_MEDICAO está em UTC (horário local = UTC − 3).")
    st.dataframe(df.head(100))
 
    csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("Salvar CSV", csv,
                       file_name=f"inmet_{codigo}_{inicio}_{fim}.csv", mime="text/csv")
