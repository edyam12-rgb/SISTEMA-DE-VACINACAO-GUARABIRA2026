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

ubs_por_distrito = {
    "Distrito 1": ["Alto", "Bairro Novo I", "Bairro Novo II", "Cordeiro", "Primavera"],
    "Distrito 2": ["Juá", "Nações", "Nordeste I", "Nordeste II", "Nordeste III"],
    "Distrito 3": ["Assis", "Clóvis Bezerra", "Rosário", "São José", "Santa Terezinha"],
    "Distrito 4": ["Cachoeira", "Contendas", "Mutirão", "Pirpiri (São Francisco de Assis)", "Tananduba"]
}

# --- FUNÇÃO PARA CRIAR OU ATUALIZAR A TABELA DE USUÁRIOS NO BANCO ---
def inicializar_tabela_usuarios():
    try:
        with conn.session as s:
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    senha VARCHAR(255) NOT NULL,
                    perfil VARCHAR(20) NOT NULL,
                    distrito VARCHAR(50),
                    ubs VARCHAR(100)
                )
            """))
            s.commit()
            
            try:
                s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS distrito VARCHAR(50)"))
                s.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ubs VARCHAR(100)"))
                s.commit()
            except:
                s.rollback()

            res = s.execute(text("SELECT COUNT(*) FROM usuarios")).fetchone()
            if res[0] == 0:
                senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
                s.execute(
                    text("INSERT INTO usuarios (username, senha, perfil, distrito, ubs) VALUES (:u, :p, :pf, :d, :ub)"),
                    {"u": "admin", "p": senha_hash, "pf": "Administrador", "d": "Geral", "ub": "Geral"}
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
    st.session_state.distrito_user = ""
    st.session_state.ubs_user = ""

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
                    st.session_state.distrito_user = df_user.iloc[0]["distrito"] or "Geral"
                    st.session_state.ubs_user = df_user.iloc[0]["ubs"] or "Geral"
                    st.rerun()
                else:
                    st.sidebar.error("Usuário ou senha incorretos!")
            except Exception as e:
                st.sidebar.error(f"Erro ao autenticar: {e}")
        else:
            st.sidebar.warning("Preencha todos os campos.")
    st.stop()

st.sidebar.success(f"Logado como: **{st.session_state.username}**\n\nPerfil: **{st.session_state.perfil}**")
if st.session_state.perfil == "Técnico":
    st.sidebar.info(f"📍 **UBS Vinculada:**\n{st.session_state.ubs_user} ({st.session_state.distrito_user})")

if st.sidebar.button("🚪 Sair / Desconectar"):
    st.session_state.logado = False
    st.session_state.username = ""
    st.session_state.perfil = ""
    st.session_state.distrito_user = ""
    st.session_state.ubs_user = ""
    st.rerun()

is_admin = (st.session_state.perfil == "Administrador")

# --- PAINEL DE CADASTRO DE PERFIS (ADMINS) ---
if is_admin:
    with st.sidebar.expander("👤 Cadastrar Novo Usuário"):
        novo_user = st.text_input("Novo Usuário", key="cad_user")
        nova_senha = st.text_input("Senha", type="password", key="cad_senha")
        novo_perfil = st.selectbox("Indicar Perfil", ["Técnico", "Administrador"], key="cad_perfil")
        
        cad_distrito = "Geral"
        cad_ubs = "Geral"
        if novo_perfil == "Técnico":
            cad_distrito = st.selectbox("Distrito do Técnico", list(ubs_por_distrito.keys()), key="cad_dist")
            cad_ubs = st.selectbox("UBS do Técnico", ubs_por_distrito.get(cad_distrito, []), key="cad_ubs_loc")

        if st.button("💾 Cadastrar Usuário"):
            if novo_user and nova_senha:
                try:
                    senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
                    with conn.session as s:
                        s.execute(
                            text("INSERT INTO usuarios (username, senha, perfil, distrito, ubs) VALUES (:u, :p, :pf, :d, :ub)"),
                            {"u": novo_user, "p": senha_hash, "pf": novo_perfil, "d": cad_distrito, "ub": cad_ubs}
                        )
                        s.commit()
                    st.sidebar.success(f"Usuário '{novo_user}' cadastrado com sucesso!")
                    st.rerun()
                except Exception as e: st.sidebar.error("Erro ao cadastrar (usuário já existe?).")
            else: st.sidebar.warning("Preencha todos os campos.")

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

lista_rotina = ["ACWY", "ANTIR. HUMANA", "DENGUE", "DTP", "DTPa adulto", "Dt", "F. AMARELA", "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", "MENIN. C", "PENTA", "PNEUMO 10", "PNEUMO 20", "ROTAVIRUS", "T. VIRAL", "T. VIRAL 2ª DOSE", "TETRA", "VARICELA", "VIP", "VIT. A", "VSR GRAVIDA"]
lista_covid = ["PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS"]
lista_descontos = ['INFLUENZA', 'T. VIRAL', 'T. VIRAL 2ª DOSE', 'F. AMARELA', 'PNEUMO 20', 'DENGUE']

if is_admin: tab1, tab2, tab3 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado", "⚙️ Gerenciar Usuários"])
else: tab1, tab2, tab3 = st.tabs(["📝 Lançamento (Por Posto)", "🔒 Relatório Consolidado (Bloqueado)", "🔒 Gerenciar Usuários (Bloqueado)"])

with tab1:
    # Inicializa estados de controle de navegação e bloqueio
    if "w_distrito" not in st.session_state:
        st.session_state.w_distrito = list(ubs_por_distrito.keys())[0] if is_admin else st.session_state.distrito_user
    if "w_ubs" not in st.session_state:
        st.session_state.w_ubs = ubs_por_distrito.get(st.session_state.w_distrito, [""])[0] if is_admin else st.session_state.ubs_user
    if "w_turno" not in st.session_state:
        st.session_state.w_turno = "Manhã (até as 11h)"
    if "w_cat" not in st.session_state:
        st.session_state.w_cat = "💉 Vacinas de Rotina"

    # Renderiza os seletores usando o estado ativo atual
    col1, col2, col3 = st.columns(3)
    if is_admin:
        sel_distrito = col1.selectbox("Selecione o Distrito:", list(ubs_por_distrito.keys()), index=list(ubs_por_distrito.keys()).index(st.session_state.w_distrito) if st.session_state.w_distrito in ubs_por_distrito else 0)
        lista_ubs_disp = ubs_por_distrito.get(sel_distrito, [])
        idx_ubs = lista_ubs_disp.index(st.session_state.w_ubs) if st.session_state.w_ubs in lista_ubs_disp else 0
        sel_ubs = col2.selectbox("Selecione a UBS:", lista_ubs_disp, index=idx_ubs)
    else:
        sel_distrito = st.session_state.distrito_user
        sel_ubs = st.session_state.ubs_user
        col1.write(f"**Distrito:** {sel_distrito}")
        col2.write(f"**UBS:** {sel_ubs}")

    lista_turnos_opt = ["Manhã (até as 11h)", "Tarde (das 11h às 15h)", "Tarde (das 15h às 16h)"]
    sel_turno = col3.selectbox("Selecione o Turno:", lista_turnos_opt, index=lista_turnos_opt.index(st.session_state.w_turno))
    
    sel_cat = st.radio("Grupo:", ["💉 Vacinas de Rotina", "🦠 Vacinas COVID-19"], horizontal=True, index=0 if st.session_state.w_cat == "💉 Vacinas de Rotina" else 1)

    # Busca dados do banco para o contexto ATIVO real
    try:
        df_existente = conn.query("SELECT vacina, quantidade FROM registros_vacinacao WHERE distrito = :d AND unidade_saude = :u AND turno = :t", params={"d": st.session_state.w_distrito, "u": st.session_state.w_ubs, "t": st.session_state.w_turno}, ttl=0)
    except: df_existente = pd.DataFrame()

    if st.session_state.w_cat == "💉 Vacinas de Rotina":
        dic_val = {v: 0 for v in lista_rotina}
        if not df_existente.empty: 
            for _, r in df_existente.iterrows(): 
                if r["vacina"] in dic_val: dic_val[r["vacina"]] = r["quantidade"]
        df_tela = pd.DataFrame({"VACINA": lista_rotina, "QUANTIDADE": [dic_val[v] for v in lista_rotina]})
    else:
        dic_val = {v: 0 for v in lista_covid}
        if not df_existente.empty: 
            for _, r in df_existente.iterrows(): 
                if r["vacina"] in dic_val: dic_val[r["vacina"]] = r["quantidade"]
        df_tela = pd.DataFrame({"VACINA": lista_covid, "QUANTIDADE": [dic_val[v] for v in lista_covid]})

    editor_key = f"editor_{st.session_state.w_distrito}_{st.session_state.w_ubs}_{st.session_state.w_turno}_{st.session_state.w_cat}"
    df_editado = st.data_editor(df_tela, hide_index=True, use_container_width=True, key=editor_key)

    # Verifica se há alteração pendente na tabela editada
    dict_banco = dict(zip(df_existente['vacina'], df_existente['quantidade'])) if not df_existente.empty else {}
    dict_tela = dict(zip(df_editado['VACINA'], df_editado['QUANTIDADE']))
    tem_pendencia = (dict_tela != dict_banco)

    # Detecta tentativa de mudança nos seletores
    tentativa_troca = (sel_distrito != st.session_state.w_distrito) or (sel_ubs != st.session_state.w_ubs) or (sel_turno != st.session_state.w_turno) or (sel_cat != st.session_state.w_cat)

    if tem_pendencia:
        st.warning("⚠️ **ATENÇÃO:** Você possui alterações não salvas neste turno/unidade! Clique em **'💾 Salvar Lançamento'** antes de tentar mudar de turno, UBS ou grupo.")
        if tentativa_troca:
            st.error("🛑 **BLOQUEIO DE SEGURANÇA:** Não é permitido mudar de turno ou unidade com alterações pendentes! Salve os dados atuais primeiro para prosseguir.")
            st.stop()

    if tentativa_troca and not tem_pendencia:
        st.session_state.w_distrito = sel_distrito
        st.session_state.w_ubs = sel_ubs
        st.session_state.w_turno = sel_turno
        st.session_state.w_cat = sel_cat
        st.rerun()

    if st.button("💾 Salvar Lançamento", type="primary"):
        try:
            with conn.session as s:
                s.execute(text("DELETE FROM registros_vacinacao WHERE distrito = :distrito AND unidade_saude = :ubs AND turno = :turno"), {"distrito": st.session_state.w_distrito, "ubs": st.session_state.w_ubs, "turno": st.session_state.w_turno})
                for _, row in df_editado[df_editado["QUANTIDADE"] > 0].iterrows():
                    s.execute(text("INSERT INTO registros_vacinacao (distrito, unidade_saude, turno, vacina, quantidade) VALUES (:distrito, :ubs, :turno, :vacina, :quantidade)"), {"distrito": st.session_state.w_distrito, "ubs": st.session_state.w_ubs, "turno": st.session_state.w_turno, "vacina": row["VACINA"], "quantidade": row["QUANTIDADE"]})
                s.commit()
                st.success("✅ Salvo com sucesso!")
                st.rerun()
        except Exception as e: st.error(f"Erro ao salvar: {e}")

with tab2:
    if is_admin:
        with st.expander("⚠️ Área Administrativa: Limpar Banco de Dados"):
            st.warning("Atenção: Esta ação irá apagar **todos** os lançamentos salvos no servidor permanentemente.")
            confirmacao = st.checkbox("Sim, tenho certeza que desejo apagar todo o histórico de lançamentos.")
            if st.button("🗑️ Apagar Todos os Dados do Servidor"):
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
        
        try: df_banco = conn.query("SELECT * FROM registros_vacinacao", ttl=0)
        except: df_banco = pd.DataFrame()
        if not df_banco.empty:
            df_banco['GRUPO_TURNO'] = df_banco['vacina'].apply(lambda x: 'COVID' if ("COVID" in x.upper() or "PFIZER" in x.upper()) else 'ROTINA')
            modo = st.radio("🔍 Visualizar por:", ["Distrito", "Estabelecimento (UBS)"], horizontal=True)
            nivel = 'distrito' if modo == "Distrito" else ['distrito', 'unidade_saude']
            lista_nivel = [nivel] if isinstance(nivel, str) else nivel
            
            for t in ["Manhã (até as 11h)", "Tarde (das 11h às 15h)", "Tarde (das 15h às 16h)"]:
                df_t = df_banco[df_banco['turno'] == t]
                if not df_t.empty:
                    cons = df_t.groupby(lista_nivel + ['GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
                    cons['TOTAL'] = cons.sum(axis=1)
                    st.markdown(f"#### ⏰ {t}"); st.dataframe(cons, use_container_width=True)
            
            df_banco['VAC_UPPER'] = df_banco['vacina'].str.upper()
            tabela = df_banco.pivot_table(index=nivel, columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0)
            for v in lista_descontos:
                if v not in tabela.columns: tabela[v] = 0
            rotina_total = df_banco[~df_banco['vacina'].isin(lista_covid)].groupby(nivel)['quantidade'].sum()
            soma_descontos = tabela[lista_descontos].sum(axis=1)
            df_geral = pd.DataFrame(index=tabela.index)
            df_geral['ROTINA (OUTRAS)'] = (rotina_total - soma_descontos).reindex(df_geral.index).fillna(0)
            for v in lista_descontos: df_geral[v] = tabela[v]
            df_geral['COVID'] = df_banco[df_banco['vacina'].isin(lista_covid)].groupby(nivel)['quantidade'].sum().reindex(df_geral.index).fillna(0)
            df_geral['TOTAL GERAL'] = df_geral['ROTINA (OUTRAS)'] + soma_descontos + df_geral['COVID']
            st.markdown("### 🏁 Total Geral")
            st.dataframe(pd.concat([df_geral, df_geral.sum(numeric_only=True).to_frame().T.rename(index={0: 'TOTAL FINAL'})]), use_container_width=True)
            
            st.markdown("---")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_geral.to_excel(writer, sheet_name='TOTAL_GERAL')
                df_banco.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
            st.download_button("📥 Baixar Planilha Consolidada", data=buffer.getvalue(), file_name="Relatorio_Final.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else: st.warning("🔒 Acesso restrito apenas para administradores.")

with tab3:
    if is_admin:
        st.markdown("### 👥 Gerenciamento de Usuários Cadastrados")
        try:
            df_usuarios = conn.query("SELECT id, username, perfil, distrito, ubs FROM usuarios ORDER BY id", ttl=0)
        except:
            df_usuarios = pd.DataFrame()
            
        if not df_usuarios.empty:
            st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("#### ⚙️ Alterar Perfil ou Excluir Usuário")
            
            usuario_selecionado = st.selectbox("Selecione o Usuário:", df_usuarios["username"].tolist())
            user_info = df_usuarios[df_usuarios["username"] == usuario_selecionado].iloc[0]
            
            with st.form("form_edicao_usuario"):
                novo_perfil_edit = st.selectbox("Alterar Perfil", ["Técnico", "Administrador"], index=0 if user_info["perfil"] == "Técnico" else 1)
                
                edit_distrito = user_info["distrito"] if user_info["distrito"] else "Geral"
                edit_ubs = user_info["ubs"] if user_info["ubs"] else "Geral"
                
                if novo_perfil_edit == "Técnico":
                    edit_distrito = st.selectbox("Distrito", list(ubs_por_distrito.keys()), index=list(ubs_por_distrito.keys()).index(edit_distrito) if edit_distrito in ubs_por_distrito else 0)
                    edit_ubs = st.selectbox("UBS", ubs_por_distrito.get(edit_distrito, []), index=0)
                else:
                    edit_distrito = "Geral"
                    edit_ubs = "Geral"
                
                col1, col2 = st.columns(2)
                atualizar = col1.form_submit_button("🔄 Atualizar Dados")
                excluir = col2.form_submit_button("🗑️ Excluir Usuário", type="primary")
                
                if atualizar:
                    try:
                        with conn.session as s:
                            s.execute(
                                text("UPDATE usuarios SET perfil = :pf, distrito = :d, ubs = :ub WHERE username = :u"),
                                {"pf": novo_perfil_edit, "d": edit_distrito, "ub": edit_ubs, "u": usuario_selecionado}
                            )
                            s.commit()
                        st.success(f"✅ Usuário '{usuario_selecionado}' atualizado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {e}")
                        
                if excluir:
                    if usuario_selecionado == "admin":
                        st.error("⚠️ O usuário principal 'admin' não pode ser excluído!")
                    else:
                        try:
                            with conn.session as s:
                                s.execute(text("DELETE FROM usuarios WHERE username = :u"), {"u": usuario_selecionado})
                                s.commit()
                            st.success(f"🗑️ Usuário '{usuario_selecionado}' excluído com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
        else:
            st.info("Nenhum usuário cadastrado.")
    else:
        st.warning("🔒 Acesso restrito apenas para administradores.")
