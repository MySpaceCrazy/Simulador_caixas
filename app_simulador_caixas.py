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

# --- Parâmetros ---
col1, col2, col3 = st.columns(3)
with col1:
    volume_temp = st.number_input("🔲 Volume máximo por caixa (Litros)", value=st.session_state.volume_maximo, step=0.1, key="volume_temp")
with col2:
    peso_temp = st.number_input("⚖️ Peso máximo por caixa (KG)", value=st.session_state.peso_maximo, step=0.1, key="peso_temp")
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

# --- Função de empacotamento com heurística ---
def empacotar_produtos(df_base, volume_maximo, peso_maximo, ignorar_braco, converter_pac_para_un, metodo="FFD"):
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

    # Ordena os produtos (decrescente) conforme heurística
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

            pac_tamanho = 1
            if converter_pac_para_un and unidade_alt == "PAC":
                pac_tamanho = int(qtd_restante)
                qtd_restante *= pac_tamanho
                unidade_alt = "UN"

            while qtd_restante > 0:
                melhor_caixa_idx = -1
                melhor_espaco = None

                for idx, cx in enumerate(caixas):
                    max_un_volume = int((volume_maximo - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_maximo - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    if unidade_alt == "PAC" and max_unidades >= 1:
                        max_unidades = 1
                    elif unidade_alt == "PAC":
                        continue

                    if max_unidades > 0:
                        espaco_restante = (volume_maximo - (cx["volume"] + volume_unit * max_unidades)) + \
                                          (peso_maximo - (cx["peso"] + peso_unit * max_unidades))

                        if metodo == "FFD":
                            melhor_caixa_idx = idx
                            break  # FFD: coloca na primeira que couber
                        elif metodo == "BFD":
                            if melhor_espaco is None or espaco_restante < melhor_espaco:
                                melhor_espaco = espaco_restante
                                melhor_caixa_idx = idx

                if melhor_caixa_idx != -1:
                    cx = caixas[melhor_caixa_idx]
                    max_un_volume = int((volume_maximo - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_maximo - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    if unidade_alt == "PAC":
                        max_unidades = 1

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

# --- Execução ---
if arquivo_usado is not None:
    try:
        df_base = pd.read_excel(arquivo_usado, sheet_name="Base")

        if st.button("🚀 Gerar Caixas (FFD x BFD)"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_ffd = empacotar_produtos(df_base.copy(), st.session_state.volume_maximo, st.session_state.peso_maximo, ignorar_braco, converter_pac_para_un, metodo="FFD")
            df_bfd = empacotar_produtos(df_base.copy(), st.session_state.volume_maximo, st.session_state.peso_maximo, ignorar_braco, converter_pac_para_un, metodo="BFD")

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

            # --- Comparativo com sistema original ---
            if "ID_Caixa" in df_base.columns:
                col_comp = ["ID_Loja"] if ignorar_braco else ["ID_Loja", "Braço"]

                comparativo_sistema = df_base.drop_duplicates(subset=col_comp + ["ID_Caixa"])
                comparativo_sistema = comparativo_sistema.groupby(col_comp).agg(Caixas_Sistema=("ID_Caixa", "nunique")).reset_index()

                gerado = st.session_state.df_resultado.drop_duplicates(subset=col_comp + ["ID_Caixa"])
                comparativo_gerado = gerado.groupby(col_comp).agg(Caixas_App=("ID_Caixa", "nunique")).reset_index()

                comparativo = pd.merge(comparativo_sistema, comparativo_gerado, on=col_comp, how="outer").fillna(0)
                comparativo["Diferença"] = comparativo["Caixas_App"] - comparativo["Caixas_Sistema"]

                st.subheader("📊 Comparativo de Caixas por Loja e Braço")
                st.dataframe(comparativo)

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
