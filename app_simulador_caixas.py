# Simulador de Geração de Caixas - Versão Consolidada 2D + 3D Correta

import streamlit as st
import pandas as pd
import io

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
    resultado = []
    caixa_id_global = 1

    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce").fillna(0)
    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce").fillna(0)
    df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce").fillna(1)
    df_base.loc[df_base["Unidade de peso"] == "G", "Peso de carga"] /= 1000

    df_base["Volume unitário"] = df_base["Volume de carga"] / df_base["Qtd.prev.orig.UMA"]
    df_base["Peso unitário"] = df_base["Peso de carga"] / df_base["Qtd.prev.orig.UMA"]
    df_base = df_base[(df_base["Volume unitário"] > 0) & (df_base["Peso unitário"] > 0)]

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
            unidade_alt = prod["Unidade med.altern."]
            if converter_pac_para_un and unidade_alt == "PAC":
                unidade_alt = "UN"

            while qtd_restante > 0:
                melhor_idx = -1
                for idx, cx in enumerate(caixas):
                    max_un_volume = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else 0
                    max_un_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else 0
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)
                    if max_unidades > 0:
                        melhor_idx = idx
                        break

                if melhor_idx != -1:
                    cx = caixas[melhor_idx]
                    max_unidades = min(qtd_restante, int((volume_max - cx["volume"]) // volume_unit), int((peso_max - cx["peso"]) // peso_unit))
                    cx["volume"] += volume_unit * max_unidades
                    cx["peso"] += peso_unit * max_unidades
                    qtd_restante -= max_unidades
                else:
                    caixas.append({
                        "ID_Caixa": f"{loja}_{braco}_{caixa_id_global}",
                        "ID_Loja": loja,
                        "Braço": braco,
                        "volume": 0.0,
                        "peso": 0.0
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

# --- Função Empacotar 3D Corrigida (Agrupamento correto + ID_Caixa no padrão do 2D) ---
def empacotar_3d(df_base, df_mestre, comprimento_caixa, largura_caixa, altura_caixa, peso_max, ocupacao_percentual):
    volume_caixa_litros = (comprimento_caixa * largura_caixa * altura_caixa * (ocupacao_percentual / 100)) / 1000
    resultado = []
    
    df_join = pd.merge(df_base, df_mestre, how='left', left_on=['ID_Produto', 'Unidade med.altern.'], right_on=['Produto', 'UM alternativa'])
    df_join = df_join.dropna(subset=['Comprimento', 'Largura', 'Altura'])

    agrupadores = ["ID_Loja"]
    if "Braço" in df_base.columns:
        agrupadores.append("Braço")

    caixa_id_global = 1

    for keys, grupo in df_join.groupby(agrupadores):
        loja = keys[0] if isinstance(keys, tuple) else keys
        braco = keys[1] if isinstance(keys, tuple) and "Braço" in df_base.columns else "Todos"
        caixas = []

        for _, row in grupo.iterrows():
            qtd = int(row["Qtd solicitada (UN)"])
            volume_un = (row["Comprimento"] * row["Largura"] * row["Altura"]) / 1000
            peso_bruto = row.get("Peso bruto", 0) or 0
            unidade_peso = str(row.get("Unidade de peso", "")).upper()
            peso_un = (peso_bruto / 1000) if unidade_peso == "G" else peso_bruto

            for _ in range(qtd):
                colocado = False
                for cx in caixas:
                    if (cx["volume"] + volume_un <= volume_caixa_litros) and (cx["peso"] + peso_un <= peso_max):
                        cx["volume"] += volume_un
                        cx["peso"] += peso_un
                        cx["produtos"].append(row)
                        colocado = True
                        break

                if not colocado:
                    caixas.append({
                        "ID_Caixa": f"{loja}_{braco}_{caixa_id_global}",
                        "ID_Loja": loja,
                        "Braço": braco,
                        "volume": volume_un,
                        "peso": peso_un,
                        "produtos": [row]
                    })
                    caixa_id_global += 1

        for cx in caixas:
            for prod in cx["produtos"]:
                resultado.append({
                    "ID_Caixa": cx["ID_Caixa"],
                    "ID_Loja": cx["ID_Loja"],
                    "Braço": cx["Braço"],
                    "ID_Produto": prod["ID_Produto"],
                    "Descrição_produto": prod["Descrição_produto"],
                    "Volume_item(L)": (prod["Comprimento"] * prod["Largura"] * prod["Altura"]) / 1000,
                    "Peso_item(KG)": (prod["Peso bruto"] / 1000) if str(prod["Unidade de peso"]).upper() == "G" else prod["Peso bruto"],
                    "Volume_caixa_total(L)": cx["volume"],
                    "Peso_caixa_total(KG)": cx["peso"]
                })

    return pd.DataFrame(resultado)
# --- Execução principal do Simulador ---

if arquivo:
    try:
        df_base = pd.read_excel(arquivo, sheet_name="Base")
        df_mestre = pd.read_excel(arquivo, sheet_name="Dados.Mestre")

        if st.button("🚀 Gerar Caixas (2D e 3D)"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            # Geração 2D com FFD e BFD
            df_ffd = empacotar(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, metodo="FFD")
            df_bfd = empacotar(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, metodo="BFD")

            metodo_usado = "BFD" if df_bfd["ID_Caixa"].nunique() < df_ffd["ID_Caixa"].nunique() else "FFD"
            st.session_state.df_resultado_2d = df_bfd if metodo_usado == "BFD" else df_ffd

            st.info(f"📦 FFD gerou: {df_ffd['ID_Caixa'].nunique()} caixas | BFD gerou: {df_bfd['ID_Caixa'].nunique()} caixas")
            st.success(f"🏆 Melhor resultado: {metodo_usado} com {st.session_state.df_resultado_2d['ID_Caixa'].nunique()} caixas.")

            st.dataframe(st.session_state.df_resultado_2d)

            # Geração 3D
            st.session_state.df_resultado_3d = empacotar_3d(
                df_base.copy(), df_mestre.copy(), comprimento_caixa, largura_caixa,
                altura_caixa, peso_temp, ocupacao_maxima
            )
            st.info(f"📦 Total de caixas geradas (3D): {st.session_state.df_resultado_3d['ID_Caixa'].nunique()}")

            st.dataframe(st.session_state.df_resultado_3d)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")

# --- Download dos resultados ---

st.markdown("---")
st.subheader("💾 Baixar Relatórios")

col_d1, col_d2 = st.columns(2)

with col_d1:
    if st.session_state.df_resultado_2d is not None:
        buffer_2d = io.BytesIO()
        with pd.ExcelWriter(buffer_2d, engine="xlsxwriter") as writer:
            st.session_state.df_resultado_2d.to_excel(writer, index=False, sheet_name="Resultado 2D")
        st.download_button(
            label="⬇️ Baixar Relatório 2D",
            data=buffer_2d.getvalue(),
            file_name="Relatorio_Caixas_2D.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with col_d2:
    if st.session_state.df_resultado_3d is not None:
        buffer_3d = io.BytesIO()
        with pd.ExcelWriter(buffer_3d, engine="xlsxwriter") as writer:
            st.session_state.df_resultado_3d.to_excel(writer, index=False, sheet_name="Resultado 3D")
        st.download_button(
            label="⬇️ Baixar Relatório 3D",
            data=buffer_3d.getvalue(),
            file_name="Relatorio_Caixas_3D.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
