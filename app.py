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

# --- ABA 1: LANÇAMENTO ---
with tab1:
    st.subheader("Painel de Lançamento por Posto de Saúde")
    
    # Seleção do Distrito
    distrito_selecionado = st.selectbox(
        "Selecione o Distrito:", 
        ["Distrito 1", "Distrito 2", "Distrito 3", "Distrito 4"]
    )
    
    # Dicionário dinâmico com as UBS corretas de acordo com os distritos
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
    
    if categoria_vacina == "💉 Vacinas de Rotina":
        if "df_rotina" not in st.session_state:
            st.session_state.df_rotina = pd.DataFrame({
                "VACINA": [
                    "BCG", 
                    "DTP", 
                    "dT (Dupla Adulto)", 
                    "dTpa", 
                    "Febre Amarela", 
                    "Hepatite A", 
                    "Hepatite B", 
                    "Meningo C", 
                    "Papilomavírus Humano (HPV)", 
                    "Pentavalente", 
                    "Pneumo 10", 
                    "Pneumo 20", 
                    "Poliomielite VIP/VOP", 
                    "Rotavírus", 
                    "Tetra Viral", 
                    "Tríplice Viral (SCR)", 
                    "Varicela"
                ],
                "QUANTIDADE": [0]*17
            })
        df_editado = st.data_editor(st.session_state.df_rotina, hide_index=True, use_container_width=True, key="editor_rotina")
    else:
        if "df_covid" not in st.session_state:
            st.session_state.df_covid = pd.DataFrame({
                "VACINA": [
                    "PFIZER ADULTO", 
                    "PFIZER PED 06 A 4 ANOS", 
                    "PFIZER PED. 05 A 11 ANOS"
                ],
                "QUANTIDADE": [0, 0, 0]
            })
        df_editado = st.data_editor(st.session_state.df_covid, hide_index=True, use_container_width=True, key="editor_covid")

    if st.button("💾 Salvar Lançamento no Servidor", type="primary"):
        df_salvar = df_editado[df_editado["QUANTIDADE"] > 0].copy()

        if not df_salvar.empty:
            try:
                with conn.session as s:
                    vacinas_da_categoria = df_editado["VACINA"].tolist()
                    
                    sql_delete = text("""
                        DELETE FROM registros_vacinacao 
                        WHERE distrito = :distrito 
                          AND unidade_saude = :ubs 
                          AND turno = :turno
                          AND vacina = ANY(:lista_vacinas)
                    """)
                    s.execute(sql_delete, {
                        "distrito": distrito_selecionado,
                        "ubs": ubs_selecionada,
                        "turno": turno_selecionado,
                        "lista_vacinas": vacinas_da_categoria
                    })

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
                    st.success(f"✅ Dados gravados com sucesso para {ubs_selecionada}!")
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")
        else:
            st.warning("Nenhuma quantidade informada nesta categoria. Digite valores maiores que zero.")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.markdown("### 📊 Painel Geral e Download")

    col_btn, _ = st.columns([1, 4])
    if col_btn.button("🔄 Puxar Dados Mais Recentes"):
        st.rerun()

    try:
        df_banco = conn.query("SELECT * FROM registros_vacinacao", ttl=0)
    except Exception as e:
        st.error("Sem comunicação com o banco de dados. Verifique a chave de conexão.")
        df_banco = pd.DataFrame()
        
    if not df_banco.empty:
        filtro = st.radio(
            "Selecione o formato do consolidado:", 
            ["Divisão por TURNO e DISTRITO", "Divisão por DISTRITO e POSTO DE SAÚDE (Detalhado)"], 
            horizontal=True
        )
        
        if filtro == "Divisão por TURNO e DISTRITO":
            consolidado = pd.pivot_table(df_banco, values='quantidade', index=['turno', 'distrito'], columns=['vacina'], aggfunc='sum', fill_value=0)
        else:
            consolidado = pd.pivot_table(df_banco, values='quantidade', index=['distrito', 'unidade_saude'], columns=['vacina'], aggfunc='sum', fill_value=0)
        
        consolidado['TOTAL GERAL'] = consolidado.sum(axis=1)
        st.dataframe(consolidado, use_container_width=True)
        st.info(f"**Total Absoluto de Doses Aplicadas:** {int(consolidado['TOTAL GERAL'].sum())}")
        
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
    else:
        st.info("👈 Nenhum dado recebido do banco ainda.")
