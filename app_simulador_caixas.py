import streamlit as st
import pandas as pd
import io
from collections import defaultdict

st.set_page_config(
    page_title="Simulador de Geração de Caixas por Loja e Braço",
    page_icon="https://raw.githubusercontent.com/MySpaceCrazy/Simulador_Operacional/refs/heads/main/simulador_icon.ico",
    layout="wide"
)

st.title("📦 Simulador de Caixas por Loja e Braço")

# --- Inicializa estados ---
if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None
if "arquivo_atual" not in st.session_state:
    st.session_state.arquivo_atual = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 50.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

# --- Parâmetros Temporários ---
col1, col2, col3 = st.columns(3)

with col1:
    volume_temp = st.number_input("🔲 Volume máximo por caixa (Litros)", value=st.session_state.volume_maximo, step=0.1, key="volume_temp")
with col2:
    peso_temp = st.number_input("⚖️ Peso máximo por caixa (KG)", value=st.session_state.peso_maximo, step=0.1, key="peso_temp")
with col3:
    arquivo = st.file_uploader("📂 Selecionar arquivo de simulação (.xlsx)", type=["xlsx"])

# Opções de Flexibilidade
col4, col5 = st.columns(2)
with col4:
    ignorar_braco = st.checkbox("🔃 Ignorar braço ao agrupar caixas", value=False)
with col5:
    converter_pac_para_un = st.checkbox("🔄 Converter PAC para UN para otimização", value=False)

if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado = None

arquivo_usado = st.session_state.arquivo_atual

# --- Função principal ---
def agrupar_produtos(df_base, volume_maximo, peso_maximo, ignorar_braco, converter_pac_para_un):
    resultado = []
    caixa_id_global = 1

    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce").fillna(0)
    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce").fillna(0)
    df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce").fillna(0)

    df_base.loc[df_base["Unidade de peso"] == "G", "Peso de carga"] /= 1000

    agrupadores = ["ID_Loja"]
    if not ignorar_braco and "Braço" in df_base.columns:
        agrupadores.append("Braço")

    grupos = df_base.groupby(
        agrupadores + ["ID_Produto", "Descrição_produto", "Volume de carga", "Peso de carga", "Unidade med.altern."]
    )[["Qtd.prev.orig.UMA"]].sum().reset_index()

    grupos = grupos.sort_values(by=["Volume de carga", "Peso de carga"], ascending=False)

    for keys, grupo in grupos.groupby(agrupadores):
        loja = keys if isinstance(keys, str) else keys[0]
        braco = keys[1] if not ignorar_braco and len(keys) > 1 else "Todos"

        caixas = []

        for _, prod in grupo.iterrows():
            qtd_restante = int(prod["Qtd.prev.orig.UMA"])
            volume_unit = prod["Volume de carga"]
            peso_unit = prod["Peso de carga"]
            unidade_alt = prod["Unidade med.altern."]
            id_prod = prod["ID_Produto"]
            descricao = prod["Descrição_produto"]

            # Conversão PAC para UN se permitido, mas não quebrar PAC internamente
            pac_tamanho = 1
            if converter_pac_para_un and unidade_alt == "PAC":
                pac_tamanho = int(qtd_restante)
                qtd_restante *= pac_tamanho
                unidade_alt = "UN"

            while qtd_restante > 0:
                alocado = False

                for cx in caixas:
                    max_un_volume = int((volume_maximo - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_maximo - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    # Se PAC, só aloca PAC inteiro
                    if unidade_alt == "PAC" and max_unidades >= 1:
                        max_unidades = 1
                    elif unidade_alt == "PAC":
                        continue

                    if max_unidades > 0:
                        cx["volume"] += volume_unit * max_unidades
                        cx["peso"] += peso_unit * max_unidades
                        cx["produtos"][id_prod]["Qtd"] += max_unidades
                        cx["produtos"][id_prod]["Volume"] += volume_unit * max_unidades
                        cx["produtos"][id_prod]["Peso"] += peso_unit * max_unidades
                        qtd_restante -= max_unidades
                        alocado = True
                        break

                if not alocado:
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

# --- Execução ---
if arquivo_usado is not None:
    try:
        df_base = pd.read_excel(arquivo_usado, sheet_name="Base")
        df_pos_fixa = pd.read_excel(arquivo_usado, sheet_name="Pos.Fixa")

        if st.button("🚀 Gerar Caixas"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_resultado = agrupar_produtos(df_base.copy(), st.session_state.volume_maximo, st.session_state.peso_maximo, ignorar_braco, converter_pac_para_un)
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
                file_name="Simulacao_Caixas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
