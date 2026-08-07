import streamlit as st
import pandas as pd
from sqlalchemy import text
import io

# Configuração da página
st.set_page_config(page_title="Sistema de Lançamento de Vacinas - Dia D", layout="wide")

# Conexão com o banco de dados PostgreSQL via Streamlit
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Erro ao configurar a conexão com o banco de dados.")

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

# Abas do sistema
tab1, tab2 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado"])

# Listas base de vacinas oficiais incluindo a T. Viral 2ª Dose
lista_rotina = [
    "ACWY", "ANTIR. HUMANA", "DENGUE", "DTP", "DTPa adulto", "Dt", 
    "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", 
    "MENIN. C", "PENTA", "PNEUMO 10", "PNEUMO 20", "ROTAVIRUS", 
    "T. VIRAL", "T. VIRAL 2ª DOSE", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"
]

lista_covid = [
    "PFIZER ADULTO", 
    "PFIZER PED 06 A 4 ANOS", 
    "PFIZER PED. 05 A 11 ANOS"
]

# --- ABA 1: LANÇAMENTO ---
with tab1:
    st.subheader("Painel de Lançamento por Posto de Saúde")
    
    # Seleção do Distrito
    distrito_selecionado = st.selectbox(
        "Selecione o Distrito:", 
        ["Distrito 1", "Distrito 2", "Distrito 3", "Distrito 4"]
    )
    
    # Dicionário dinâmico com as UBS corretas de acordo com os distritos de Guarabira
    ubs_por_distrito = {
        "Distrito 1": ["Alto", "Bairro Novo I", "Bairro Novo II", "Cordeiro", "Primavera"],
        "Distrito 2": ["Juá", "Nações", "Nordeste I", "Nordeste II", "Nordeste III"],
        "Distrito 3": ["Assis", "Clóvis Bezerra", "Rosário", "São José", "Santa Terezinha"],
        "Distrito 4": ["Cachoeira", "Contendas", "Mutirão", "Pirpiri (São Francisco de Assis)", "Tananduba"]
    }
    
    ubs_selecionada = st.selectbox(
        "Selecione a Unidade de Saúde (UBS):", 
        ubs_por_distrito.get(distrito_selecionado, [])
    )
    
    # Seleção de Turnos atualizada
    turno_selecionado = st.selectbox(
        "Selecione o Turno:", 
        ["Manhã (até as 11h)", "Tarde (das 11h às 15h)", "Tarde (das 15h às 16h)"]
    )
    
    st.markdown("---")
    
    # Seleção de Categoria para facilitar o lançamento
    categoria_vacina = st.radio(
        "Selecione o grupo de vacinas:",
        ["💉 Vacinas de Rotina", "🦠 Vacinas COVID-19"],
        horizontal=True
    )

    # Busca valores já salvos no banco para esta UBS e Turno
    try:
        df_existente = conn.query(
            "SELECT vacina, quantidade FROM registros_vacinacao WHERE distrito = :d AND unidade_saude = :u AND turno = :t",
            params={"d": distrito_selecionado, "u": ubs_selecionada, "t": turno_selecionado},
            ttl=0
        )
    except:
        df_existente = pd.DataFrame()

    if categoria_vacina == "💉 Vacinas de Rotina":
        dic_quantidades = {v: 0 for v in lista_rotina}
        if not df_existente.empty:
            for _, row in df_existente.iterrows():
                if row["vacina"] in dic_quantidades:
                    dic_quantidades[row["vacina"]] = row["quantidade"]
        
        df_tela = pd.DataFrame({"VACINA": lista_rotina, "QUANTIDADE": [dic_quantidades[v] for v in lista_rotina]})
        df_editado = st.data_editor(df_tela, hide_index=True, use_container_width=True, key="editor_rotina")
    else:
        dic_quantidades = {v: 0 for v in lista_covid}
        if not df_existente.empty:
            for _, row in df_existente.iterrows():
                if row["vacina"] in dic_quantidades:
                    dic_quantidades[row["vacina"]] = row["quantidade"]

        df_tela = pd.DataFrame({"VACINA": lista_covid, "QUANTIDADE": [dic_quantidades[v] for v in lista_covid]})
        df_editado = st.data_editor(df_tela, hide_index=True, use_container_width=True, key="editor_covid")

    if st.button("💾 Salvar Lançamento no Servidor", type="primary"):
        df_salvar = df_editado[df_editado["QUANTIDADE"] > 0].copy()

        try:
            with conn.session as s:
                sql_delete = text("""
                    DELETE FROM registros_vacinacao 
                    WHERE distrito = :distrito 
                      AND unidade_saude = :ubs 
                      AND turno = :turno
                """)
                s.execute(sql_delete, {
                    "distrito": distrito_selecionado,
                    "ubs": ubs_selecionada,
                    "turno": turno_selecionado
                })

                if not df_salvar.empty:
                    for _, row in df_salvar.iterrows():
                        sql_insert = text("""
                            INSERT INTO registros_vacinacao (distrito, unidade_saude, turno, vacina, quantidade)
                            VALUES (:distrito, :ubs, :turno, :vacina, :quantidade)
                        """)
                        s.execute(sql_insert, {
                            "distrito": distrito_selecionado,
                            "ubs": ubs_selecionada,
                            "turno": turno_selecionado,
                            "vacina": row["VACINA"],
                            "quantidade": row["QUANTIDADE"]
                        })
                
                s.commit()
                st.success(f"✅ Lançamento salvo com sucesso para {ubs_selecionada} ({turno_selecionado})!")
        except Exception as e:
            st.error(f"Erro ao salvar no banco: {e}")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.markdown("### 📊 Relatório Consolidado (Formato Oficial)")

    col_btn1, _ = st.columns([1, 4])
    with col_btn1:
        if st.button("🔄 Atualizar Relatório"):
            st.rerun()

    try:
        df_banco = conn.query("SELECT * FROM registros_vacinacao", ttl=0)
    except Exception as e:
        st.error("Sem comunicação com o banco de dados. Verifique a chave de conexão.")
        df_banco = pd.DataFrame()
        
    if not df_banco.empty:
        with st.expander("⚠️ Área Administrativa: Limpar Banco de Dados"):
            st.warning("Atenção: Esta ação irá apagar **todos** os lançamentos salvos no servidor permanentemente.")
            confirmacao = st.checkbox("Sim, tenho certeza que desejo apagar todo o histórico de lançamentos.")
            if st.button("🗑️ Apagar Todos os Dados do Servidor", type="primary"):
                if confirmacao:
                    try:
                        with conn.session as s:
                            s.execute(text("DELETE FROM registros_vacinacao"))
                            s.commit()
                        st.success("🗑️ Banco de dados limpo com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao limpar banco: {e}")
                else:
                    st.error("Marque a caixa de confirmação para poder apagar os dados.")

        # Classificação detalhada para o relatório por turno (Rotina e Covid)
        def classificar_por_turno(nome):
            nome = str(nome).upper()
            if "COVID" in nome or "PFIZER" in nome:
                return "COVID"
            return "ROTINA"

        df_banco['GRUPO_TURNO'] = df_banco['vacina'].apply(classificar_por_turno)
        
        # 1. Consolidado por Turno (Mostrando Rotina e Covid conforme solicitado)
        consolidado_turno = df_banco.groupby(['turno', 'distrito', 'GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
        for col in ['ROTINA', 'COVID']:
            if col not in consolidado_turno.columns:
                consolidado_turno[col] = 0
        consolidado_turno['TOTAL'] = consolidado_turno.sum(axis=1)

        turnos = df_banco['turno'].unique()
        for t in turnos:
            st.markdown(f"#### 🕒 Turno: {t}")
            st.dataframe(consolidado_turno.loc[t], use_container_width=True)
        
        # 2. TOTAL GERAL ACUMULADO (Descontando Influenza, T. Viral 1ª, T. Viral 2ª e F. Amarela do Total de Rotina)
        st.markdown("---")
        st.markdown("#### 🏁 TOTAL GERAL (Acumulado com Descontos Oficiais)")

        # Cria colunas específicas detalhadas para o cálculo do total geral
        df_banco['VAC_UPPER'] = df_banco['vacina'].str.upper()
        
        # Pivot completo por vacina para isolar os descontos necessários
        tabela_completa = df_banco.pivot_table(index='distrito', columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0)
        
        # Garante a existência das colunas necessárias
        for v in ['INFLUENZA', 'T. VIRAL', 'T. VIRAL 2ª DOSE', 'F. AMARELA']:
            if v not in tabela_completa.columns:
                tabela_completa[v] = 0

        # Soma total geral de rotina por distrito
        rotina_total = df_banco[df_banco['GRUPO_TURNO'] == 'ROTINA'].groupby('distrito')['quantidade'].sum()
        covid_total = df_banco[df_banco['GRUPO_TURNO'] == 'COVID'].groupby('distrito')['quantidade'].sum()

        df_geral = pd.DataFrame(index=tabela_completa.index)
        df_geral['ROTINA'] = rotina_total
        df_geral['COVID'] = covid_total
        df_geral['INFLUENZA'] = tabela_completa['INFLUENZA']
        df_geral['T VIRAL (1ª D)'] = tabela_completa['T. VIRAL']
        df_geral['T VIRAL (2ª D)'] = tabela_completa['T. VIRAL 2ª DOSE']
        df_geral['F. AMARELA'] = tabela_completa['F. AMARELA']
        
        # Cálculo do Total Geral descontando os itens solicitados do total de rotina + covid
        df_geral['TOTAL GERAL'] = (
            df_geral['ROTINA'].fillna(0) + df_geral['COVID'].fillna(0) 
            - df_geral['INFLUENZA'] - df_geral['T VIRAL (1ª D)'] 
            - df_geral['T VIRAL (2ª D)'] - df_geral['F. AMARELA']
        )
        
        # Preenche vazios com 0
        df_geral = df_geral.fillna(0)

        st.dataframe(df_geral, use_container_width=True)

        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            consolidado_turno.to_excel(writer, sheet_name='CONSOLIDADO_TURNO')
            df_geral.to_excel(writer, sheet_name='TOTAL_GERAL')
            df_banco.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada (.xlsx)",
            data=buffer.getvalue(),
            file_name="Relatorio_Final_Dia_D.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("👈 Nenhum dado recebido do banco ainda.")
