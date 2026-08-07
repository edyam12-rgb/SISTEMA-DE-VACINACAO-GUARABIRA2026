import streamlit as st
import pandas as pd
from sqlalchemy import text
import io
import hashlib

# Configuração da página
st.set_page_config(page_title="Sistema de Lançamento de Vacinas - Dia D", layout="wide")

# Conexão com o banco de dados
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Erro ao configurar a conexão com o banco de dados.")

# --- FUNÇÃO PARA CRIAR A TABELA DE USUÁRIOS SE NÃO EXISTIR ---
def inicializar_tabela_usuarios():
    try:
        with conn.session as s:
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    senha VARCHAR(255) NOT NULL,
                    perfil VARCHAR(20) NOT NULL
                )
            """))
            # Cria um usuário Administrador padrão (admin / admin123) se a tabela estiver vazia
            res = s.execute(text("SELECT COUNT(*) FROM usuarios")).fetchone()
            if res[0] == 0:
                senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
                s.execute(
                    text("INSERT INTO usuarios (username, senha, perfil) VALUES (:u, :p, :pf)"),
                    {"u": "admin", "p": senha_hash, "pf": "Administrador"}
                )
            s.commit()
    except Exception as e:
        pass

inicializar_tabela_usuarios()

# --- CONTROLE DE SESSÃO E LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.username = ""
    st.session_state.perfil = ""

st.sidebar.title("🔐 Acesso ao Sistema")

if not st.session_state.logado:
    st.sidebar.subheader("Faça seu Login")
    login_user = st.sidebar.text_input("Usuário", key="login_user")
    login_senha = st.sidebar.text_input("Senha", type="password", key="login_senha")
    
    if st.sidebar.button("Entrar", type="primary"):
        if login_user and login_senha:
            senha_hash = hashlib.sha256(login_senha.encode()).hexdigest()
            try:
                df_user = conn.query(
                    "SELECT * FROM usuarios WHERE username = :u AND senha = :s",
                    params={"u": login_user, "s": senha_hash},
                    ttl=0
                )
                if not df_user.empty:
                    st.session_state.logado = True
                    st.session_state.username = login_user
                    st.session_state.perfil = df_user.iloc[0]["perfil"]
                    st.rerun()
                else:
                    st.sidebar.error("Usuário ou senha incorretos!")
            except Exception as e:
                st.sidebar.error(f"Erro ao autenticar: {e}")
        else:
            st.sidebar.warning("Preencha todos os campos.")
    st.stop()

# Se já estiver logado, exibe informações na barra lateral e opção de sair
st.sidebar.success(f"Logado como: **{st.session_state.username}**\n\nPerfil: **{st.session_state.perfil}**")
if st.sidebar.button("🚪 Sair / Desconectar"):
    st.session_state.logado = False
    st.session_state.username = ""
    st.session_state.perfil = ""
    st.rerun()

is_admin = (st.session_state.perfil == "Administrador")

# --- PAINEL DE CADASTRO DE PERFIS (EXCLUSIVO PARA ADMINS) ---
if is_admin:
    with st.sidebar.expander("👤 Gerenciar / Cadastrar Usuários"):
        st.write("Cadastrar novo usuário ou técnico:")
        novo_user = st.text_input("Novo Usuário", key="cad_user")
        nova_senha = st.text_input("Senha", type="password", key="cad_senha")
        novo_perfil = st.selectbox("Indicar Perfil", ["Técnico", "Administrador"], key="cad_perfil")
        
        if st.button("💾 Cadastrar Usuário"):
            if novo_user and nova_senha:
                try:
                    senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
                    with conn.session as s:
                        s.execute(
                            text("INSERT INTO usuarios (username, senha, perfil) VALUES (:u, :p, :pf)"),
                            {"u": novo_user, "p": senha_hash, "pf": novo_perfil}
                        )
                        s.commit()
                    st.sidebar.success(f"Usuário '{novo_user}' cadastrado com sucesso!")
                except Exception as e:
                    st.sidebar.error(f"Erro (usuário já existe?): {e}")
            else:
                st.sidebar.warning("Preencha usuário e senha.")

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

# Listas oficiais
lista_rotina = [
    "ACWY", "ANTIR. HUMANA", "DENGUE", "DTP", "DTPa adulto", "Dt", 
    "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", 
    "MENIN. C", "PENTA", "PNEUMO 10", "PNEUMO 20", "ROTAVIRUS", 
    "T. VIRAL", "T. VIRAL 2ª DOSE", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"
]
lista_covid = ["PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS"]
lista_descontos = ['INFLUENZA', 'T. VIRAL', 'T. VIRAL 2ª DOSE', 'F. AMARELA', 'PNEUMO 20', 'DENGUE']

ubs_por_distrito = {
    "Distrito 1": ["Alto", "Bairro Novo I", "Bairro Novo II", "Cordeiro", "Primavera"],
    "Distrito 2": ["Juá", "Nações", "Nordeste I", "Nordeste II", "Nordeste III"],
    "Distrito 3": ["Assis", "Clóvis Bezerra", "Rosário", "São José", "Santa Terezinha"],
    "Distrito 4": ["Cachoeira", "Contendas", "Mutirão", "Pirpiri (São Francisco de Assis)", "Tananduba"]
}

# Controle de abas por perfil
if is_admin:
    tab1, tab2 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado"])
else:
    tab1, tab2 = st.tabs(["📝 Lançamento (Por Posto)", "🔒 Relatório Consolidado (Bloqueado)"])
    st.sidebar.info("👤 Perfil Técnico: Acesso restrito apenas à tela de lançamento.")

# --- ABA 1: LANÇAMENTO ---
with tab1:
    st.subheader("Painel de Lançamento por Posto de Saúde")
    distrito_selecionado = st.selectbox("Selecione o Distrito:", list(ubs_por_distrito.keys()), key="sel_distrito")
    ubs_selecionada = st.selectbox("Selecione a Unidade de Saúde (UBS):", ubs_por_distrito.get(distrito_selecionado, []), key="sel_ubs")
    turno_selecionado = st.selectbox("Selecione o Turno:", ["Manhã (até as 11h)", "Tarde (das 11h às 15h)", "Tarde (das 15h às 16h)"], key="sel_turno")
    
    st.markdown("---")
    categoria_vacina = st.radio("Selecione o grupo:", ["💉 Vacinas de Rotina", "🦠 Vacinas COVID-19"], horizontal=True, key="sel_cat")
    
    try:
        df_existente = conn.query(
            "SELECT vacina, quantidade FROM registros_vacinacao WHERE distrito = :d AND unidade_saude = :u AND turno = :t", 
            params={"d": distrito_selecionado, "u": ubs_selecionada, "t": turno_selecionado}, 
            ttl=0
        )
    except: 
        df_existente = pd.DataFrame()

    if categoria_vacina == "💉 Vacinas de Rotina":
        dic = {v: 0 for v in lista_rotina}
        if not df_existente.empty: 
            for _, r in df_existente.iterrows(): 
                if r["vacina"] in dic: dic[r["vacina"]] = r["quantidade"]
        df_tela = pd.DataFrame({"VACINA": lista_rotina, "QUANTIDADE": [dic[v] for v in lista_rotina]})
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

# --- ABA 2: RELATÓRIO CONSOLIDADO (APENAS PARA ADMINISTRADORES) ---
with tab2:
    if is_admin:
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
            
            st.markdown("---")
            modo_visualizacao = st.radio(
                "🔍 Visualizar consolidado por:", 
                ["Distrito", "Estabelecimento (UBS)"], 
                horizontal=True,
                key="radio_modo_vis"
            )
            
            nivel_agrupamento = 'distrito' if modo_visualizacao == "Distrito" else ['distrito', 'unidade_saude']

            # 1. Painel Consolidado por Turno Separado
            st.markdown("---")
            st.markdown("### 🕒 Consolidado Separado por Turno")
            
            turnos_disponiveis = ["Manhã (até as 11h)", "Tarde (das 11h às 15h)", "Tarde (das 15h às 16h)"]
            for t in turnos_disponiveis:
                df_turno = df_banco[df_banco['turno'] == t]
                st.markdown(f"#### ⏰ Turno: {t}")
                if not df_turno.empty:
                    if modo_visualizacao == "Distrito":
                        cons_t = df_turno.groupby(['distrito', 'GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
                    else:
                        cons_t = df_turno.groupby(['distrito', 'unidade_saude', 'GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
                    
                    for col in ['ROTINA', 'COVID']:
                        if col not in cons_t.columns: cons_t[col] = 0
                    cons_t['TOTAL'] = cons_t.sum(axis=1)
                    st.dataframe(cons_t, use_container_width=True)
                else:
                    st.info(f"Nenhum lançamento registrado para o turno: {t}")

            # 1.1 Total Geral para os Três Turnos (Somados)
            st.markdown("#### 🏁 Total Geral Acumulado (Três Turnos Somados)")
            if modo_visualizacao == "Distrito":
                cons_geral_turnos = df_banco.groupby(['distrito', 'GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
            else:
                cons_geral_turnos = df_banco.groupby(['distrito', 'unidade_saude', 'GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
            
            for col in ['ROTINA', 'COVID']:
                if col not in cons_geral_turnos.columns: cons_geral_turnos[col] = 0
            cons_geral_turnos['TOTAL'] = cons_geral_turnos.sum(axis=1)
            
            linha_total_turnos = cons_geral_turnos.sum(numeric_only=True)
            linha_total_turnos.name = 'TOTAL FINAL'
            cons_geral_turnos_com_soma = pd.concat([cons_geral_turnos, linha_total_turnos.to_frame().T])
            st.dataframe(cons_geral_turnos_com_soma, use_container_width=True)

            # 2. Total Geral Acumulado com Descontos e Soma por Coluna
            st.markdown("---")
            st.markdown(f"### 📋 Detalhamento Oficial com Descontos (Por {modo_visualizacao})")
            
            df_banco['VAC_UPPER'] = df_banco['vacina'].str.upper()
            tabela = df_banco.pivot_table(index=nivel_agrupamento, columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0)
            
            for v in lista_descontos:
                if v not in tabela.columns: tabela[v] = 0
                
            rotina_total = df_banco[~df_banco['vacina'].isin(lista_covid)].groupby(nivel_agrupamento)['quantidade'].sum()
            soma_descontos = tabela[lista_descontos].sum(axis=1)
            
            df_geral = pd.DataFrame(index=tabela.index)
            df_geral['ROTINA (OUTRAS)'] = (rotina_total - soma_descontos).reindex(df_geral.index).fillna(0)
            
            for v in lista_descontos: 
                df_geral[v] = tabela[v]
                
            df_geral['COVID'] = df_banco[df_banco['vacina'].isin(lista_covid)].groupby(nivel_agrupamento)['quantidade'].sum().reindex(df_geral.index).fillna(0)
            
            df_geral['TOTAL GERAL'] = df_geral['ROTINA (OUTRAS)'] + soma_descontos + df_geral['COVID']
            
            linha_total = df_geral.sum(numeric_only=True)
            linha_total.name = 'TOTAL FINAL'
            df_geral_com_soma = pd.concat([df_geral, linha_total.to_frame().T])
            
            st.dataframe(df_geral_com_soma, use_container_width=True)

            st.markdown("---")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_geral_com_soma.to_excel(writer, sheet_name='TOTAL_GERAL')
                df_banco.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
            
            st.download_button(
                label="📥 Baixar Planilha Consolidada (.xlsx)",
                data=buffer.getvalue(),
                file_name="Relatorio_Final_Dia_D.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("👈 Nenhum dado recebido do banco ainda.")
    else:
        st.warning("🔒 Acesso restrito. Esta aba está disponível apenas para administradores.")
