# simulador_optimizado.py
import streamlit as st
import pandas as pd
import io
from collections import defaultdict

st.set_page_config(
    page_title="Simulador de Geração de Caixas por Loja e Braço",
    page_icon="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_Operacional/refs/heads/main/simulador_icon.ico",
    layout="wide"
)

st.title("📦 Simulador de Caixas por Loja e Braço (Optimizado)")

if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None
if "arquivo_atual" not in st.session_state:
    st.session_state.arquivo_atual = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 37.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

col1, col2, col3 = st.columns(3)

with col1:
    volume_temp = st.number_input("🔲 Volume máximo por caixa (Litros)", value=st.session_state.volume_maximo, step=0.1, key="volume_temp")
with col2:
    peso_temp = st.number_input("⚖️ Peso máximo por caixa (KG)", value=st.session_state.peso_maximo, step=0.1, key="peso_temp")
with col3:
    arquivo = st.file_uploader("📂 Selecionar arquivo de simulação (.xlsx)", type=["xlsx"])

if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado = None

arquivo_usado = st.session_state.arquivo_atual

def expandir_linhas(df):
    dados_expand = []
    for _, row in df.iterrows():
        qtd = int(row["Qtd.prev.orig.UMA"]) if pd.notna(row["Qtd.prev.orig.UMA"]) else 0
        for _ in range(qtd):
            dados_expand.append(row.to_dict())
    return dados_expand

def empacotar_ffd(itens, volume_max, peso_max):
    caixas = []
    itens = sorted(itens, key=lambda x: max(x["Volume de carga"], x["Peso de carga"]), reverse=True)
    for item in itens:
        for caixa in caixas:
            if caixa["volume"] + item["Volume de carga"] <= volume_max and caixa["peso"] + item["Peso de carga"] <= peso_max:
                caixa["itens"].append(item)
                caixa["volume"] += item["Volume de carga"]
                caixa["peso"] += item["Peso de carga"]
                break
        else:
            caixas.append({"itens": [item], "volume": item["Volume de carga"], "peso": item["Peso de carga"]})
    return caixas

def empacotar_bfd(itens, volume_max, peso_max):
    caixas = []
    itens = sorted(itens, key=lambda x: max(x["Volume de carga"], x["Peso de carga"]), reverse=True)
    for item in itens:
        melhor_caixa = None
        melhor_sobra = float("inf")
        for caixa in caixas:
            sobra_vol = volume_max - caixa["volume"] - item["Volume de carga"]
            sobra_peso = peso_max - caixa["peso"] - item["Peso de carga"]
            if sobra_vol >= 0 and sobra_peso >= 0:
                sobra_total = sobra_vol + sobra_peso
                if sobra_total < melhor_sobra:
                    melhor_sobra = sobra_total
                    melhor_caixa = caixa
        if melhor_caixa:
            melhor_caixa["itens"].append(item)
            melhor_caixa["volume"] += item["Volume de carga"]
            melhor_caixa["peso"] += item["Peso de carga"]
        else:
            caixas.append({"itens": [item], "volume": item["Volume de carga"], "peso": item["Peso de carga"]})
    return caixas

def gerar_relatorio(caixas, loja, braco):
    relatorio = []
    for i, cx in enumerate(caixas, 1):
        produtos = defaultdict(lambda: {"Qtd_separada(UN)": 0, "Volume_produto(L)": 0.0, "Peso_produto(KG)": 0.0, "Descrição_produto": ""})
        for item in cx["itens"]:
            p = produtos[item["ID_Produto"]]
            p["Qtd_separada(UN)"] += 1
            p["Volume_produto(L)"] += item["Volume de carga"]
            p["Peso_produto(KG)"] += item["Peso de carga"]
            p["Descrição_produto"] = item["Descrição_produto"]
        for id_prod, dados in produtos.items():
            relatorio.append({
                "ID_Loja": loja,
                "Braço": braco,
                "ID_Caixa": f"{loja}_{braco}_{i}",
                "ID_Produto": id_prod,
                "Descrição_produto": dados["Descrição_produto"],
                "Qtd_separada(UN)": dados["Qtd_separada(UN)"],
                "Volume_produto(L)": dados["Volume_produto(L)"],
                "Peso_produto(KG)": dados["Peso_produto(KG)"],
                "Volume_caixa_total(L)": cx["volume"],
                "Peso_caixa_total(KG)": cx["peso"]
            })
    return pd.DataFrame(relatorio)

if arquivo_usado is not None:
    try:
        df_base = pd.read_excel(arquivo_usado, sheet_name="Base")
        df_pos = pd.read_excel(arquivo_usado, sheet_name="Pos.Fixa")
        if "Braço" not in df_base.columns:
            df_base = df_base.merge(df_pos[["ID_Produto", "Braço"]].drop_duplicates("ID_Produto"), on="ID_Produto", how="left")

        if st.button("🚀 Gerar Caixas"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce")
            df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce")
            df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce")

            resultado_final = []
            for (loja, braco), grupo in df_base.groupby(["ID_Loja", "Braço"]):
                produtos = expandir_linhas(grupo)
                caixas_ffd = empacotar_ffd(produtos, st.session_state.volume_maximo, st.session_state.peso_maximo)
                caixas_bfd = empacotar_bfd(produtos, st.session_state.volume_maximo, st.session_state.peso_maximo)
                melhor = caixas_bfd if len(caixas_bfd) <= len(caixas_ffd) else caixas_ffd
                resultado_final.append(gerar_relatorio(melhor, loja, braco))

            df_resultado = pd.concat(resultado_final, ignore_index=True)
            st.session_state.df_resultado = df_resultado
            st.success(f"Simulação concluída. Total de caixas geradas: {df_resultado['ID_Caixa'].nunique()}")

        if st.session_state.df_resultado is not None:
            st.dataframe(st.session_state.df_resultado)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                st.session_state.df_resultado.to_excel(writer, sheet_name="Resumo Caixas", index=False)

            st.download_button(
                label="📥 Baixar Relatório Excel",
                data=buffer.getvalue(),
                file_name="Simulacao_Caixas_Optimizada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
