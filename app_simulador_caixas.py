import streamlit as st
import pandas as pd
import io
from collections import defaultdict

# --- Configuração inicial ---
st.set_page_config(
    page_title="Simulador de Geração de Caixas por Loja e Braço",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Simulador de Caixas por Loja e Braço")

# --- Sessão: variáveis persistentes ---
if "df_resultado" not in st.session_state:
    st.session_state.df_resultado = None
if "arquivo_atual" not in st.session_state:
    st.session_state.arquivo_atual = None
if "volume_maximo" not in st.session_state:
    st.session_state.volume_maximo = 50.0
if "peso_maximo" not in st.session_state:
    st.session_state.peso_maximo = 20.0

# --- Parâmetros do usuário ---
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

# --- Atualização de arquivo selecionado ---
if arquivo is not None and arquivo != st.session_state.arquivo_atual:
    st.session_state.arquivo_atual = arquivo
    st.session_state.df_resultado = None

arquivo_usado = st.session_state.arquivo_atual

# --- Função principal de agrupamento ---
def agrupar_produtos(df_base, volume_maximo, peso_maximo, ignorar_braco, converter_pac_para_un, modo="FFD"):
    resultado = []
    caixa_id_global = 1

    # Conversões e garantias de tipos
    df_base["Peso de carga"] = pd.to_numeric(df_base["Peso de carga"], errors="coerce").fillna(0)
    df_base["Volume de carga"] = pd.to_numeric(df_base["Volume de carga"], errors="coerce").fillna(0)
    df_base["Qtd.prev.orig.UMA"] = pd.to_numeric(df_base["Qtd.prev.orig.UMA"], errors="coerce").fillna(0)
    df_base.loc[df_base["Unidade de peso"] == "G", "Peso de carga"] /= 1000

    # Verifica se 'Braço' existe
    if "Braço" not in df_base.columns:
        df_base["Braço"] = "Desconhecido"

    agrupadores = ["ID_Loja"]
    if not ignorar_braco:
        agrupadores.append("Braço")

    grupos = df_base.groupby(
        agrupadores + ["ID_Produto", "Descrição_produto", "Volume de carga", "Peso de carga", "Unidade med.altern."]
    )[["Qtd.prev.orig.UMA"]].sum().reset_index()

    grupos = grupos.sort_values(by=["Volume de carga", "Peso de carga"], ascending=False)

    for keys, grupo in grupos.groupby(agrupadores):
        loja = keys[0] if isinstance(keys, tuple) else keys
        braco = keys[1] if not ignorar_braco and isinstance(keys, tuple) and len(keys) > 1 else "Todos"

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
                melhor_caixa = None
                melhor_aproveitamento = None

                for cx in caixas:
                    max_un_volume = int((volume_maximo - cx["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_maximo - cx["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    if unidade_alt == "PAC":
                        max_unidades = 1 if max_un_volume >= 1 and max_un_peso >= 1 else 0

                    if max_unidades > 0:
                        if modo == "FFD":
                            melhor_caixa = cx
                            break
                        elif modo == "BFD":
                            aproveitamento = (cx["volume"] + volume_unit * max_unidades) / volume_maximo
                            if melhor_aproveitamento is None or aproveitamento > melhor_aproveitamento:
                                melhor_caixa = cx
                                melhor_aproveitamento = aproveitamento

                if melhor_caixa:
                    max_un_volume = int((volume_maximo - melhor_caixa["volume"]) // volume_unit) if volume_unit > 0 else qtd_restante
                    max_un_peso = int((peso_maximo - melhor_caixa["peso"]) // peso_unit) if peso_unit > 0 else qtd_restante
                    max_unidades = min(qtd_restante, max_un_volume, max_un_peso)

                    if unidade_alt == "PAC":
                        max_unidades = 1

                    melhor_caixa["volume"] += volume_unit * max_unidades
                    melhor_caixa["peso"] += peso_unit * max_unidades
                    melhor_caixa["produtos"][id_prod]["Qtd"] += max_unidades
                    melhor_caixa["produtos"][id_prod]["Volume"] += volume_unit * max_unidades
                    melhor_caixa["produtos"][id_prod]["Peso"] += peso_unit * max_unidades
                    qtd_restante -= max_unidades
                else:
                    nova_caixa = {
                        "ID_Caixa": f"{loja}_{braco}_{caixa_id_global}",
                        "ID_Loja": loja,
                        "Braço": braco,
                        "volume": 0.0,
                        "peso": 0.0,
                        "produtos": defaultdict(lambda: {"Qtd": 0, "Volume": 0.0, "Peso": 0.0, "Descricao": descricao})
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

# --- Execução principal ---
if arquivo_usado is not None:
    try:
        df_base = pd.read_excel(arquivo_usado, sheet_name="Base")

        # --- Se existir aba Pos.Fixa, fazer merge para completar informações ---
        if "Pos.Fixa" in pd.ExcelFile(arquivo_usado).sheet_names:
            df_pos_fixa = pd.read_excel(arquivo_usado, sheet_name="Pos.Fixa")
            if "Braço" not in df_base.columns and "Braço" in df_pos_fixa.columns:
                df_base = df_base.merge(df_pos_fixa[["ID_Produto", "Braço"]], on="ID_Produto", how="left")

        if st.button("🚀 Gerar Caixas"):
            st.session_state.volume_maximo = volume_temp
            st.session_state.peso_maximo = peso_temp

            df_ffd = agrupar_produtos(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, modo="FFD")
            df_bfd = agrupar_produtos(df_base.copy(), volume_temp, peso_temp, ignorar_braco, converter_pac_para_un, modo="BFD")

            total_ffd = df_ffd["ID_Caixa"].nunique()
            total_bfd = df_bfd["ID_Caixa"].nunique()

            st.info(f"✅ FFD: {total_ffd} caixas | ✅ BFD: {total_bfd} caixas")

            if total_bfd < total_ffd:
                melhor_df = df_bfd
                melhor_modo = "BFD"
            else:
                melhor_df = df_ffd
                melhor_modo = "FFD"

            st.session_state.df_resultado = melhor_df
            st.success(f"🏆 Melhor Resultado: {melhor_modo} com {melhor_df['ID_Caixa'].nunique()} caixas")

            # Comparativo com sistema anterior
            if "ID_Caixa" in df_base.columns:
                col_comp = ["ID_Loja"]
                if not ignorar_braco:
                    col_comp.append("Braço")

                comp_sistema = df_base.drop_duplicates(subset=col_comp + ["ID_Caixa"])
                comp_sistema = comp_sistema.groupby(col_comp).agg(Caixas_Sistema=("ID_Caixa", "nunique")).reset_index()

                comp_gerado = melhor_df.drop_duplicates(subset=col_comp + ["ID_Caixa"])
                comp_gerado = comp_gerado.groupby(col_comp).agg(Caixas_App=("ID_Caixa", "nunique")).reset_index()

                comparativo = pd.merge(comp_sistema, comp_gerado, on=col_comp, how="outer").fillna(0)
                comparativo["Diferença"] = comparativo["Caixas_App"] - comparativo["Caixas_Sistema"]

                st.subheader("📊 Comparativo por Loja e Braço")
                st.dataframe(comparativo)

        if st.session_state.df_resultado is not None:
            st.subheader("📦 Resumo das Caixas Geradas")
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
        st.error(f"❌ Erro: {type(e).__name__} - {e}")
