# Simulador de Geração de Caixas - Versão 3.2 (Corrigido)

import streamlit as st
import pandas as pd
import io
from collections import defaultdict

# --- Configuração Streamlit ---
st.set_page_config(page_title="Simulador de Caixas", page_icon="📦", layout="wide")
st.title("📦 Simulador de Caixas por Loja e Braço")

# --- Controle de estado ---
if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None
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

# --- Troca de arquivo ---
if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado = None
    st.session_state.df_resultado_3d = None

# --- Função Empacotar 2D ---
def empacotar(df_base, volume_max, peso_max, ignorar_braco, converter_pac_para_un, metodo="FFD"):
    resultado = []
    caixa_id_global = 1

    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce").fillna(0)
    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce").fillna(0)
    df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce").fillna(1)
    df_base.loc[df_base["Unidade de peso"] == "G", "Peso de carga"] /= 1000
    df_base["Volume unitário"] = df_base["Volume de carga"] / df_base["Qtd.prev.orig.UMA"]
    df_base["Peso unitário"] = df_base["Peso de carga"] / df_base["Qtd.prev.orig.UMA"]

    agrupadores = ["ID_Loja"]
    if not ignorar_braco and "Braço" in df_base.columns:
        agrupadores.append("Braço")

    grupos = df_base.groupby(agrupadores + ["ID_Produto", "Descrição_produto", "Volume unitário", "Peso unitário", "Unidade med.altern."])[["Qtd.prev.orig.UMA"]].sum().reset_index()
    grupos = grupos.sort_values(by=["Volume unitário", "Peso unitário"], ascending=False)

    for keys, grupo in grupos.groupby(agrupadores):
        loja = keys[0] if isinstance(keys, tuple) else keys
        braco = keys[1] if isinstance(keys, tuple) and not ignorar_braco else "Todos"
        caixas = []

        for _, prod in grupo.iterrows():
            qtd_restante = int(prod["Qtd.prev.orig.UMA"])
            volume_unit = prod["Volume unitário"]
            peso_unit = prod["Peso unitário"]

            while qtd_restante > 0:
                melhor_caixa_idx = -1

                for idx, cx in enumerate(caixas):
                    max_un_volume = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    if max_unidades > 0:
                        melhor_caixa_idx = idx
                        break

                if melhor_caixa_idx != -1:
                    cx = caixas[melhor_caixa_idx]
                    max_un_volume = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)
                    cx["volume"] += volume_unit * max_unidades
                    cx["peso"] += peso_unit * max_unidades
                    qtd_restante -= max_unidades
                else:
                    caixas.append({
                        "ID_Caixa": f"{loja}_{braco}_{caixa_id_global}",
                        "ID_Loja": loja,
                        "Braço": braco,
                        "volume": 0.0,
                        "peso": 0.0,
                        "produtos": defaultdict(lambda: {"Qtd": 0})
                    })
                    caixa_id_global += 1

        for cx in caixas:
            resultado.append({
                "ID_Caixa": cx["ID_Caixa"],
                "ID_Loja": cx["ID_Loja"],
                "Braço": cx["Braço"],
                "Volume_caixa_total(L)": cx["volume"],
                "Peso_caixa_total(KG)": cx["peso"]
            })
    return pd.DataFrame(resultado)

# --- Função Empacotar 3D ---
def empacotar_3d(df_dados, comprimento_caixa, largura_caixa, altura_caixa, peso_max, ocupacao_percentual):
    volume_caixa_litros = (comprimento_caixa * largura_caixa * altura_caixa * (ocupacao_percentual / 100)) / 1000
    resultado = []
    caixa_id = 1

    df_dados["Numerador"] = pd.to_numeric(df_dados["Numerador"], errors="coerce").fillna(1)
    df_dados["Peso bruto"] = pd.to_numeric(df_dados["Peso bruto"], errors="coerce").fillna(0)
    df_dados["Comprimento"] = pd.to_numeric(df_dados["Comprimento"], errors="coerce").fillna(1)
    df_dados["Largura"] = pd.to_numeric(df_dados["Largura"], errors="coerce").fillna(1)
    df_dados["Altura"] = pd.to_numeric(df_dados["Altura"], errors="coerce").fillna(1)

    itens = []
    for _, row in df_dados.iterrows():
        qtd = int(row["Numerador"])
        volume_un = (row["Comprimento"] * row["Largura"] * row["Altura"]) / 1000
        peso_un = row["Peso bruto"] / 1000 if row["Unidade de peso"] == "G" else row["Peso bruto"]
        for _ in range(qtd):
            itens.append({
                "ID_Produto": row["Produto"],
                "Volume": volume_un,
                "Peso": peso_un,
                "Descricao": row["Denominador"]
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
            caixas.append({"ID_Caixa": f"CX3D_{caixa_id}", "volume": item["Volume"], "peso": item["Peso"], "produtos": [item]})
            caixa_id += 1

    for cx in caixas:
        for prod in cx["produtos"]:
            resultado.append({
                "ID_Caixa": cx["ID_Caixa"],
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

        if st.button("🚀 Gerar Caixas (FFD 2D)"):
            st.session_state.df_resultado = empacotar(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un)
            st.info(f"📦 FFD gerou: {st.session_state.df_resultado['ID_Caixa'].nunique()} caixas.")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                st.session_state.df_resultado.to_excel(writer, sheet_name="Resumo Caixas 2D", index=False)
            st.download_button("📥 Baixar Relatório Excel (2D)", data=buffer.getvalue(), file_name="Simulacao_Caixas_2D.xlsx")

        if st.button("🚀 Gerar Caixas (3D)"):
            st.session_state.df_resultado_3d = empacotar_3d(df_mestre.copy(), comprimento_caixa, largura_caixa, altura_caixa, peso_temp, ocupacao_maxima)
            st.dataframe(st.session_state.df_resultado_3d)
            buffer_3d = io.BytesIO()
            with pd.ExcelWriter(buffer_3d, engine="xlsxwriter") as writer:
                st.session_state.df_resultado_3d.to_excel(writer, sheet_name="Resumo Caixas 3D", index=False)
            st.download_button("📥 Baixar Relatório Excel (3D)", data=buffer_3d.getvalue(), file_name="Simulacao_Caixas_3D.xlsx")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
