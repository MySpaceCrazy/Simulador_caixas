# Simulador de Geração de Caixas - Versão Consolidada 2D + 3D

import streamlit as st
import pandas as pd
import io
from collections import defaultdict

# --- Configuração inicial ---
st.set_page_config(page_title="Simulador de Caixas", page_icon="📦", layout="wide")
st.title("📦 Simulador de Caixas por Loja e Braço")

# --- Controle de estado ---
if "df_resultado_2d" not in st.session_state:
    st.session_state.df_resultado_2d = None
if "df_resultado_3d" not in st.session_state:
    st.session_state.df_resultado_3d = None
if "arquivo_atual" not in st.session_state:
    st.session_state.arquivo_atual = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 37.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

# --- Parâmetros 2D ---
col1, col2, col3 = st.columns(3)
with col1:
    volume_temp = st.number_input("🔲 Volume máximo por caixa (Litros)", value=st.session_state.volume_maximo, step=0.1)
with col2:
    peso_temp = st.number_input("⚖️ Peso máximo por caixa (KG)", value=st.session_state.peso_maximo, step=0.1)
with col3:
    arquivo = st.file_uploader("📂 Selecionar arquivo (.xlsx)", type=["xlsx"])

col4, col5 = st.columns(2)
with col4:
    ignorar_braco = st.checkbox("🔃 Ignorar braço ao agrupar caixas", value=False)
with col5:
    converter_pac_para_un = st.checkbox("🔄 Converter PAC para UN para otimização", value=False)

# --- Parâmetros 3D ---
st.markdown("---")
st.subheader("📦 Parâmetros do Empacotamento 3D")
col6, col7, col8, col9 = st.columns(4)
with col6:
    comprimento_caixa = st.number_input("📏 Comprimento da caixa 3D (cm)", value=40.0, step=1.0)
with col7:
    largura_caixa = st.number_input("📏 Largura da caixa 3D (cm)", value=30.0, step=1.0)
with col8:
    altura_caixa = st.number_input("📏 Altura da caixa 3D (cm)", value=25.0, step=1.0)
with col9:
    ocupacao_maxima = st.number_input("🔲 % de ocupação máxima (3D)", value=100.0, step=1.0, min_value=1.0, max_value=100.0)

# Detecta troca de arquivo
if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado_2d = None
    st.session_state.df_resultado_3d = None

# --- Função Empacotar 2D ---
def empacotar(df_base, volume_max, peso_max, ignorar_braco, converter_pac_para_un, metodo="FFD"):
    # Mantém seu código 2D original
    # ...
    return pd.DataFrame([])  # Coloque aqui seu empacotar 2D conforme está no seu código completo que já enviou

# --- Função Empacotar 3D Atualizada ---
def empacotar_3d(df_dados, comprimento_caixa, largura_caixa, altura_caixa, peso_max, ocupacao_percentual):
    volume_caixa_cm3 = comprimento_caixa * largura_caixa * altura_caixa
    volume_caixa_litros = (volume_caixa_cm3 * (ocupacao_percentual / 100)) / 1000

    resultado = []
    caixa_id = 1

    df_dados["Numerador"] = pd.to_numeric(df_dados["Numerador"], errors="coerce").fillna(1)
    df_dados["Peso bruto"] = pd.to_numeric(df_dados["Peso bruto"], errors="coerce").fillna(0)
    df_dados["Comprimento"] = pd.to_numeric(df_dados["Comprimento"], errors="coerce").fillna(1)
    df_dados["Largura"] = pd.to_numeric(df_dados["Largura"], errors="coerce").fillna(1)
    df_dados["Altura"] = pd.to_numeric(df_dados["Altura"], errors="coerce").fillna(1)

    itens = []
    for _, row in df_dados.iterrows():
        unidade = row["UM alternativa"]
        qtd = int(row["Numerador"])
        volume_un = (row["Comprimento"] * row["Largura"] * row["Altura"]) / 1000
        peso_un = row["Peso bruto"] / 1000 if row["Unidade de peso"] == "G" else row["Peso bruto"]

        for _ in range(qtd):
            itens.append({
                "ID_Produto": row["Produto"],
                "Volume": volume_un,
                "Peso": peso_un,
                "Descricao": row["Denominador"],
                "UM alternativa": unidade,
                "Loja": row.get("ID_Loja", "Loja_Indefinida"),
                "Braço": row.get("Braço", "Braço_Indefinido")
            })

    caixas = []
    for item in sorted(itens, key=lambda x: x["Volume"], reverse=True):
        colocado = False
        for cx in caixas:
            if (cx["volume"] + item["Volume"] <= volume_caixa_litros) and (cx["peso"] + item["Peso"] <= peso_max):
                cx["volume"] += item["Volume"]
                cx["peso"] += item["Peso"]
                cx["produtos"].append(item)
                colocado = True
                break
        if not colocado:
            caixas.append({
                "ID_Caixa": f"CX3D_{caixa_id}",
                "volume": item["Volume"],
                "peso": item["Peso"],
                "produtos": [item],
                "Loja": item["Loja"],
                "Braço": item["Braço"]
            })
            caixa_id += 1

    for cx in caixas:
        for prod in cx["produtos"]:
            resultado.append({
                "ID_Caixa": cx["ID_Caixa"],
                "ID_Loja": cx["Loja"],
                "Braço": cx["Braço"],
                "ID_Produto": prod["ID_Produto"],
                "Descrição_produto": prod["Descricao"],
                "Volume_item(L)": prod["Volume"],
                "Peso_item(KG)": prod["Peso"],
                "Volume_caixa_total(L)": cx["volume"],
                "Peso_caixa_total(KG)": cx["peso"]
            })

    return pd.DataFrame(resultado)

# --- Execução ---
if arquivo:
    try:
        df_base = pd.read_excel(arquivo, sheet_name="Base")
        df_mestre = pd.read_excel(arquivo, sheet_name="Dados.Mestre")

        if st.button("🚀 Gerar Caixas (2D e 3D)"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            # --- Empacota 2D ---
            df_ffd = empacotar(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, metodo="FFD")
            df_bfd = empacotar(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, metodo="BFD")

            total_ffd = df_ffd["ID_Caixa"].nunique()
            total_bfd = df_bfd["ID_Caixa"].nunique()
            metodo_usado = "BFD" if total_bfd < total_ffd else "FFD"
            st.session_state.df_resultado_2d = df_bfd if metodo_usado == "BFD" else df_ffd

            st.success(f"🏆 Melhor resultado 2D: {metodo_usado} gerou {st.session_state.df_resultado_2d['ID_Caixa'].nunique()} caixas.")

            # --- Empacota 3D ---
            st.session_state.df_resultado_3d = empacotar_3d(df_mestre.copy(), comprimento_caixa, largura_caixa, altura_caixa, peso_temp, ocupacao_maxima)

            total_3d = st.session_state.df_resultado_3d["ID_Caixa"].nunique()
            st.success(f"🏆 Total de caixas geradas no 3D: {total_3d}")

            # --- Mostra resultados ---
            st.subheader("📊 Detalhe caixas 2D")
            st.dataframe(st.session_state.df_resultado_2d)

            st.subheader("📊 Detalhe caixas 3D")
            st.dataframe(st.session_state.df_resultado_3d)

            # --- Baixar relatório ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                st.session_state.df_resultado_2d.to_excel(writer, sheet_name="Resumo Caixas 2D", index=False)
                st.session_state.df_resultado_3d.to_excel(writer, sheet_name="Resumo Caixas 3D", index=False)
            st.download_button("📥 Baixar Relatório Completo", data=buffer.getvalue(), file_name="Relatorio_Caixas_2D_3D.xlsx")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
