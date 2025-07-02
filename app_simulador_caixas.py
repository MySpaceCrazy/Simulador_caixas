# Simulador de Geração de Caixas - Versão 2.1

import streamlit as st
import pandas as pd
import io
from collections import defaultdict

# --- Configuração do Streamlit ---
st.set_page_config(
    page_title="Simulador de Geração de Caixas por Loja e Braço",
    page_icon="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_Operacional/refs/heads/main/simulador_icon.ico",
    layout="wide"
)

st.title("📦 Simulador de Caixas por Loja e Braço")

# --- Controle de estado da aplicação ---
if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None
if "arquivo_atual" not in st.session_state:
    st.session_state.arquivo_atual = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 50.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

# --- Parâmetros da interface ---
col1, col2, col3 = st.columns(3)
with col1:
    volume_temp = st.number_input("🔲 Volume máximo por caixa (Litros)", value=st.session_state.volume_maximo, step=0.1)
with col2:
    peso_temp = st.number_input("⚖️ Peso máximo por caixa (KG)", value=st.session_state.peso_maximo, step=0.1)
with col3:
    arquivo = st.file_uploader("📂 Selecionar arquivo de simulação (.xlsx)", type=["xlsx"])

col4, col5 = st.columns(2)
with col4:
    ignorar_braco = st.checkbox("🔃 Ignorar braço ao agrupar caixas", value=False)
with col5:
    converter_pac_para_un = st.checkbox("🔄 Converter PAC para UN para otimização", value=False)

if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado = None

arquivo_usado = st.session_state.arquivo_atual

# --- Função de Empacotamento Corrigida ---
def empacotar(df_base, volume_max, peso_max, ignorar_braco, converter_pac_para_un, metodo="FFD"):
    resultado = []
    caixa_id_global = 1

    # Normaliza dados
    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce").fillna(0)
    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce").fillna(0)
    df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce").fillna(0)
    df_base.loc[df_base["Unidade de peso"] == "G", "Peso de carga"] /= 1000  # Convertendo gramas para kg

    # Agrupadores padrão
    agrupadores = ["ID_Loja"]
    if not ignorar_braco and "Braço" in df_base.columns:
        agrupadores.append("Braço")

    # Agrupa e calcula corretamente volume e peso por unidade
    grupos = df_base.groupby(
        agrupadores + ["ID_Produto", "Descrição_produto", "Unidade med.altern."]
    ).agg({
        "Qtd.prev.orig.UMA": "sum",
        "Volume de carga": "sum",
        "Peso de carga": "sum"
    }).reset_index()

    grupos["Volume_unit"] = grupos["Volume de carga"] / grupos["Qtd.prev.orig.UMA"].replace(0, 1)
    grupos["Peso_unit"] = grupos["Peso de carga"] / grupos["Qtd.prev.orig.UMA"].replace(0, 1)

    grupos = grupos.sort_values(by=["Volume_unit", "Peso_unit"], ascending=False)

    for keys, grupo in grupos.groupby(agrupadores):
        loja = keys if isinstance(keys, str) else keys[0]
        braco = keys[1] if not ignorar_braco and len(keys) > 1 else "Todos"

        caixas = []

        for _, prod in grupo.iterrows():
            qtd_restante = int(prod["Qtd.prev.orig.UMA"])
            volume_unit = prod["Volume_unit"]
            peso_unit = prod["Peso_unit"]
            unidade_alt = prod["Unidade med.altern."]
            id_prod = prod["ID_Produto"]
            descricao = prod["Descrição_produto"]

            if converter_pac_para_un and unidade_alt == "PAC":
                unidade_alt = "UN"

            while qtd_restante > 0:
                melhor_caixa_idx = -1
                melhor_espaco = None

                for idx, cx in enumerate(caixas):
                    max_un_volume = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    if max_unidades > 0:
                        espaco_restante = (volume_max - (cx["volume"] + volume_unit * max_unidades)) + \
                                          (peso_max - (cx["peso"] + peso_unit * max_unidades))

                        if metodo == "FFD":
                            melhor_caixa_idx = idx
                            break
                        elif metodo == "BFD":
                            if melhor_espaco is None or espaco_restante < melhor_espaco:
                                melhor_espaco = espaco_restante
                                melhor_caixa_idx = idx

                if melhor_caixa_idx != -1:
                    cx = caixas[melhor_caixa_idx]
                    max_un_volume = int((volume_max - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_max - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    cx["volume"] += volume_unit * max_unidades
                    cx["peso"] += peso_unit * max_unidades
                    cx["produtos"][id_prod]["Qtd"] += max_unidades
                    cx["produtos"][id_prod]["Volume"] += volume_unit * max_unidades
                    cx["produtos"][id_prod]["Peso"] += peso_unit * max_unidades
                    qtd_restante -= max_unidades
                else:
                    nova_caixa = {
                        "ID_Caixa": f"{loja}_{braco}_{caixa_id_global}",
                        "ID_Loja": loja,
                        "Braço": braco,
                        "volume": 0.0,
                        "peso": 0.0,
                        "produtos": defaultdict(lambda: {
                            "Qtd": 0, "Volume": 0.0, "Peso": 0.0, "Descricao": descricao
                        })
                    }
                    caixas.append(nova_caixa)
                    caixa_id_global += 1

        for cx in caixas:
            for id_prod, dados in cx["produtos"].items():
                resultado.append({
                    "ID_Caixa": cx["ID_Caixa"],
                    "ID_Loja": cx["ID_Loja"],
                    "Braço": cx["Braço"],
                    "ID_Produto": id_prod,
                    "Descrição_produto": dados["Descricao"],
                    "Qtd_separada(UN)": dados["Qtd"],
                    "Volume_produto(L)": dados["Volume"],
                    "Peso_produto(KG)": dados["Peso"],
                    "Volume_caixa_total(L)": cx["volume"],
                    "Peso_caixa_total(KG)": cx["peso"]
                })

    return pd.DataFrame(resultado)

# --- Execução Principal ---
if arquivo_usado is not None:
    try:
        df_base = pd.read_excel(arquivo_usado, sheet_name="Base")

        if st.button("🚀 Gerar Caixas (Comparar FFD x BFD)"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_ffd = empacotar(df_base.copy(), st.session_state.volume_maximo, st.session_state.peso_maximo, ignorar_braco, converter_pac_para_un, metodo="FFD")
            df_bfd = empacotar(df_base.copy(), st.session_state.volume_maximo, st.session_state.peso_maximo, ignorar_braco, converter_pac_para_un, metodo="BFD")

            total_ffd = df_ffd["ID_Caixa"].nunique()
            total_bfd = df_bfd["ID_Caixa"].nunique()

            st.info(f"📦 FFD gerou: {total_ffd} caixas | BFD gerou: {total_bfd} caixas")

            if total_bfd < total_ffd:
                st.session_state.df_resultado = df_bfd
                metodo_usado = "BFD"
            else:
                st.session_state.df_resultado = df_ffd
                metodo_usado = "FFD"

            st.success(f"Melhor resultado: {metodo_usado} com {st.session_state.df_resultado['ID_Caixa'].nunique()} caixas.")

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

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
