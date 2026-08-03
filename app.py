import streamlit as st
import pandas as pd
import io

# Configuração da Página
st.set_page_config(page_title="Lançamento - Dia D", page_icon="💉", layout="wide")

# Lista padrão de vacinas baseada nas suas planilhas
VACINAS = [
    "ACWY", "ANTIR. HUMANA", "DENGUE", "Dt", "DTP", "DTPa adulto",
    "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", "MENIN. C",
    "PENTA", "PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PNEUMO 10", "ROTAVIRUS",
    "T. VIRAL", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"
]

DISTRITOS = ["DISTRITO 1", "DISTRITO 2", "DISTRITO 3", "DISTRITO 4"]
TURNOS = ["MANHÃ", "TARDE"]

# Inicializa o "banco de dados" temporário na memória do sistema
if 'dados_vacinacao' not in st.session_state:
    st.session_state['dados_vacinacao'] = pd.DataFrame(columns=["DISTRITO", "TURNO", "VACINA", "QUANTIDADE"])

st.title("💉 Sistema de Vacinação - Dia D")

# Criando as abas de navegação
tab1, tab2 = st.tabs(["📝 Lançamento de Dados", "📊 Relatório Consolidado"])

# --- ABA 1: LANÇAMENTO DE DADOS ---
with tab1:
    st.subheader("Inserir Quantidades Aplicadas")
    
    col1, col2 = st.columns(2)
    distrito_selecionado = col1.selectbox("Selecione o Distrito", DISTRITOS)
    turno_selecionado = col2.selectbox("Selecione o Turno", TURNOS)
    
    st.markdown("---")
    st.write("Preencha as quantidades na coluna correspondente e clique em salvar:")
    
    # Cria a tabela editável
    df_entrada = pd.DataFrame({
        "VACINA": VACINAS,
        "QUANTIDADE": [0] * len(VACINAS)
    })
    
    # Exibe a tabela na tela para o usuário digitar
    df_editado = st.data_editor(
        df_entrada,
        hide_index=True,
        use_container_width=True,
        column_config={
            "VACINA": st.column_config.TextColumn("Imunobiológico", disabled=True),
            "QUANTIDADE": st.column_config.NumberColumn("Quantidade Aplicada", min_value=0, step=1)
        }
    )
    
    # Botão para salvar
    if st.button("💾 Salvar Lançamento", type="primary"):
        # Pega apenas as linhas onde o usuário digitou mais de 0 vacinas
        df_salvar = df_editado[df_editado["QUANTIDADE"] > 0].copy()
        
        if not df_salvar.empty:
            df_salvar["DISTRITO"] = distrito_selecionado
            df_salvar["TURNO"] = turno_selecionado
            
            # Organiza a ordem das colunas
            df_salvar = df_salvar[["DISTRITO", "TURNO", "VACINA", "QUANTIDADE"]]
            
            # Salva no banco de dados da sessão
            st.session_state['dados_vacinacao'] = pd.concat(
                [st.session_state['dados_vacinacao'], df_salvar], 
                ignore_index=True
            )
            st.success(f"✅ Dados salvos com sucesso para {distrito_selecionado} no turno da {turno_selecionado}!")
        else:
            st.warning("Nenhuma vacina preenchida. Digite quantidades maiores que zero para salvar.")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.subheader("Painel Geral")
    
    df_banco = st.session_state['dados_vacinacao']
    
    if not df_banco.empty:
        # Filtros de visualização
        filtro_turno = st.radio("Exibir consolidação por:", ["Ambos (Total Geral)", "Somente MANHÃ", "Somente TARDE"], horizontal=True)
        
        df_view = df_banco.copy()
        if filtro_turno == "Somente MANHÃ":
            df_view = df_view[df_view["TURNO"] == "MANHÃ"]
        elif filtro_turno == "Somente TARDE":
            df_view = df_view[df_view["TURNO"] == "TARDE"]
        
        # Cria a matriz igual à planilha original (Distritos nas linhas, Vacinas nas colunas)
        if not df_view.empty:
            consolidado = pd.pivot_table(
                df_view,
                values='QUANTIDADE',
                index=['DISTRITO'],
                columns=['VACINA'],
                aggfunc='sum',
                fill_value=0
            )
            
            # Cria a coluna final somando tudo
            consolidado['TOTAL GERAL'] = consolidado.sum(axis=1)
            
            # Exibe a tabela na tela
            st.dataframe(consolidado, use_container_width=True)
            
            # Métricas
            st.info(f"**Total Absoluto de Doses Aplicadas no Filtro Atual:** {int(consolidado['TOTAL GERAL'].sum())} doses.")
            
            # Botão de Download
            st.markdown("---")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                consolidado.to_excel(writer, sheet_name='CONSOLIDADO')
                # Salva também um histórico de quem lançou o que
                df_banco.to_excel(writer, sheet_name='HISTÓRICO LANÇAMENTOS', index=False)
            
            st.download_button(
                label="📥 Baixar Planilha Pronta",
                data=buffer.getvalue(),
                file_name="Relatorio_Consolidado_Dia_D.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Botão de segurança para zerar o sistema
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("🗑️ Apagar todos os dados do sistema", type="secondary"):
                st.session_state['dados_vacinacao'] = pd.DataFrame(columns=["DISTRITO", "TURNO", "VACINA", "QUANTIDADE"])
                st.rerun()
        else:
            st.warning("Não há lançamentos para este filtro específico ainda.")
            
    else:
        st.info("👈 Nenhum dado lançado ainda. Vá na aba 'Lançamento de Dados' e comece a preencher.")