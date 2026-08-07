import streamlit as st
import pandas as pd
from sqlalchemy import text
import io

# Configuração da página
st.set_page_config(page_title="Sistema de Lançamento de Vacinas - Dia D", layout="wide")

# Conexão com o banco de dados
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Erro ao configurar a conexão com o banco de dados.")

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

tab1, tab2 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado"])

# Listas oficiais
lista_rotina = [
    "ACWY", "ANTIR. HUMANA", "DENGUE", "DTP", "DTPa adulto", "Dt", 
    "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", 
    "MENIN. C", "PENTA", "PNEUMO 10", "PNEUMO 20", "ROTAVIRUS", 
    "T. VIRAL", "T. VIRAL 2ª DOSE", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"
]
lista_covid = ["PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS"]
lista_descontos = ['INFLUENZA', 'T. VIRAL', 'T. VIRAL 2ª DOSE', 'F. AMARELA', 'PNEUMO 20', 'DENGUE']

# --- ABA 1: LANÇAMENTO ---
with tab1:
    st.subheader("Painel de Lançamento por Posto de Saúde")
    distrito_selecionado = st.selectbox("Selecione o Distrito:", ["Distrito 1", "Distrito 2", "Distrito 3", "Distrito 4"])
    
    ubs_por_distrito = {
        "Distrito 1": ["Alto", "Bairro Novo I", "Bairro Novo II", "Cordeiro", "Primavera"],
        "Distrito 2": ["Juá", "Nações", "Nordeste I", "Nordeste II", "Nordeste III"],
        "Distrito 3": ["Assis", "Clóvis Bezerra", "Rosário", "São José", "Santa Terezinha"],
        "Distrito 4": ["Cachoeira", "Contendas", "Mutirão", "Pirpiri (São Francisco de Assis)", "Tananduba"]
    }
    
    ubs_selecionada = st.selectbox("Selecione a Unidade de Saúde (UBS):", ubs_por_distrito.get(distrito_selecionado, []))
    turno_selecionado = st.selectbox("Selecione o Turno:", ["Manhã (até as 11h)", "Tarde (das 11h às 15h)", "Tarde (das 15h às 16h)"])
    
    st.markdown("---")
    categoria_vacina = st.radio("Selecione o grupo:", ["💉 Vacinas de Rotina", "🦠 Vacinas COVID-19"], horizontal=True)
    
    # Busca valores salvos no banco para esta UBS e Turno específicos
    try:
        df_existente = conn.query(
            "SELECT vacina, quantidade FROM registros_vacinacao WHERE distrito = :d AND unidade_saude = :u AND turno = :t", 
            params={"d": distrito_selecionado, "u": ubs_selecionada, "t": turno_selecionado}, 
            ttl=0
        )
    except: 
        df_existente = pd.DataFrame()

    # Criação do dicionário de quantidades com base no banco (ou zero se não houver registros)
    if categoria_vacina == "💉 Vacinas de Rotina":
        dic = {v: 0 for v in lista_rotina}
        if not df_existente.empty: 
            for _, r in df_existente.iterrows(): 
                if r["vacina"] in dic: dic[r["vacina"]] = r["quantidade"]
        df_tela = pd.DataFrame({"VACINA": lista_rotina, "QUANTIDADE": [dic[v] for v in lista_rotina]})
        # Chave dinâmica garante que o editor zere ou recarregue ao trocar de posto/turno
        editor_key = f"rotina_{distrito_selecionado}_{ubs_selecionada}_{turno_selecionado}"
    else:
        dic = {v: 0 for v in lista_covid}
        if not df_existente.empty: 
            for _, r in df_existente.iterrows(): 
                if r["vacina"] in dic: dic[r["vacina"]] = r["quantidade"]
        df_tela = pd.DataFrame({"VACINA": lista_covid, "QUANTIDADE": [dic[v] for v in lista_covid]})
        editor_key = f"covid_{distrito_selecionado}_{ubs_selecionada}_{turno_selecionado}"
        
    df_editado = st.data_editor(df_tela, hide_index=True, use_container_width=True, key=editor_key)
    
    if st.button("💾 Salvar Lançamento no Servidor", type="primary"):
        try:
            with conn.session as s:
                s.execute(
                    text("DELETE FROM registros_vacinacao WHERE distrito = :distrito AND unidade_saude = :ubs AND turno = :turno"), 
                    {"distrito": distrito_selecionado, "ubs": ubs_selecionada, "turno": turno_selecionado}
                )
                for _, row in df_editado[df_editado["QUANTIDADE"] > 0].iterrows():
                    s.execute(
                        text("INSERT INTO registros_vacinacao (distrito, unidade_saude, turno, vacina, quantidade) VALUES (:distrito, :ubs, :turno, :vacina, :quantidade)"), 
                        {"distrito": distrito_selecionado, "ubs": ubs_selecionada, "turno": turno_selecionado, "vacina": row["VACINA"], "quantidade": row["QUANTIDADE"]}
                    )
                s.commit()
                st.success(f"✅ Lançamento salvo para {ubs_selecionada} ({turno_selecionado})!")
        except Exception as e: 
            st.error(f"Erro ao salvar: {e}")

# --- ABA 2: RELATÓRIO CONSOLIDADO ---
with tab2:
    st.markdown("### 📊 Painel Geral de Relatórios")
    if st.button("🔄 Atualizar Relatório"): st.rerun()

    try: df_banco = conn.query("SELECT * FROM registros_vacinacao", ttl=0)
    except: df_banco = pd.DataFrame()

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

        df_banco['GRUPO_TURNO'] = df_banco['vacina'].apply(lambda x: 'COVID' if ("COVID" in x.upper() or "PFIZER" in x.upper()) else 'ROTINA')
        
        # 1. Painel Consolidado por Turno
        st.markdown("---")
        st.markdown("### 🕒 Consolidado por Turno")
        consolidado_turno = df_banco.groupby(['turno', 'distrito', 'GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
        for col in ['ROTINA', 'COVID']:
            if col not in consolidado_turno.columns: consolidado_turno[col] = 0
        consolidado_turno['TOTAL'] = consolidado_turno.sum(axis=1)

        for t in df_banco['turno'].unique():
            st.markdown(f"#### Turno: {t}")
            st.dataframe(consolidado_turno.loc[t], use_container_width=True)

        # 2. Total Geral Acumulado com Descontos e Soma por Coluna
        st.markdown("---")
        st.markdown("### 🏁 Total Geral Acumulado (Com Descontos Oficiais)")
        
        df_banco['VAC_UPPER'] = df_banco['vacina'].str.upper()
        tabela = df_banco.pivot_table(index='distrito', columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0)
        
        for v in lista_descontos:
            if v not in tabela.columns: tabela[v] = 0
            
        rotina_total = df_banco[~df_banco['vacina'].isin(lista_covid)].groupby('distrito')['quantidade'].sum()
        soma_descontos = tabela[lista_descontos].sum(axis=1)
        
        df_geral = pd.DataFrame(index=tabela.index)
        df_geral['ROTINA (OUTRAS)'] = (rotina_total - soma_descontos).reindex(df_geral.index).fillna(0)
        
        for v in lista_descontos: 
            df_geral[v] = tabela[v]
            
        df_geral['COVID'] = df_banco[df_banco['vacina'].isin(lista_covid)].groupby('distrito')['quantidade'].sum().reindex(df_geral.index).fillna(0)
        
        df_geral['TOTAL GERAL'] = df_geral['ROTINA (OUTRAS)'] + soma_descontos + df_geral['COVID']
        
        linha_total = df_geral.sum(numeric_only=True)
        linha_total.name = 'TOTAL FINAL'
        df_geral_com_soma = pd.concat([df_geral, linha_total.to_frame().T])
        
        st.dataframe(df_geral_com_soma, use_container_width=True)

        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            consolidado_turno.to_excel(writer, sheet_name='CONSOLIDADO_TURNO')
            df_geral_com_soma.to_excel(writer, sheet_name='TOTAL_GENERAL')
            df_banco.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada (.xlsx)",
            data=buffer.getvalue(),
            file_name="Relatorio_Final_Dia_D.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("👈 Nenhum dado recebido do banco ainda.")
