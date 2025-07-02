import streamlit as st
import pandas as pd
import io
from collections import defaultdict
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="Simulador de Geração de Caixas por Loja e Braço",
    page_icon="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_Operacional/refs/heads/main/simulador_icon.ico",
    layout="wide"
)

st.title("📦 Simulador de Caixas por Loja e Braço")

# --- Inicializa sessão ---
if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None
if "arquivo" not in st.session_state:
    st.session_state.arquivo = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 50.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

# --- Parâmetros ---
col1, col2, col3 = st.columns(3)

with col1:
    volume_maximo = st.number_input("🔲 Volume máximo por caixa (Litros)", value=st.session_state.volume_maximo, step=0.1)
with col2:
    peso_maximo = st.number_input("⚖️ Peso máximo por caixa (KG)", value=st.session_state.peso_maximo, step=0.1)
with col3:
    arquivo = st.file_uploader("📂 Selecionar arquivo de simulação (.xlsx)", type=["xlsx"])

# Atualiza estado dos parâmetros
st.session_state.volume_maximo = volume_maximo
st.session_state.peso_maximo = peso_maximo

if arquivo is not None:
    st.session_state.arquivo = arquivo

# --- Função de Agrupamento ---
def agrupar_produtos(df_base, df_pos_fixa, volume_maximo, peso_maximo):
    resultado = []
    caixas_geradas = 0

    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce")
    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce")

    for (loja, braco), grupo in df_base.merge(df_pos_fixa, on="ID_Produto").groupby(["ID_Loja", "Braço"]):
        produtos = grupo.to_dict(orient="records")
        caixas = []
        caixa_atual = {"produtos": defaultdict(lambda: {
            "Qtd_separada(UN)": 0,
            "Volume_produto(L)": 0.0,
            "Peso_produto(KG)": 0.0,
            "Descrição_produto": ""
        }), "volume": 0.0, "peso": 0.0}

        for prod in produtos:
            volume_prod = prod["Volume de carga"]
            peso_prod = prod["Peso de carga"]
            qtd_total = prod["Qtd.prev.orig.UMA"]
            unidade_alt = prod["Unidade med.altern."]

            if prod["Unidade de peso"] == "G":
                peso_prod /= 1000

            qtd_total = int(qtd_total) if not pd.isna(qtd_total) else 0

            for _ in range(qtd_total):
                precisa_nova_caixa = False

                if unidade_alt == "PAC":
                    if (volume_prod > volume_maximo) or (peso_prod > peso_maximo):
                        st.warning(f"O produto {prod['ID_Produto']} - {prod['Descrição_produto']} em PAC excede o limite de uma caixa. Verifique os parâmetros.")
                    precisa_nova_caixa = (caixa_atual["volume"] + volume_prod > volume_maximo) or (caixa_atual["peso"] + peso_prod > peso_maximo)
                else:
                    precisa_nova_caixa = (caixa_atual["volume"] + volume_prod > volume_maximo) or (caixa_atual["peso"] + peso_prod > peso_maximo)

                if precisa_nova_caixa:
                    caixas.append(caixa_atual)
                    caixa_atual = {"produtos": defaultdict(lambda: {
                        "Qtd_separada(UN)": 0,
                        "Volume_produto(L)": 0.0,
                        "Peso_produto(KG)": 0.0,
                        "Descrição_produto": ""
                    }), "volume": 0.0, "peso": 0.0}

                item = caixa_atual["produtos"][prod["ID_Produto"]]
                item["Qtd_separada(UN)"] += 1
                item["Volume_produto(L)"] += volume_prod
                item["Peso_produto(KG)"] += peso_prod
                item["Descrição_produto"] = prod["Descrição_produto"]

                caixa_atual["volume"] += volume_prod
                caixa_atual["peso"] += peso_prod

        if caixa_atual["produtos"]:
            caixas.append(caixa_atual)

        for cx in caixas:
            caixas_geradas += 1
            for id_prod, dados in cx["produtos"].items():
                resultado.append({
                    "ID_Loja": loja,
                    "Braço": braco,
                    "ID_Caixa": f"{loja}_{braco}_{caixas_geradas}",
                    "ID_Produto": id_prod,
                    "Descrição_produto": dados["Descrição_produto"],
                    "Qtd_separada(UN)": dados["Qtd_separada(UN)"],
                    "Volume_produto(L)": dados["Volume_produto(L)"],
                    "Peso_produto(KG)": dados["Peso_produto(KG)"],
                    "Volume_caixa_total(L)": cx["volume"],
                    "Peso_caixa_total(KG)": cx["peso"]
                })

    return pd.DataFrame(resultado)

# --- Botão para gerar caixas ---
if st.session_state.arquivo is not None:
    try:
        df_base = pd.read_excel(st.session_state.arquivo, sheet_name="Base")
        df_pos_fixa = pd.read_excel(st.session_state.arquivo, sheet_name="Pos.Fixa")

        if st.button("🚀 Gerar Caixas"):
            df_resultado = agrupar_produtos(df_base, df_pos_fixa, volume_maximo, peso_maximo)
            st.session_state.df_resultado = df_resultado
            st.success(f"Simulação concluída. Total de caixas geradas: {df_resultado['ID_Caixa'].nunique()}")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

# --- Exibe resultado se existir ---
if st.session_state.df_resultado is not None:
    st.dataframe(st.session_state.df_resultado)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        st.session_state.df_resultado.to_excel(writer, sheet_name="Resumo Caixas", index=False)

    st.download_button(
        label="📥 Baixar Relatório Excel",
        data=buffer.getvalue(),
        file_name="Simulacao_Caixas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
