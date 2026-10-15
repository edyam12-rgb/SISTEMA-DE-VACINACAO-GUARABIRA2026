import streamlit as st
import pandas as pd
from sqlalchemy import text
import io
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuração da página
st.set_page_config(page_title="Sistema de Lançamento de Vacinas - Dia D", layout="wide")

# Conexão com o banco de dados
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Erro ao configurar a conexão com o banco de dados: {e}")
    conn = None

ubs_por_distrito = {
    "Distrito 1": ["Alto", "Bairro Novo I", "Bairro Novo II", "Cordeiro", "Primavera"],
    "Distrito 2": ["Juá", "Nações", "Nordeste I", "Nordeste II", "Nordeste III"],
    "Distrito 3": ["Assis", "Clóvis Bezerra", "Rosário", "São José", "Santa Terezinha"],
    "Distrito 4": ["Cachoeira", "Contendas", "Mutirão", "Pirpiri", "Tananduba"]
}

# --- FUNÇÃO PARA CRIAR OU ATUALIZAR A TABELA DE USUÁRIOS NO BANCO ---
def inicializar_tabela_usuarios():
    if conn is None:
        return
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

            s.execute(text("UPDATE usuarios SET distrito = 'Geral' WHERE distrito IS NULL OR distrito = ''"))
            s.execute(text("UPDATE usuarios SET ubs = 'Geral' WHERE ubs IS NULL OR ubs = ''"))
            s.commit()

            senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
            res = s.execute(text("SELECT COUNT(*) FROM usuarios WHERE username = 'admin'")).fetchone()
            if res[0] == 0:
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
    modo_acesso = st.sidebar.radio("Selecione:", ["Fazer Login", "Redefinir Senha"], horizontal=True)
    
    if modo_acesso == "Fazer Login":
        st.sidebar.subheader("Faça seu Login")
        login_user = st.sidebar.text_input("Usuário", key="login_user")
        login_senha = st.sidebar.text_input("Senha", type="password", key="login_senha")
        
        if st.sidebar.button("Entrar", type="primary"):
            if login_user and login_senha:
                senha_hash = hashlib.sha256(login_senha.encode()).hexdigest()
                try:
                    df_user = conn.query(
                        "SELECT * FROM usuarios WHERE LOWER(TRIM(username)) = LOWER(TRIM(:u)) AND senha = :s",
                        params={"u": login_user, "s": senha_hash},
                        ttl=0
                    )
                    if not df_user.empty:
                        st.session_state.logado = True
                        st.session_state.username = df_user.iloc[0]["username"]
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
    
    else:
        st.sidebar.subheader("🔑 Redefinir Senha")
        st.sidebar.info("Digite o seu nome de utilizador e a nova senha desejada.")
        
        rec_user = st.sidebar.text_input("Nome de Usuário", key="rec_user")
        rec_nova_1 = st.sidebar.text_input("Nova Senha", type="password", key="rec_nova_1")
        rec_nova_2 = st.sidebar.text_input("Confirmar Nova Senha", type="password", key="rec_nova_2")
        
        if st.sidebar.button("Atualizar Minha Senha"):
            if rec_user and rec_nova_1 and rec_nova_2:
                if rec_nova_1 != rec_nova_2:
                    st.sidebar.error("As senhas não coincidem!")
                else:
                    try:
                        df_u = conn.query(
                            "SELECT * FROM usuarios WHERE LOWER(TRIM(username)) = LOWER(TRIM(:u))", 
                            params={"u": rec_user}, 
                            ttl=0
                        )
                        if df_u.empty:
                            st.sidebar.error("Usuário não encontrado! Verifique se digitou o nome corretamente.")
                        else:
                            nome_real = df_u.iloc[0]["username"]
                            novo_hash = hashlib.sha256(rec_nova_1.encode()).hexdigest()
                            with conn.session as s:
                                s.execute(
                                    text("UPDATE usuarios SET senha = :p WHERE username = :u"),
                                    {"p": novo_hash, "u": nome_real}
                                )
                                s.commit()
                            st.sidebar.success("✅ Senha redefinida com sucesso! Volte à aba 'Fazer Login'.")
                    except Exception as e:
                        st.sidebar.error(f"Erro ao redefinir: {e}")
            else:
                st.sidebar.warning("Preencha todos os campos.")

    st.stop()

st.sidebar.success(f"Logado como: **{st.session_state.username}**\n\nPerfil: **{st.session_state.perfil}**")
if st.session_state.perfil == "Técnico":
    st.sidebar.info(f"📍 **UBS Vinculada:**\n{st.session_state.ubs_user} ({st.session_state.distrito_user})")

# --- ALTERAR SENHA DO PRÓPRIO UTILIZADOR NA BARRA LATERAL (SE JÁ ESTIVER LOGADO) ---
with st.sidebar.expander("🔑 Alterar Minha Senha"):
    senha_atual = st.text_input("Senha Atual", type="password", key="sidebar_senha_atual")
    nova_senha_1 = st.text_input("Nova Senha", type="password", key="sidebar_nova_senha1")
    nova_senha_2 = st.text_input("Confirmar Nova Senha", type="password", key="sidebar_nova_senha2")
    
    if st.button("🔄 Salvar Nova Senha"):
        if senha_atual and nova_senha_1 and nova_senha_2:
            if nova_senha_1 != nova_senha_2:
                st.sidebar.error("As novas senhas não coincidem!")
            else:
                atual_hash = hashlib.sha256(senha_atual.encode()).hexdigest()
                try:
                    df_check = conn.query(
                        "SELECT * FROM usuarios WHERE username = :u AND senha = :s",
                        params={"u": st.session_state.username, "s": atual_hash},
                        ttl=0
                    )
                    if df_check.empty:
                        st.sidebar.error("A senha atual está incorreta!")
                    else:
                        nova_hash = hashlib.sha256(nova_senha_1.encode()).hexdigest()
                        with conn.session as s:
                            s.execute(
                                text("UPDATE usuarios SET senha = :p WHERE username = :u"),
                                {"p": nova_hash, "u": st.session_state.username}
                            )
                            s.commit()
                        st.sidebar.success("✅ Senha alterada com sucesso!")
                except Exception as e:
                    st.sidebar.error(f"Erro ao alterar senha: {e}")
        else:
            st.sidebar.warning("Preencha todos os campos de senha.")

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
            ubs_disponiveis = ubs_por_distrito.get(cad_distrito, [])
            cad_ubs = st.selectbox("UBS do Técnico", ubs_disponiveis, key="cad_ubs_loc")

        if st.button("💾 Cadastrar Usuário"):
            if novo_user and nova_senha:
                try:
                    senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
                    with conn.session as s:
                        s.execute(
                            text("INSERT INTO usuarios (username, senha, perfil, distrito, ubs) VALUES (:u, :p, :pf, :d, :ub)"),
                            {"u": novo_user.strip(), "p": senha_hash, "pf": novo_perfil, "d": cad_distrito, "ub": cad_ubs}
                        )
                        s.commit()
                    st.sidebar.success(f"Usuário '{novo_user}' cadastrado com sucesso!")
                    st.rerun()
                except Exception as e: 
                    st.sidebar.error("Erro ao cadastrar (usuário já existe?).")
            else: 
                st.sidebar.warning("Preencha todos os campos.")

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

lista_bruta = [
    "ACWY", "ANTIR. HUMANA", "DENGUE", "DTP", "DTPa adulto", "Dt", "F. AMARELA", 
    "HEPAT. A", "HEPAT. B", "HPV", "INFLUENZA", "MENIN. C", "PENTA", "PNEUMO 10", 
    "PNEUMO 20", "ROTAVIRUS", "T. VIRAL", "T. VIRAL 2ª DOSE", "TETRA", "VARICELA", 
    "VIP", "VIT. A", "VSR GRAVIDA", 
    "PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS"
]
lista_todas_vacinas = sorted(lista_bruta)

lista_descontos = ['INFLUENZA', 'T. VIRAL', 'T. VIRAL 2ª DOSE', 'F. AMARELA', 'PNEUMO 20', 'DENGUE']
lista_covid = ["PFIZER ADULTO", "PFIZER PED 06 A 4 ANOS", "PFIZER PED. 05 A 11 ANOS"]

if is_admin: 
    tab1, tab2, tab3 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado", "⚙️ Gerenciar Usuários"])
else: 
    tab1, tab2, tab3 = st.tabs(["📝 Lançamento (Por Posto)", "🔒 Relatório Consolidado (Bloqueado)", "🔒 Gerenciar Usuários (Bloqueado)"])

with tab1:
    def obter_turno_automatico():
        try:
            hora_local = datetime.now(ZoneInfo("America/Fortaleza")).hour
        except Exception:
            hora_local = datetime.now().hour
        return "Manhã (até as 11h)" if hora_local < 11 else "Tarde (das 11h às 16h)"

    if not is_admin:
        st.session_state.sel_turno_ativo = obter_turno_automatico()
    else:
        if "sel_turno_ativo" not in st.session_state:
            st.session_state.sel_turno_ativo = obter_turno_automatico()

    if "sel_distrito_ativo" not in st.session_state:
        st.session_state.sel_distrito_ativo = list(ubs_por_distrito.keys())[0] if is_admin else st.session_state.distrito_user
    if "sel_ubs_ativo" not in st.session_state:
        st.session_state.sel_ubs_ativo = ubs_por_distrito.get(st.session_state.sel_distrito_ativo, [""])[0] if is_admin else st.session_state.ubs_user

    unidade_atual_txt = f"**UBS:** {st.session_state.sel_ubs_ativo} ({st.session_state.sel_distrito_ativo})" if is_admin else f"**UBS:** {st.session_state.ubs_user} ({st.session_state.distrito_user})"
    st.info(f"🕒 **TURNO ATIVO ATUAL:** `{st.session_state.sel_turno_ativo}`  |  📍 {unidade_atual_txt}")

    try:
        df_existente = conn.query("SELECT vacina, quantidade FROM registros_vacinacao WHERE distrito = :d AND unidade_saude = :u AND turno = :t", params={"d": st.session_state.sel_distrito_ativo, "u": st.session_state.sel_ubs_ativo, "t": st.session_state.sel_turno_ativo}, ttl=0)
    except: 
        df_existente = pd.DataFrame()

    dic_val = {v: 0 for v in lista_todas_vacinas}
    if not df_existente.empty: 
        for _, r in df_existente.iterrows(): 
            v_nome = r["vacina"]
            if v_nome in dic_val: 
                dic_val[v_nome] = r["quantidade"]
            
    df_tela_aux = []
    for v in lista_todas_vacinas:
        tipo_label = "🦠 COVID-19" if v in lista_covid else "💉 Rotina"
        df_tela_aux.append({"TIPO": tipo_label, "VACINA": v, "QUANTIDADE": dic_val[v]})
        
    df_tela = pd.DataFrame(df_tela_aux)

    editor_key = f"editor_unificado_{st.session_state.sel_distrito_ativo}_{st.session_state.sel_ubs_ativo}_{st.session_state.sel_turno_ativo}"
    df_editado = st.data_editor(df_tela, hide_index=True, use_container_width=True, disabled=["TIPO", "VACINA"], key=editor_key)

    dict_banco = dict(zip(df_existente['vacina'], df_existente['quantidade'])) if not df_existente.empty else {}
    dict_tela = dict(zip(df_editado['VACINA'], df_editado['QUANTIDADE']))
    
    tem_pendencia = False
    for vac, qtd_tela in dict_tela.items():
        qtd_banco = dict_banco.get(vac, 0)
        q_t = float(qtd_tela) if pd.notna(qtd_tela) else 0.0
        q_b = float(qtd_banco) if pd.notna(qtd_banco) else 0.0
        if q_t != q_b:
            tem_pendencia = True
            break

    if tem_pendencia:
        st.warning("⚠️ **ATENÇÃO:** Existem alterações não salvas neste turno. **O seletor de turno está bloqueado** até que você clique em **'💾 Salvar Lançamento'**.")

    with st.form("form_seletor_turno"):
        lista_turnos_opt = ["Manhã (até as 11h)", "Tarde (das 11h às 16h)"]
        
        if is_admin:
            col1, col2, col3 = st.columns(3)
            f_distrito = col1.selectbox("Selecione o Distrito:", list(ubs_por_distrito.keys()), index=list(ubs_por_distrito.keys()).index(st.session_state.sel_distrito_ativo) if st.session_state.sel_distrito_ativo in ubs_por_distrito else 0, disabled=tem_pendencia)
            lista_ubs_disp = ubs_por_distrito.get(f_distrito, [])
            idx_ubs = lista_ubs_disp.index(st.session_state.sel_ubs_ativo) if st.session_state.sel_ubs_ativo in lista_ubs_disp else 0
            f_ubs = col2.selectbox("Selecione a UBS:", lista_ubs_disp, index=idx_ubs, disabled=tem_pendencia)
            
            idx_turno = lista_turnos_opt.index(st.session_state.sel_turno_ativo) if st.session_state.sel_turno_ativo in lista_turnos_opt else 0
            f_turno = col3.selectbox("Selecione o Turno:", lista_turnos_opt, index=idx_turno, disabled=tem_pendencia)
        else:
            f_distrito = st.session_state.distrito_user
            f_ubs = st.session_state.ubs_user
            st.info(f"📍 **Unidade Fixa:** {f_ubs} ({f_distrito})")
            
            idx_turno = lista_turnos_opt.index(st.session_state.sel_turno_ativo) if st.session_state.sel_turno_ativo in lista_turnos_opt else 0
            f_turno = st.selectbox("Selecione o Turno (Automático pelo Horário):", lista_turnos_opt, index=idx_turno, disabled=True)
        
        btn_trocar = st.form_submit_button("🔄 Alterar Turno / Unidade", disabled=tem_pendencia if is_admin else True)

    if is_admin and not tem_pendencia and btn_trocar:
        st.session_state.sel_distrito_ativo = f_distrito
        st.session_state.sel_ubs_ativo = f_ubs
        st.session_state.sel_turno_ativo = f_turno
        st.rerun()

    if st.button("💾 Salvar Lançamento", type="primary"):
        try:
            with conn.session as s:
                s.execute(text("DELETE FROM registros_vacinacao WHERE distrito = :distrito AND unidade_saude = :ubs AND turno = :turno"), {"distrito": st.session_state.sel_distrito_ativo, "ubs": st.session_state.sel_ubs_ativo, "turno": st.session_state.sel_turno_ativo})
                for _, row in df_editado[df_editado["QUANTIDADE"] > 0].iterrows():
                    s.execute(text("INSERT INTO registros_vacinacao (distrito, unidade_saude, turno, vacina, quantidade) VALUES (:distrito, :ubs, :turno, :vacina, :quantidade)"), {"distrito": st.session_state.sel_distrito_ativo, "ubs": st.session_state.sel_ubs_ativo, "turno": st.session_state.sel_turno_ativo, "vacina": row["VACINA"], "quantidade": row["QUANTIDADE"]})
                s.commit()
                st.success("✅ Salvo com sucesso!")
                st.rerun()
        except Exception as e: 
            st.error(f"Erro ao salvar: {e}")

with tab2:
    if is_admin:
        st.markdown("### 📊 Painel de Relatório Consolidado")
        
        col_btn1, col_btn2 = st.columns([2, 5])
        if col_btn1.button("🔄 Atualizar Relatório", type="secondary"):
            st.rerun()

        with st.expander("⚠️ Área Administrativa: Limpar Banco de Dados"):
            st.warning("Atenção: Esta ação irá apagar **todos** os lançamentos salvos no servidor permanentemente.")
            confirmacao = st.checkbox("Sim, tenho certeza que desejo apagar todo o histórico de lançamentos.", key="chk_limpar_banco")
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
        
        try: 
            df_banco = conn.query("SELECT * FROM registros_vacinacao", ttl=0)
        except: 
            df_banco = pd.DataFrame()

        if not df_banco.empty:
            df_banco['GRUPO_TURNO'] = df_banco['vacina'].apply(lambda x: 'COVID' if ("COVID" in x.upper() or "PFIZER" in x.upper()) else 'ROTINA')
            modo = st.radio("🔍 Visualizar por:", ["Distrito", "Estabelecimento (UBS)"], horizontal=True, key="radio_modo_rel")
            nivel = 'distrito' if modo == "Distrito" else ['distrito', 'unidade_saude']
            lista_nivel = [nivel] if isinstance(nivel, str) else nivel
            
            tabelas_turnos = {}
            turnos_lista = ["Manhã (até as 11h)", "Tarde (das 11h às 16h)"]
            
            for t in turnos_lista:
                df_t = df_banco[df_banco['turno'] == t]
                if not df_t.empty:
                    cons = df_t.groupby(lista_nivel + ['GRUPO_TURNO'])['quantidade'].sum().unstack(fill_value=0)
                    cons['TOTAL'] = cons.sum(axis=1)
                    
                    if modo == "Estabelecimento (UBS)":
                        soma_distrito = cons.groupby(level=0).sum()
                        soma_distrito.index = pd.MultiIndex.from_tuples([(d, "TOTAL DISTRITO") for d in soma_distrito.index])
                        cons = pd.concat([cons, soma_distrito]).sort_index()
                    
                    tabelas_turnos[t] = cons
                    st.markdown(f"#### ⏰ {t}")
                    st.dataframe(cons, use_container_width=True)
            
            df_banco['VAC_UPPER'] = df_banco['vacina'].str.upper()
            tabela = df_banco.pivot_table(index=nivel, columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0)
            
            for v in lista_descontos:
                if v not in tabela.columns: 
                    tabela[v] = 0
            
            rotina_total = df_banco[~df_banco['vacina'].isin(lista_covid)].groupby(nivel)['quantidade'].sum()
            soma_descontos = tabela[lista_descontos].sum(axis=1)
            df_geral = pd.DataFrame(index=tabela.index)
            df_geral['ROTINA (OUTRAS)'] = (rotina_total - soma_descontos).reindex(df_geral.index).fillna(0)
            for v in lista_descontos: 
                df_geral[v] = tabela[v]
            
            cols_covid_presentes = [c for c in tabela.columns if c in lista_covid]
            df_geral['COVID'] = tabela[cols_covid_presentes].sum(axis=1) if cols_covid_presentes else 0
            
            df_geral['TOTAL GERAL'] = df_geral['ROTINA (OUTRAS)'] + soma_descontos + df_geral['COVID']
            
            if modo == "Estabelecimento (UBS)":
                soma_geral_distrito = df_geral.groupby(level=0).sum()
                soma_geral_distrito.index = pd.MultiIndex.from_tuples([(d, "TOTAL DISTRITO") for d in soma_geral_distrito.index])
                df_geral = pd.concat([df_geral, soma_geral_distrito]).sort_index()

            if isinstance(nivel, list):
                linhas_ubs = [idx for idx in df_geral.index if idx[1] != "TOTAL DISTRITO"]
                total_final_serie = df_geral.loc[linhas_ubs].sum(numeric_only=True)
            else:
                total_final_serie = df_geral.sum(numeric_only=True)

            df_geral_com_total = pd.concat([df_geral, total_final_serie.to_frame().T.rename(index={0: 'TOTAL FINAL'})])
            st.markdown("### 🏁 Total Geral")
            st.dataframe(df_geral_com_total, use_container_width=True)
            
            st.markdown("---")
            
            col_d1, col_d2 = st.columns(2)
            
            buffer_xlsx = io.BytesIO()
            with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
                for t_nome, df_t_val in tabelas_turnos.items():
                    sheet_name = t_nome.replace("(", "").replace(")", "").replace(" ", "_")[:31]
                    df_t_val.to_excel(writer, sheet_name=sheet_name)
                df_geral_com_total.to_excel(writer, sheet_name='TOTAL_GERAL')
                df_banco.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
            
            col_d1.download_button(
                "📥 Baixar Planilha Consolidada (Excel)", 
                data=buffer_xlsx.getvalue(), 
                file_name="Relatorio_Final.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            buffer_pdf = io.BytesIO()
            doc = SimpleDocTemplate(buffer_pdf, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Heading1'],
                fontSize=13,
                textColor=colors.HexColor('#1f77b4'),
                alignment=1,
                spaceAfter=6
            )
            
            section_style = ParagraphStyle(
                'SectionStyle',
                parent=styles['Heading2'],
                fontSize=9,
                textColor=colors.HexColor('#333333'),
                spaceBefore=4,
                space
