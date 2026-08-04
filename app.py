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
    
    # Seleções de Distrito, UBS e Turno (ajuste conforme as variáveis do seu código original)
    distrito_selecionado = st.selectbox("Selecione o Distrito:", ["Distrito 1", "Distrito 2", "Distrito 3", "Distrito 4"])
    ubs_selecionada = st.text_input("Nome da Unidade de Saúde (UBS):")
    turno_selecionado = st.selectbox("Selecione o Turno:", ["Manhã", "Tarde", "Noite"])
    
    st.markdown("---")
    st.markdown("### Digite as quantidades aplicadas por vacina:")
    
    # Exemplo de tabela editável de vacinas (substitua pelo seu dataframe original de vacinas se necessário)
    if "df_vazios" not in st.session_state:
        st.session_state.df_vazios = pd.DataFrame({
            "VACINA": ["BCG", "Hepatite B", "Poliomielite", "Pentavalente", "Tríplice Viral", "Febre Amarela"],
            "QUANTIDADE": [0, 0, 0, 0, 0, 0]
        })
    
    df_editado = st.data_editor(st.session_state.df_vazios, hide_index=True, use_container_width=True)

    if st.button("💾 Salvar Lançamento no Servidor", type="primary"):
        df_salvar = df_editado[df_editado["QUANTIDADE"] > 0].copy()

        if not df_salvar.empty:
            if not ubs_selecionada.strip():
                st.warning("Por favor, preencha o nome da Unidade de Saúde (UBS).")
            else:
                try:
                    # Transação no banco de dados para segurança
                    with conn.session as s:
                        # 1. Limpa os registros anteriores desta UBS e Turno específicos
                        # para evitar que os valores se multipliquem ao salvar novamente.
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

                        # 2. Insere os valores atuais exatos que estão na tela
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
            st.warning("Nenhuma vacina informada. Digite valores maiores que zero.")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.markdown("### 📊 Painel Geral e Download")

    col_btn, _ = st.columns([1, 4])
    if col_btn.button("🔄 Puxar Dados Mais Recentes"):
        st.rerun()

    try:
        # Busca em tempo real da tabela
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
