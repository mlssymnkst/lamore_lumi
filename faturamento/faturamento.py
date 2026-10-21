import base64
import json
import os
import random
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Faturamento L'amore", page_icon="🌸", layout="wide",
                   initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
CSS_FILE = BASE_DIR / "faturamento.css"
LOGO_FILE = PROJECT_DIR / "images" / "logo redondo.png"
# Onde as telas HTML estão hospedadas (servidor estático / Vercel). O Flask (:5000) é só API.
# Em produção, defina a variável de ambiente FRONT_URL (ex.: https://seu-site.vercel.app).
FRONT_URL = os.getenv("FRONT_URL", "http://localhost:5500").rstrip("/")
LINKS = {
    "inicio": f"{FRONT_URL}/login/html_login.html",
    "insumos": f"{FRONT_URL}/insumos/insumos.html",
    "chatbot": f"{FRONT_URL}/bot/chatbot.html",
    "login": f"{FRONT_URL}/login/html_login.html",  # botão de perfil
}


def carregar_css(caminho):
    if not caminho.is_file():
        st.error(f"Arquivo CSS não encontrado: {caminho}")
        return
    css = caminho.read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


def carregar_logo_base64(caminho):
    if not caminho.is_file():
        return None
    mime = "image/png" if caminho.suffix.lower() == ".png" else "image/jpeg"
    conteudo = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{conteudo}"


def formatar_moeda(valor):
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_compacto(valor):
    """850 -> '850' | 12500 -> '12,5k' | 1250000 -> '1,3M' (para caber nos rótulos)."""
    valor = float(valor)
    if valor >= 1_000_000:
        texto = f"{valor / 1_000_000:.1f}M"
    elif valor >= 1_000:
        texto = f"{valor / 1_000:.1f}k"
    else:
        texto = f"{valor:.0f}"
    return texto.replace(".", ",")


def normalizar(texto):
    """Minúsculas e sem acento, para a busca achar 'cerimônia' digitando 'ceri'."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def filtrar_por_busca(base, termo):
    """Mantém só os pedidos em que TODAS as palavras digitadas aparecem em algum campo
    (nº do pedido, cliente, categoria, valor, data, status ou UF)."""
    palavras = normalizar(termo).split()
    if not palavras or base.empty:
        return base
    texto = (base["pedido"].astype(str) + " " + base["cliente"] + " " + base["categoria"]
             + " " + base["status"] + " " + base["uf"] + " "
             + base["data"].dt.strftime("%d/%m/%Y") + " "
             + base["valor"].map(formatar_moeda)).map(normalizar)
    achou = pd.Series(True, index=base.index)
    for palavra in palavras:
        achou &= texto.str.contains(palavra, regex=False)
    return base[achou]


def criar_card(icone, numero, descricao, classe=""):
    return f"""
    <div class="card">
      <div class="card-icone {classe}">
        <span class="material-icons" aria-hidden="true">{icone}</span>
      </div>
      <div class="card-numero">{numero}</div>
      <div class="card-label">{descricao}</div>
    </div>
    """


def renderizar_cabecalho(logo_data):
    """Desenha menu lateral + cabeçalho e devolve o texto digitado na busca."""
    if logo_data:
        logo_header = f'<img src="{logo_data}" class="logo-header" alt="Logo L’amore">'
    else:
        logo_header = '<div class="logo-fallback">L</div>'

    # Barra de ícones igual à do chatbot (.icon-sidebar / .icon-btn).
    # O HTML deve estar diretamente em st.markdown e não em st.code,
    # st.text ou cercas Markdown ```html.
    st.markdown(
        f"""
        <div class="icon-sidebar">
          <div class="icon-btn" data-tooltip="Menu">
            <span class="material-icons">menu</span>
          </div>
          <a class="icon-btn" href="{LINKS['insumos']}" target="_self"
             data-tooltip="Insumos" aria-label="Insumos">
            <span class="material-icons">inventory_2</span>
          </a>
          <a class="icon-btn" href="{LINKS['chatbot']}" target="_self"
             data-tooltip="Chatbot" aria-label="Chatbot">
            <span class="material-icons">reviews</span>
          </a>
          <div class="icon-btn" data-tooltip="Faturamento" aria-label="Faturamento">
            <span class="material-symbols-outlined">bar_chart</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_titulo, col_acoes = st.columns([3, 2], vertical_alignment="center")
    with col_titulo:
        st.markdown(
            f"""
            <div class="cabecalho">
              <div class="titulo-area">
                {logo_header}
                <span class="titulo">Faturamento L'amore</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_acoes:
        # Mesmo visual das telas de chatbot e insumos: campo de pesquisa + lupa + perfil.
        # O st.form faz Enter e clique na lupa dispararem a mesma busca.
        with st.container(key="topbar_acoes"):
            with st.form("form_busca_faturamento", clear_on_submit=False):
                termo = st.text_input("Pesquisar", key="busca_faturamento",
                                      placeholder="Pesquisar pedido...",
                                      label_visibility="collapsed")
                st.form_submit_button("Pesquisar", help="Pesquisar nos pedidos")  # ícone vem do CSS
            # Perfil: volta para a tela de login, como nas outras telas
            st.markdown(
                f"""<a class="topbar-icon-btn" href="{LINKS['login']}" target="_self"
                       title="Conta" aria-label="Conta (voltar ao login)">
                      <span class="material-icons">person</span>
                    </a>""",
                unsafe_allow_html=True,
            )
    return termo


carregar_css(CSS_FILE)
LOGO_BASE64 = carregar_logo_base64(LOGO_FILE)
TERMO_BUSCA = renderizar_cabecalho(LOGO_BASE64)

# ---------------------------------------------------------------------------
# DADOS (fictícios para demonstração; substituir pela API Flask quando integrada)
# ---------------------------------------------------------------------------
dados = [
    {"pedido": 1, "cliente": "Cliente 1", "categoria": "Categoria 1", "valor": 200.00, "data": "2026-01-01", "status": "Pago", "uf": "SP"},
    {"pedido": 2, "cliente": "Cliente 2", "categoria": "Categoria 2", "valor": 470.00, "data": "2026-01-15", "status": "Pendente", "uf": "RJ"},
    {"pedido": 3, "cliente": "Cliente 3", "categoria": "Categoria 3", "valor": 9200.00, "data": "2026-02-05", "status": "Cancelado", "uf": "MG"},
    {"pedido": 4, "cliente": "Cliente 4", "categoria": "Categoria 4", "valor": 10.00, "data": "2026-02-20", "status": "Pago", "uf": "SP"},
    {"pedido": 5, "cliente": "Cliente 5", "categoria": "Categoria 5", "valor": 1000.00, "data": "2026-03-01", "status": "Pendente", "uf": "PR"},
]
ESTADOS_BR = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
              "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
              "RR", "SC", "SP", "SE", "TO"]


def gerar_pedidos_ficticios(qtd=100, primeiro_numero=6, ano=2026, semente=42):
    """Gera pedidos de exemplo. A semente fixa mantém os mesmos dados a cada execução."""
    rng = random.Random(semente)
    categorias = ["Convites", "Save the date", "Cardápios", "Marcadores de mesa",
                  "Tags e lacres", "Caixas personalizadas", "Papelaria de cerimônia"]
    status = ["Pago", "Pendente", "Cancelado", "Atrasado"]
    pesos_status = [55, 20, 10, 15]
    # Estados com mais peso nas vendas; os demais aparecem com menos frequência
    pesos_uf = {"SP": 10, "RJ": 7, "MG": 7, "PR": 5, "RS": 5, "SC": 4, "BA": 4}
    pesos = [pesos_uf.get(uf, 1.5) for uf in ESTADOS_BR]
    pedidos = []
    for i in range(qtd):
        # os 27 primeiros percorrem todos os estados, para o mapa ter número em cada um
        uf = ESTADOS_BR[i] if i < len(ESTADOS_BR) else rng.choices(ESTADOS_BR, weights=pesos)[0]
        dia = date(ano, 1, 1) + timedelta(days=rng.randrange(365))
        n = primeiro_numero + i
        pedidos.append({
            "pedido": n, "cliente": f"Cliente {n}", "categoria": rng.choice(categorias),
            "valor": round(min(max(rng.lognormvariate(6.3, 0.8), 60), 9500), 2),
            "data": dia.isoformat(), "status": rng.choices(status, weights=pesos_status)[0],
            "uf": uf,
        })
    return pedidos


dados += gerar_pedidos_ficticios(100)
df = pd.DataFrame(dados)
df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
df["status"] = df["status"].fillna("").astype(str).str.strip().str.title()
df["uf"] = df["uf"].fillna("").astype(str).str.upper().str.strip()
# format="mixed" aceita tanto 2026-01-31 quanto 31/01/2026 (vindo da API no futuro)
df["data"] = pd.to_datetime(df["data"], errors="coerce", format="mixed", dayfirst=True)
df = df.dropna(subset=["data"])
df["ano"] = df["data"].dt.year
df["mes"] = df["data"].dt.month

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
TODOS = "Todos"

# Paleta da tela (rosa + bege) — usada nos gráficos e no mapa
COR_BEGE_CARD = "#EFE6DA"
COR_BEGE_ESCURO = "#E2D2BF"
COR_ROSA_CLARO = "#F4C0D1"
COR_ROSA = "#ED93B1"
COR_ROSA_FORTE = "#D4537E"
COR_VINHO = "#72243E"
COR_TEXTO = "#3D342C"

# ---------------------------------------------------------------------------
# FILTROS (listas suspensas)
# ---------------------------------------------------------------------------
st.markdown('<div class="filtros-titulo">Filtros</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    anos = sorted(df["ano"].unique().tolist(), reverse=True)
    ano_sel = st.selectbox("Ano", anos, index=0, key="filtro_ano_faturamento")
with c2:
    opcoes_status = [TODOS] + sorted(df["status"].unique().tolist())
    status_sel = st.selectbox("Status dos pedidos", opcoes_status, index=0,
                              key="filtro_status_faturamento")
with c3:
    opcoes_uf = [TODOS] + sorted(x for x in df["uf"].unique().tolist() if x)
    uf_sel = st.selectbox("Estado (UF)", opcoes_uf, index=0,
                          key="filtro_uf_faturamento")

# A pesquisa do cabeçalho vem primeiro; depois Ano, Status e UF refinam o resultado
df_buscado = filtrar_por_busca(df, TERMO_BUSCA)
mascara = df_buscado["ano"] == ano_sel
if status_sel != TODOS:
    mascara &= df_buscado["status"] == status_sel
if uf_sel != TODOS:
    mascara &= df_buscado["uf"] == uf_sel
df_filtrado = df_buscado[mascara].copy()

if TERMO_BUSCA.strip():
    st.caption(f"Pesquisa por “{TERMO_BUSCA.strip()}”: {len(df_filtrado)} pedido(s) em {ano_sel}. "
               "Para limpar, apague o texto e aperte Enter.")

# ---------------------------------------------------------------------------
# CARDS
# ---------------------------------------------------------------------------
total_pedidos = len(df_filtrado)
atrasados = int((df_filtrado["status"] == "Atrasado").sum())
pendentes = int((df_filtrado["status"] == "Pendente").sum())
faturamento_total = df_filtrado["valor"].sum()  # todos os pedidos, de qualquer status
estado_maior = df_filtrado.groupby("uf")["valor"].sum().idxmax() if not df_filtrado.empty else "—"

cards = [
    ("trending_up", str(total_pedidos), "Número de pedidos", "verde"),
    ("priority_high", str(atrasados), "Em atraso", "vermelho"),
    ("schedule", str(pendentes), "Pendentes", "amarelo"),
    ("payments", formatar_moeda(faturamento_total), "Faturamento total", "azul"),
    ("my_location", estado_maior, "Estado com maior valor", "rosa"),
]
for coluna, item in zip(st.columns(5), cards):
    with coluna:
        st.markdown(criar_card(*item), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# GRÁFICO: ANO INTEIRO (12 meses, mesmo os sem vendas aparecem com R$ 0)
# ---------------------------------------------------------------------------
with st.container(key="box_grafico"):
    st.markdown(f'<div class="secao-titulo">Faturamento mensal de {ano_sel}</div>',
                unsafe_allow_html=True)
    if df_filtrado.empty:
        st.info("Não há pedidos para exibir com os filtros selecionados.")
    else:
        # Soma de TODOS os pedidos filtrados (pago, pendente, atrasado, cancelado...)
        por_mes = df_filtrado.groupby("mes")["valor"].sum().reindex(range(1, 13), fill_value=0)
        qtd_mes = df_filtrado.groupby("mes")["pedido"].count().reindex(range(1, 13), fill_value=0)
        fig = go.Figure(go.Bar(
            x=MESES, y=por_mes.values,
            marker=dict(color=COR_ROSA, line=dict(color=COR_ROSA_FORTE, width=1)),
            text=[formatar_compacto(v) if v else "" for v in por_mes.values],
            textposition="outside", cliponaxis=False,
            textfont=dict(color=COR_TEXTO, size=11),
            customdata=[formatar_moeda(v) for v in por_mes.values],
            hovertemplate="<b>%{x}</b><br>Faturamento: %{customdata}<extra></extra>",
        ))
        fig.update_layout(
            height=320, margin=dict(l=15, r=15, t=25, b=35),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False, font=dict(family="Arial", color=COR_TEXTO),
            yaxis=dict(showgrid=True, gridcolor=COR_BEGE_ESCURO, zeroline=False,
                       title=None, tickprefix="R$ ", separatethousands=True),
            bargap=0.35,
        )
        # Todos os 12 meses sempre rotulados no eixo X
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=MESES,
                         tickmode="array", tickvals=MESES, ticktext=MESES,
                         showticklabels=True, tickfont=dict(color=COR_TEXTO, size=13),
                         showgrid=False, title=None, automargin=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Ver tabela mensal"):
            nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
                     "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            tab_mes = pd.DataFrame({"Mês": nomes, "Pedidos": qtd_mes.values,
                                    "Faturamento": [formatar_moeda(v) for v in por_mes.values]})
            total = pd.DataFrame({"Mês": ["Total do ano"], "Pedidos": [int(qtd_mes.sum())],
                                  "Faturamento": [formatar_moeda(por_mes.sum())]})
            st.dataframe(pd.concat([tab_mes, total], ignore_index=True),
                         use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# TABELA + MAPA
# ---------------------------------------------------------------------------
col_tabela, col_mapa = st.columns([1, 1])

with col_tabela:
    with st.container(key="box_tabela"):
        st.markdown('<div class="secao-titulo">Pedidos</div>', unsafe_allow_html=True)
        if df_filtrado.empty:
            st.info("Nenhum pedido encontrado com os filtros selecionados.")
        else:
            tabela = df_filtrado[["pedido", "cliente", "categoria", "valor", "data", "status"]].copy()
            tabela["valor"] = tabela["valor"].map(formatar_moeda)
            tabela["data"] = tabela["data"].dt.strftime("%d/%m/%Y")
            tabela.columns = ["Nº do pedido", "Cliente", "Categoria", "Valor", "Data", "Status"]
            st.dataframe(tabela, use_container_width=True, hide_index=True)

URL_GEOJSON = ("https://raw.githubusercontent.com/codeforamerica/click_that_hood/"
               "master/public/data/brazil-states.geojson")
# Propriedades onde o arquivo GeoJSON costuma guardar a sigla do estado
CHAVES_SIGLA = ("sigla", "SIGLA", "UF", "uf", "abbrev", "id")


@st.cache_data(ttl=86400)
def carregar_geojson(url):
    with urlopen(url, timeout=15) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def descobrir_chave_sigla(geojson):
    """Acha em qual propriedade do GeoJSON está a sigla (SP, RJ...)."""
    props = geojson["features"][0]["properties"]
    for chave in CHAVES_SIGLA:
        if str(props.get(chave, "")).upper() in ESTADOS_BR:
            return chave
    return None


def centro_do_estado(feature):
    """Centro da caixa que envolve o estado; usado para escrever a sigla no mapa."""
    pontos = []

    def coletar(coords):
        if coords and isinstance(coords[0], (int, float)):
            pontos.append(coords)
        else:
            for item in coords:
                coletar(item)

    coletar(feature["geometry"]["coordinates"])
    lons = [p[0] for p in pontos]
    lats = [p[1] for p in pontos]
    return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


def grafico_estados_em_barras(mapa_df):
    """Plano B quando o mapa não carrega: barras horizontais por UF."""
    dados_uf = mapa_df[mapa_df["Faturamento"] > 0].sort_values("Faturamento")
    fig_b = go.Figure(go.Bar(
        x=dados_uf["Faturamento"], y=dados_uf["UF"], orientation="h",
        marker_color=COR_ROSA,
        customdata=[formatar_moeda(v) for v in dados_uf["Faturamento"]],
        hovertemplate="<b>%{y}</b><br>Faturamento: %{customdata}<extra></extra>",
    ))
    fig_b.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial", color=COR_TEXTO),
        xaxis=dict(showgrid=True, gridcolor=COR_BEGE_ESCURO, tickprefix="R$ "),
    )
    return fig_b


with col_mapa:
    with st.container(key="box_mapa"):
        st.markdown('<div class="secao-titulo">Faturamento por estado</div>',
                    unsafe_allow_html=True)
        # O mapa respeita Ano e Status, mas não o filtro de UF (senão sobraria 1 estado).
        # Soma TODO o faturamento, não só os pedidos pagos.
        base_mapa = df_buscado[df_buscado["ano"] == ano_sel]
        if status_sel != TODOS:
            base_mapa = base_mapa[base_mapa["status"] == status_sel]
        por_estado = (base_mapa.groupby("uf", as_index=False)["valor"].sum()
                      .rename(columns={"uf": "UF", "valor": "Faturamento"}))
        mapa_df = pd.DataFrame({"UF": ESTADOS_BR}).merge(por_estado, on="UF", how="left")
        mapa_df["Faturamento"] = mapa_df["Faturamento"].fillna(0)

        try:
            geojson = carregar_geojson(URL_GEOJSON)
            chave = descobrir_chave_sigla(geojson)
            if chave is None:
                raise ValueError("o GeoJSON não traz a sigla dos estados")

            maximo = max(float(mapa_df["Faturamento"].max()), 1.0)
            fig_mapa = go.Figure(go.Choropleth(
                geojson=geojson, locations=mapa_df["UF"], z=mapa_df["Faturamento"],
                featureidkey=f"properties.{chave}",
                # 0 = bege escuro (o país aparece inteiro); depois vai do rosa claro ao vinho
                colorscale=[[0, COR_BEGE_ESCURO], [0.0001, COR_ROSA_CLARO],
                            [0.5, COR_ROSA], [0.8, COR_ROSA_FORTE], [1, COR_VINHO]],
                zmin=0, zmax=maximo,
                marker_line_color="#FFFFFF", marker_line_width=1,
                colorbar=dict(title=dict(text="R$"), thickness=10, len=0.7,
                              tickprefix="R$ ", tickfont=dict(color=COR_TEXTO)),
                hovertemplate="<b>%{location}</b><br>Faturamento: R$ %{z:,.2f}<extra></extra>",
            ))

            # Sigla + valor (compacto) escritos em cada estado
            valores = dict(zip(mapa_df["UF"], mapa_df["Faturamento"]))
            centros = {}
            for f in geojson["features"]:
                sigla = str(f["properties"].get(chave, "")).upper()
                if sigla in ESTADOS_BR:
                    centros[sigla] = centro_do_estado(f)
            ufs = list(centros.keys())
            fig_mapa.add_trace(go.Scattergeo(
                lon=[centros[u][0] for u in ufs], lat=[centros[u][1] for u in ufs],
                text=[f"<b>{u}</b><br>{formatar_compacto(valores[u])}" for u in ufs],
                mode="text", hoverinfo="skip",
                # texto branco sobre os estados escuros, escuro sobre os claros
                textfont=dict(size=10, family="Arial",
                              color=["#FFFFFF" if valores[u] / maximo > 0.55 else COR_TEXTO
                                     for u in ufs]),
            ))

            # Zoom: enquadra exatamente o Brasil (lon -74 a -34, lat -34 a 5,5)
            fig_mapa.update_geos(
                visible=False, projection_type="mercator",
                lonaxis_range=[-74, -34], lataxis_range=[-34, 5.5],
                bgcolor="rgba(0,0,0,0)",
            )
            fig_mapa.update_layout(height=560, margin=dict(l=0, r=0, t=0, b=0),
                                   paper_bgcolor="rgba(0,0,0,0)", geo_bgcolor="rgba(0,0,0,0)",
                                   showlegend=False)
            st.plotly_chart(fig_mapa, use_container_width=True, config={"displayModeBar": False})
        except Exception as erro:
            st.warning("Não foi possível carregar o mapa; mostrando o ranking por estado.")
            st.caption(f"Detalhe técnico: {erro}")
            if mapa_df["Faturamento"].sum() > 0:
                st.plotly_chart(grafico_estados_em_barras(mapa_df), use_container_width=True,
                                config={"displayModeBar": False})

        estado_consulta = st.selectbox("Consultar estado", ESTADOS_BR,
                                       index=ESTADOS_BR.index("SP"),
                                       key="estado_consulta_faturamento")
        valor_estado = mapa_df.loc[mapa_df["UF"] == estado_consulta, "Faturamento"].iloc[0]
        st.metric(f"Faturamento em {estado_consulta}", formatar_moeda(valor_estado))