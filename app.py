import streamlit as st
import pandas as pd
from sqlalchemy import text
import io
import hashlib
from datetime import datetime
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
            ubs_disponiveis = ubs_por_distrito.get(cad_distrito, [])
            cad_ubs = st.selectbox("UBS do Técnico", ubs_disponiveis, key="cad_ubs_loc")

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
                except Exception as e: 
                    st.sidebar.error("Erro ao cadastrar (usuário já existe?).")
            else: 
                st.sidebar.warning("Preencha todos os campos.")

st.title("💉 Sistema de Lançamento de Vacinas - Dia D")

# LISTA UNIFICADA E ORDENADA PERFEITAMENTE EM ORDEM ALFABÉTICA
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
        hora_atual = datetime.now().hour
        return "Manhã (até as 11h)" if hora_atual < 11 else "Tarde (das 11h às 16h)"

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
        st.markdown("### 📊 Painel de Relatório
