# Simulador de Geração de Caixas 2D + 3D Consolidado

import streamlit as st
import pandas as pd
import io
from collections import defaultdict

# --- Configuração ---
st.set_page_config(page_title="Simulador de Caixas 2D e 3D", page_icon="📦", layout="wide")
st.title("📦 Simulador de Caixas - Empacotamento 2D e 3D")

# --- Estados ---
if "df_2d" not in st.session_state:
    st.session_state.df_2d = None
if "df_3d" not in st.session_state:
    st.session_state.df_3d = None
if "comparativo_2d" not in st.session_state:
    st.session_state.comparativo_2d = None
if "arquivo_atual" not in st.session_state:
    st.session_state.arquivo_atual = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 37.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

# --- Parâmetros 2D ---
st.subheader("⚙️ Parâmetros do Empacotamento 2D")
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
st.subheader("📦 Parâmetros do Empacotamento 3D")
col6, col7, col8, col9 = st.columns(4)
with col6:
    comprimento_caixa = st.number_input("📏 Comprimento da caixa (cm)", value=40.0, step=1.0)
with col7:
    largura_caixa = st.number_input("📏 Largura da caixa (cm)", value=30.0, step=1.0)
with col8:
    altura_caixa = st.number_input("📏 Altura da caixa (cm)", value=25.0, step=1.0)
with col9:
    ocupacao_maxima = st.number_input("🔲 % de ocupação máxima (3D)", value=100.0, step=1.0, min_value=1.0, max_value=100.0)

# --- Detecta troca de arquivo ---
if arquivo and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_2d = None
    st.session_state.df_3d = None
    st.session_state.comparativo_2d = None

# --- Função Empacotamento 2D ---
def empacotar_2d(df_base, volume_max, peso_max, ignorar_braco, converter_pac_para_un, metodo="FFD"):
    resultado = []
    caixa_id = 1
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
            id_prod = prod["ID_Produto"]
            descricao = prod["Descrição_produto"]
            unidade_alt = prod["Unidade med.altern."]

            if converter_pac_para_un and unidade_alt == "PAC":
                unidade_alt = "UN"

            while qtd_restante > 0:
                melhor_idx = -1
                for idx, cx in enumerate(caixas):
                    max_vol = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_vol, max_peso)
                    if max_unidades > 0:
                        melhor_idx = idx
                        break

                if melhor_idx != -1:
                    cx = caixas[melhor_idx]
                    max_vol = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_vol, max_peso)
                    cx["volume"] += volume_unit * max_unidades
                    cx["peso"] += peso_unit * max_unidades
                    qtd_restante -= max_unidades
                else:
                    caixas.append({
                        "ID_Caixa": f"{loja}_{braco}_{caixa_id}",
                        "ID_Loja": loja,
                        "Braço": braco,
                        "volume": 0.0,
                        "peso": 0.0,
                        "produtos": defaultdict(lambda: {"Qtd": 0, "Descricao": descricao})
                    })
                    caixa_id += 1

        for cx in caixas:
            resultado.append({
                "ID_Caixa": cx["ID_Caixa"],
                "ID_Loja": cx["ID_Loja"],
                "Braço": cx["Braço"],
                "Volume_caixa_total(L)": cx["volume"],
                "Peso_caixa_total(KG)": cx["peso"]
            })
    return pd.DataFrame(resultado)

# --- Função Empacotamento 3D ---
def empacotar_3d(df_dados, comp_caixa, larg_caixa, alt_caixa, peso_max, ocupacao_pct):
    volume_caixa_litros = (comp_caixa * larg_caixa * alt_caixa * (ocupacao_pct / 100)) / 1000
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
            itens.append({"ID_Produto": row["Produto"], "Volume": volume_un, "Peso": peso_un, "Descricao": row["Denominador"]})

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

        if st.button("🚀 Rodar Empacotamento Completo 2D + 3D"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_ffd = empacotar_2d(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, metodo="FFD")
            df_bfd = empacotar_2d(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, metodo="BFD")

            total_ffd = df_ffd["ID_Caixa"].nunique()
            total_bfd = df_bfd["ID_Caixa"].nunique()

            st.session_state.df_2d = df_bfd if total_bfd < total_ffd else df_ffd
            metodo_usado = "BFD" if total_bfd < total_ffd else "FFD"

            st.success(f"📦 2D: {metodo_usado} gerou {st.session_state.df_2d['ID_Caixa'].nunique()} caixas.")

            df_caixas = st.session_state.df_2d.drop_duplicates(subset=["ID_Caixa", "Volume_caixa_total(L)", "Peso_caixa_total(KG)"])
            media_vol = (df_caixas["Volume_caixa_total(L)"].mean() / volume_temp) * 100
            media_peso = (df_caixas["Peso_caixa_total(KG)"].mean() / peso_temp) * 100
            st.info(f"🎯 Eficiência 2D - Volume: {media_vol:.1f}%, Peso: {media_peso:.1f}%")

            df_3d = empacotar_3d(df_mestre.copy(), comprimento_caixa, largura_caixa, altura_caixa, peso_temp, ocupacao_maxima)
            st.session_state.df_3d = df_3d
            st.success(f"📦 3D gerou {df_3d['ID_Caixa'].nunique()} caixas.")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                st.session_state.df_2d.to_excel(writer, sheet_name="Resumo 2D", index=False)
                st.session_state.df_3d.to_excel(writer, sheet_name="Resumo 3D", index=False)
            st.download_button("📥 Baixar Excel Consolidado", data=buffer.getvalue(), file_name="Resumo_Caixas.xlsx")

        # Exibição de resultados
        if st.session_state.df_2d is not None:
            st.subheader("📦 Resultado 2D")
            st.dataframe(st.session_state.df_2d)

        if st.session_state.df_3d is not None:
            st.subheader("📦 Resultado 3D")
            st.dataframe(st.session_state.df_3d)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
