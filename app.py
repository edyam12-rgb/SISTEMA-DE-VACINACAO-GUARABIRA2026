import streamlit as st
import pandas as pd
import io
from sqlalchemy import text

# Configuração da Página
st.set_page_config(page_title="Lançamento - Dia D", page_icon="💉", layout="wide")

# Inicializa conexão oficial com o PostgreSQL via Streamlit
conn = st.connection("postgresql", type="sql")

# Lista de vacinas 
VACINAS = [
    "ACWY", "ANTIR. HUMANA", "COVID BIVALENTE", "DENGUE", "Dt", "DTP", "DTPa adulto",
    "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", "MENIN. C",
    "PENTA", "PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS",
    "PNEUMO 10", "ROTAVIRUS", "T. VIRAL", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"
]

# Distritos mapeados
DISTRITOS_UBS = {
    "DISTRITO 1": ['ALTO', 'B NOVO I', 'B NOVO II', 'CORDEIRO', 'PRIMAVERA'],
    "DISTRITO 2": ['JUA', 'NACOES', 'NORDESTE I', 'NORDESTE II', 'NORDESTE III'],
    "DISTRITO 3": ['ASSIS', 'CLOVIS', 'ROSARIO', 'SÃO JOSE', 'STA TEREZINHA'],
    "DISTRITO 4": ['CACHOEIRA', 'CONTENDAS', 'MUTIRAO', 'PIRPIRI', 'TANANDUBA']
}

TURNOS = [
    "MANHÃ (Até 11h)", 
    "TARDE 1 (Das 11h às 15h)", 
    "TARDE 2 (Das 15h às 16h)"
]

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

tab1, tab2 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado"])

# --- ABA 1: LANÇAMENTO DE DADOS ---
with tab1:
    st.markdown("### 📌 Lançamento de Quantidades Aplicadas")
    
    col1, col2, col3 = st.columns(3)
    distrito_selecionado = col1.selectbox("Selecione o Distrito:", list(DISTRITOS_UBS.keys()))
    ubs_selecionada = col2.selectbox("Selecione o Posto de Saúde:", DISTRITOS_UBS[distrito_selecionado])
    turno_selecionado = col3.selectbox("Selecione o Turno:", TURNOS)
    
    st.markdown("---")
    st.write(f"Preencha as vacinas aplicadas em **{ubs_selecionada} ({distrito_selecionado})** no turno **{turno_selecionado}**:")
    
    df_entrada = pd.DataFrame({"VACINA": VACINAS, "QUANTIDADE": [0] * len(VACINAS)})
    
    df_editado = st.data_editor(
        df_entrada,
        hide_index=True,
        use_container_width=True,
        column_config={
            "VACINA": st.column_config.TextColumn("Imunobiológico", disabled=True),
            "QUANTIDADE": st.column_config.NumberColumn("Quantidade Aplicada", min_value=0, step=1)
        }
    )
    
    if st.button("💾 Salvar Lançamento no Servidor", type="primary"):
        df_salvar = df_editado[df_editado["QUANTIDADE"] > 0].copy()
        
        if not df_salvar.empty:
            try:
                # Transação no banco de dados para segurança
                with conn.session as s:
                    for _, row in df_salvar.iterrows():
                        sql = text("""
                            INSERT INTO registros_vacinacao (distrito, unidade_saude, turno, vacina, quantidade) 
                            VALUES (:distrito, :ubs, :turno, :vacina, :quantidade)
                        """)
                        s.execute(sql, {
                            "distrito": distrito_selecionado,
                            "ubs": ubs_selecionada,
                            "turno": turno_selecionado,
                            "vacina": row["VACINA"],
                            "quantidade": row["QUANTIDADE"]
                        })
                    s.commit()
                st.success(f"✅ Dados gravados no banco de dados central com sucesso para {ubs_selecionada}!")
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")
        else:
            st.warning("Nenhuma vacina informada. Digite valores maiores que 0.")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.markdown("### 📈 Painel Geral e Download")
    
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
