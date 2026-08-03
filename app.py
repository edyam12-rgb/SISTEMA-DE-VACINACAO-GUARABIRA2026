import streamlit as st
import pandas as pd
import io

# Configuração da Página
st.set_page_config(page_title="Lançamento - Dia D", page_icon="💉", layout="wide")

# Lista de vacinas mapeada
VACINAS = [
    "ACWY", "ANTIR. HUMANA", "DENGUE", "Dt", "DTP", "DTPa adulto",
    "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", "MENIN. C",
    "PENTA", "PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS",
    "PNEUMO 10", "ROTAVIRUS", "T. VIRAL", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"
]

# Distritos mapeados com as UBSs (Postos) de Guarabira
DISTRITOS_UBS = {
    "DISTRITO 1": ['ALTO', 'B NOVO I', 'B NOVO II', 'CORDEIRO', 'PRIMAVERA'],
    "DISTRITO 2": ['JUA', 'NACOES', 'NORDESTE I', 'NORDESTE II', 'NORDESTE III'],
    "DISTRITO 3": ['ASSIS', 'CLOVIS', 'ROSARIO', 'SÃO JOSE', 'STA TEREZINHA'],
    "DISTRITO 4": ['CACHOEIRA', 'CONTENDAS', 'MUTIRAO', 'PIRPIRI', 'TANANDUBA']
}

# Novos 3 Turnos especificados
TURNOS = [
    "MANHÃ (Até 11h)", 
    "TARDE 1 (Das 11h às 15h)", 
    "TARDE 2 (Das 15h às 16h)"
]

# Inicializa o banco de dados temporário na memória
if 'dados_vacinacao' not in st.session_state:
    st.session_state['dados_vacinacao'] = pd.DataFrame(columns=["DISTRITO", "UNIDADE_SAUDE", "TURNO", "VACINA", "QUANTIDADE"])

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

# Criando as abas de navegação
tab1, tab2 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado"])

# --- ABA 1: LANÇAMENTO DE DADOS ---
with tab1:
    st.markdown("### 📌 Lançamento de Quantidades Aplicadas")
    
    col1, col2, col3 = st.columns(3)
    distrito_selecionado = col1.selectbox("Selecione o Distrito:", list(DISTRITOS_UBS.keys()))
    
    # A lista de UBS muda automaticamente dependendo do distrito
    ubs_selecionada = col2.selectbox("Selecione o Posto de Saúde:", DISTRITOS_UBS[distrito_selecionado])
    turno_selecionado = col3.selectbox("Selecione o Turno:", TURNOS)
    
    st.markdown("---")
    st.write(f"Preencha as vacinas aplicadas em **{ubs_selecionada} ({distrito_selecionado})** no turno **{turno_selecionado}**:")
    
    # Cria a tabela editável
    df_entrada = pd.DataFrame({
        "VACINA": VACINAS,
        "QUANTIDADE": [0] * len(VACINAS)
    })
    
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
        df_salvar = df_editado[df_editado["QUANTIDADE"] > 0].copy()
        
        if not df_salvar.empty:
            df_salvar["DISTRITO"] = distrito_selecionado
            df_salvar["UNIDADE_SAUDE"] = ubs_selecionada
            df_salvar["TURNO"] = turno_selecionado
            
            df_salvar = df_salvar[["DISTRITO", "UNIDADE_SAUDE", "TURNO", "VACINA", "QUANTIDADE"]]
            
            st.session_state['dados_vacinacao'] = pd.concat(
                [st.session_state['dados_vacinacao'], df_salvar], 
                ignore_index=True
            )
            st.success(f"✅ Dados salvos com sucesso para {ubs_selecionada}!")
        else:
            st.warning("Nenhuma vacina informada. Digite valores maiores que 0.")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.markdown("### 📈 Painel Geral e Download")
    
    df_banco = st.session_state['dados_vacinacao']
    
    if not df_banco.empty:
        
        # Filtro principal da visualização do Excel
        filtro = st.radio(
            "Selecione o formato do consolidado:", 
            [
                "Divisão por TURNO e DISTRITO", 
                "Divisão por DISTRITO e POSTO DE SAÚDE (Detalhado)"
            ], 
            horizontal=True
        )
        
        if filtro == "Divisão por TURNO e DISTRITO":
            # Aqui está o que você pediu: Agrupa primeiro pelo TURNO, depois pelo DISTRITO
            consolidado = pd.pivot_table(
                df_banco,
                values='QUANTIDADE',
                index=['TURNO', 'DISTRITO'],
                columns=['VACINA'],
                aggfunc='sum',
                fill_value=0
            )
        else:
            # Mostra o detalhe completo por Distrito -> Posto
            consolidado = pd.pivot_table(
                df_banco,
                values='QUANTIDADE',
                index=['DISTRITO', 'UNIDADE_SAUDE'],
                columns=['VACINA'],
                aggfunc='sum',
                fill_value=0
            )
        
        # Cria a coluna final somando as linhas
        consolidado['TOTAL GERAL'] = consolidado.sum(axis=1)
        
        # Exibe a tabela na tela
        st.dataframe(consolidado, use_container_width=True)
        
        # Totalizador Absoluto
        st.info(f"**Total Absoluto de Doses Aplicadas:** {int(consolidado['TOTAL GERAL'].sum())}")
        
        # Botão de Download para o Excel Final
        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            consolidado.to_excel(writer, sheet_name='CONSOLIDADO')
            df_banco.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada (.xlsx)",
            data=buffer.getvalue(),
            file_name="Relatorio_Final_Dia_D.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Botão de Segurança (Limpar Tudo)
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("⚠️ Reiniciar Sistema (Apagar Todos os Dados)", type="secondary"):
            st.session_state['dados_vacinacao'] = pd.DataFrame(columns=["DISTRITO", "UNIDADE_SAUDE", "TURNO", "VACINA", "QUANTIDADE"])
            st.rerun()
            
    else:
        st.info("👈 Não há dados no sistema. Volte para a aba de Lançamento e insira as informações.")
