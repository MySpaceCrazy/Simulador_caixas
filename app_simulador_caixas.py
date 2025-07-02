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

# Se o usuário carregar novo arquivo, atualiza e zera o resultado antigo
if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado = None

arquivo_usado = st.session_state.arquivo_atual

# --- Função principal ---
def agrupar_produtos(df_base, volume_maximo, peso_maximo):
    resultado = []
    caixa_id_global = 1

    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce").fillna(0)
    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce").fillna(0)
    df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce").fillna(0)

    df_base.loc[df_base["Unidade de peso"] == "G", "Peso de carga"] /= 1000

    df_base["Braço"] = df_base["Layout"] if "Layout" in df_base.columns else df_base["Braço"]

    grupos = df_base.groupby([
        "ID_Loja", "Braço", "ID_Produto", "Descrição_produto",
        "Volume de carga", "Peso de carga", "Unidade med.altern."
    ], dropna=False)["Qtd.prev.orig.UMA"].sum().reset_index()

    grupos = grupos.sort_values(by=["Volume de carga", "Peso de carga"], ascending=False)

    for (loja, braco), grupo in grupos.groupby(["ID_Loja", "Braço"]):
        caixas = []

        for _, prod in grupo.iterrows():
            qtd_restante = int(prod["Qtd.prev.orig.UMA"])
            volume_unit = prod["Volume de carga"]
            peso_unit = prod["Peso de carga"]
            unidade_alt = prod["Unidade med.altern."]
            id_prod = prod["ID_Produto"]
            descricao = prod["Descrição_produto"]

            while qtd_restante > 0:
                alocado = False

                for cx in caixas:
                    if unidade_alt == "PAC":
                        if (cx["volume"] + volume_unit <= volume_maximo) and (cx["peso"] + peso_unit <= peso_maximo):
                            cx["volume"] += volume_unit
                            cx["peso"] += peso_unit
                            cx["produtos"][id_prod]["Qtd"] += 1
                            cx["produtos"][id_prod]["Volume"] += volume_unit
                            cx["produtos"][id_prod]["Peso"] += peso_unit
                            alocado = True
                            qtd_restante -= 1
                            break
                    else:
                        max_un_volume = int((volume_maximo - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                        max_un_peso = int((peso_maximo - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                        max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

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
        df_pos_fixa = pd.read_excel(arquivo_usado, sheet_name="Pos.Fixa")  # compatível, mas não utilizado diretamente

        if st.button("🚀 Gerar Caixas"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_resultado = agrupar_produtos(df_base.copy(), st.session_state.volume_maximo, st.session_state.peso_maximo)
            st.session_state.df_resultado = df_resultado
            st.success(f"Simulação concluída. Total de caixas geradas: {df_resultado['ID_Caixa'].nunique()}")

            # --- Comparativo com sistema original ---
            if "ID_Caixa" in df_base.columns:
                original = df_base.dropna(subset=["ID_Caixa"])
                comparativo_sistema = original.groupby(["ID_Loja", "Braço"])["ID_Caixa"].nunique().reset_index(name="Caixas_Sistema")

                gerado = df_resultado.groupby(["ID_Loja", "Braço"])["ID_Caixa"].nunique().reset_index(name="Caixas_App")

                comparativo = pd.merge(comparativo_sistema, gerado, on=["ID_Loja", "Braço"], how="outer").fillna(0)
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
