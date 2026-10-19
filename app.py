import streamlit as st
import pandas as pd
from sqlalchemy import text
import io
import os
import hashlib
import json
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

# --- FUNÇÃO DE ESTILIZAÇÃO COMPACTA E COLORIDA ---
def destacar_linhas_tabela(df):
    def aplicar_cor_linha(row):
        idx_str = str(row.name).upper()
        if 'TOTAL FINAL' in idx_str or 'TOTAL GERAL' in idx_str or 'TOTAL MUNICÍPIO' in idx_str:
            return ['background-color: #d4edda; color: #155724; font-weight: bold; font-size: 11px;'] * len(row)
        elif 'TOTAL PARCIAL' in idx_str:
            return ['background-color: #fff3cd; color: #856404; font-weight: bold; font-size: 11px;'] * len(row)
        elif 'TOTAL DISTRITO' in idx_str:
            return ['background-color: #d1ecf1; color: #0c5460; font-weight: bold; font-size: 11px;'] * len(row)
        return ['font-size: 11px;'] * len(row)

    formatadores = {}
    for col in df.columns:
        if col != 'INFORMADO POR':
            formatadores[col] = "{:,}".format

    return df.style.apply(aplicar_cor_linha, axis=1).format(formatadores, na_rep="0")

# --- FUNÇÃO PARA CRIAR OU ATUALIZAR TABELAS NO BANCO ---
def inicializar_tabelas():
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

            s.execute(text("""
                CREATE TABLE IF NOT EXISTS registros_vacinacao (
                    id SERIAL PRIMARY KEY,
                    distrito VARCHAR(50),
                    unidade_saude VARCHAR(100),
                    turno VARCHAR(50),
                    vacina VARCHAR(100),
                    quantidade INT,
                    lancado_por VARCHAR(50)
                )
            """))
            s.commit()

            try:
                s.execute(text("ALTER TABLE registros_vacinacao ADD COLUMN IF NOT EXISTS lancado_por VARCHAR(50)"))
                s.commit()
            except:
                s.rollback()

            s.execute(text("""
                CREATE TABLE IF NOT EXISTS historico_dias_d (
                    id SERIAL PRIMARY KEY,
                    data_evento DATE NOT NULL,
                    nome_campanha VARCHAR(150) NOT NULL,
                    dados_json TEXT NOT NULL,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
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

inicializar_tabelas()

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

    st.markdown("""
        <style>
            .block-container {
                padding-top: 0rem !important;
                padding-bottom: 0rem !important;
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
                max-width: 100% !important;
            }
            header {visibility: hidden;}
            img {
                max-height: 98vh;
                object-fit: contain;
            }
            th, td {
                padding-left: 4px !important;
                padding-right: 4px !important;
            }
        </style>
    """, unsafe_allow_html=True)

    nome_imagem = "Campanha Vacinas_ Dia D do SUS.png"
    if os.path.exists(nome_imagem):
        st.image(nome_imagem, use_container_width=True)
    else:
        st.error(f"💡 Ficheiro '{nome_imagem}' não encontrado na pasta raiz do GitHub.")

    st.stop()

st.sidebar.success(f"Logado como: **{st.session_state.username}**\n\nPerfil: **{st.session_state.perfil}**")
if st.session_state.perfil == "Técnico":
    st.sidebar.info(f"📍 **UBS Vinculada:**\n{st.session_state.ubs_user} ({st.session_state.distrito_user})")

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

if is_admin: 
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Lançamento (Por Posto)", "📊 Relatório Consolidado", "📜 Histórico Dias D", "⚙️ Gerenciar Usuários"])
else: 
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Lançamento (Por Posto)", "🔒 Relatório Consolidado (Bloqueado)", "🔒 Histórico Dias D (Bloqueado)", "🔒 Gerenciar Usuários (Bloqueado)"])

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

with tab1:
    def obter_turno_automatico():
        try:
            hora_local = datetime.now(ZoneInfo("America/Fortaleza")).hour
        except Exception:
            hora_local = datetime.now().hour
        return "Manhã (até as 12h)" if hora_local < 12 else "Tarde (das 12h às 16h)"

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
                dic_val[v_nome] = int(r["quantidade"])
            
    df_tela_aux = []
    for v in lista_todas_vacinas:
        tipo_label = "🦠 COVID-19" if v in lista_covid else "💉 Rotina"
        df_tela_aux.append({"TIPO": tipo_label, "VACINA": v, "QUANTIDADE": int(dic_val[v])})
        
    df_tela = pd.DataFrame(df_tela_aux)

    editor_key = f"editor_unificado_{st.session_state.sel_distrito_ativo}_{st.session_state.sel_ubs_ativo}_{st.session_state.sel_turno_ativo}"
    df_editado = st.data_editor(df_tela, hide_index=True, use_container_width=True, disabled=["TIPO", "VACINA"], key=editor_key)

    dict_banco = dict(zip(df_existente['vacina'], df_existente['quantidade'])) if not df_existente.empty else {}
    dict_tela = dict(zip(df_editado['VACINA'], df_editado['QUANTIDADE']))
    
    tem_pendencia = False
    for vac, qtd_tela in dict_tela.items():
        qtd_banco = dict_banco.get(vac, 0)
        q_t = int(qtd_tela) if pd.notna(qtd_tela) else 0
        q_b = int(qtd_banco) if pd.notna(qtd_banco) else 0
        if q_t != q_b:
            tem_pendencia = True
            break

    if tem_pendencia:
        st.warning("⚠️ **ATENÇÃO:** Existem alterações não salvas neste turno. **O seletor de turno está bloqueado** até que você clique em **'💾 Salvar Lançamento'**.")

    with st.form("form_seletor_turno"):
        lista_turnos_opt = ["Manhã (até as 12h)", "Tarde (das 12h às 16h)"]
        
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
            usuario_atual = st.session_state.username
            with conn.session as s:
                s.execute(text("DELETE FROM registros_vacinacao WHERE distrito = :distrito AND unidade_saude = :ubs AND turno = :turno"), {"distrito": st.session_state.sel_distrito_ativo, "ubs": st.session_state.sel_ubs_ativo, "turno": st.session_state.sel_turno_ativo})
                for _, row in df_editado[df_editado["QUANTIDADE"] > 0].iterrows():
                    s.execute(text("""
                        INSERT INTO registros_vacinacao (distrito, unidade_saude, turno, vacina, quantidade, lancado_por) 
                        VALUES (:distrito, :ubs, :turno, :vacina, :quantidade, :user)
                    """), {
                        "distrito": st.session_state.sel_distrito_ativo, 
                        "ubs": st.session_state.sel_ubs_ativo, 
                        "turno": st.session_state.sel_turno_ativo, 
                        "vacina": row["VACINA"], 
                        "quantidade": int(row["QUANTIDADE"]),
                        "user": usuario_atual
                    })
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

        with st.expander("📦 Finalizar Dia D e Arquivar no Histórico"):
            st.info("Esta opção grava o relatório atual na tabela de histórico permanente para futuras pesquisas e depois limpa os lançamentos ativos para o próximo Dia D.")
            
            data_hist = st.date_input("Data do Dia D:", value=datetime.now())
            nome_campanha_hist = st.text_input("Nome da Campanha:", value="Dia D de Multivacinação")
            
            if st.button("💾 Arquivar este Dia D e Limpar Lançamentos Ativos", type="primary"):
                try:
                    df_banco_arq = conn.query("SELECT * FROM registros_vacinacao", ttl=0)
                    if df_banco_arq.empty:
                        st.warning("Não existem lançamentos ativos para arquivar!")
                    else:
                        json_dados = df_banco_arq.to_json(orient="records")
                        with conn.session as s:
                            s.execute(text("""
                                INSERT INTO historico_dias_d (data_evento, nome_campanha, dados_json)
                                VALUES (:data, :nome, :json_data)
                            """), {"data": data_hist, "nome": nome_campanha_hist.strip(), "json_data": json_dados})
                            
                            s.execute(text("DELETE FROM registros_vacinacao"))
                            s.commit()
                        st.success(f"✅ Dia D ('{nome_campanha_hist}') arquivado no histórico com sucesso e dados ativos limpos!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao arquivar Dia D: {e}")

        with st.expander("⚠️ Área Administrativa: Limpar Lançamentos Sem Arquivar"):
            st.warning("Atenção: Esta ação irá apagar **todos** os lançamentos salvos no servidor sem salvar no histórico.")
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
            if 'lancado_por' not in df_banco.columns:
                df_banco['lancado_por'] = 'Não Informado'
            else:
                df_banco['lancado_por'] = df_banco['lancado_por'].fillna('Não Informado').replace('', 'Não Informado')

            df_banco['quantidade'] = df_banco['quantidade'].fillna(0).astype(int)
            df_banco['GRUPO_TURNO'] = df_banco['vacina'].apply(lambda x: 'COVID' if ("COVID" in x.upper() or "PFIZER" in x.upper()) else 'ROTINA')
            modo = st.radio("🔍 Visualizar detalhamento por:", ["Distrito", "Estabelecimento (UBS)"], horizontal=True, key="radio_modo_rel")
            
            nivel = ['distrito', 'unidade_saude'] if modo == "Estabelecimento (UBS)" else 'distrito'
            lista_nivel = nivel if isinstance(nivel, list) else [nivel]
            
            tabelas_turnos = {}
            turnos_lista = ["Manhã (até as 12h)", "Tarde (das 12h às 16h)"]
            
            for t in turnos_lista:
                df_t = df_banco[df_banco['turno'] == t]
                if not df_t.empty:
                    cons = df_t.groupby(lista_nivel + ['GRUPO_TURNO'], dropna=False)['quantidade'].sum().unstack(fill_value=0)
                    for grp in ['ROTINA', 'COVID']:
                        if grp not in cons.columns:
                            cons[grp] = 0
                    cons['TOTAL'] = cons['ROTINA'] + cons['COVID']
                    cons = cons.astype(int)
                    
                    if modo == "Estabelecimento (UBS)":
                        dict_usr_t = df_t.groupby(['distrito', 'unidade_saude'])['lancado_por'].unique().apply(lambda u: ", ".join(sorted(set(u)))).to_dict()
                        cons['INFORMADO POR'] = [dict_usr_t.get(idx, '-') for idx in cons.index]
                        
                        soma_distrito = cons[['ROTINA', 'COVID', 'TOTAL']].groupby(level=0).sum().astype(int)
                        if not soma_distrito.empty:
                            soma_distrito['INFORMADO POR'] = '-'
                            soma_distrito.index = pd.MultiIndex.from_tuples([(d, "TOTAL DISTRITO") for d in soma_distrito.index])
                            cons = pd.concat([cons, soma_distrito]).sort_index()
                    
                    if isinstance(nivel, list):
                        linhas_ubs_t = [idx for idx in cons.index if idx[1] != "TOTAL DISTRITO"]
                        tot_turno_s = cons.loc[linhas_ubs_t, ['ROTINA', 'COVID', 'TOTAL']].sum(numeric_only=True).astype(int)
                        row_tot = tot_turno_s.to_frame().T
                        if modo == "Estabelecimento (UBS)":
                            row_tot['INFORMADO POR'] = '-'
                        cons_com_total = pd.concat([cons, row_tot.rename(index={0: ('TOTAL PARCIAL', 'TODOS OS POSTOS')})])
                    else:
                        tot_turno_s = cons[['ROTINA', 'COVID', 'TOTAL']].sum(numeric_only=True).astype(int)
                        cons_com_total = pd.concat([cons, tot_turno_s.to_frame().T.rename(index={0: 'TOTAL PARCIAL TURNO'})])

                    tabelas_turnos[t] = cons_com_total
                    st.markdown(f"#### ⏰ {t} - Visão por Grupo")
                    st.dataframe(destacar_linhas_tabela(cons_com_total), use_container_width=True)
                else:
                    st.markdown(f"#### ⏰ {t} - Visão por Grupo")
                    st.info(f"Nenhum lançamento efetuado no turno da {t.split()[0]}.")

            st.markdown("---")

            tot_geral_vac = df_banco.groupby('vacina')['quantidade'].sum().astype(int).to_frame().T
            tot_geral_vac.index = ['TOTAL MUNICÍPIO']
            
            st.markdown("### 💉 Total Geral por Vacina (Município)")
            st.dataframe(destacar_linhas_tabela(tot_geral_vac), use_container_width=True)
            st.markdown("---")

            df_banco['VAC_UPPER'] = df_banco['vacina'].str.upper()
            tabela = df_banco.pivot_table(index=nivel, columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0, dropna=False).astype(int)
            
            for v in lista_descontos:
                if v not in tabela.columns: 
                    tabela[v] = 0
            
            rotina_total = df_banco[~df_banco['vacina'].isin(lista_covid)].groupby(nivel, dropna=False)['quantidade'].sum().astype(int)
            soma_descontos = tabela[lista_descontos].sum(axis=1).astype(int)
            df_geral = pd.DataFrame(index=tabela.index)
            df_geral['ROTINA (OUTRAS)'] = (rotina_total - soma_descontos).reindex(df_geral.index).fillna(0).astype(int)
            for v in lista_descontos: 
                df_geral[v] = tabela[v].astype(int)
            
            cols_covid_presentes = [c for c in tabela.columns if c in lista_covid]
            df_geral['COVID'] = tabela[cols_covid_presentes].sum(axis=1).astype(int) if cols_covid_presentes else 0
            df_geral['TOTAL GERAL'] = (df_geral['ROTINA (OUTRAS)'] + soma_descontos + df_geral['COVID']).astype(int)
            
            if modo == "Estabelecimento (UBS)":
                soma_geral_distrito = df_geral.groupby(level=0).sum().astype(int)
                if not soma_geral_distrito.empty:
                    soma_geral_distrito.index = pd.MultiIndex.from_tuples([(d, "TOTAL DISTRITO") for d in soma_geral_distrito.index])
                    df_geral = pd.concat([df_geral, soma_geral_distrito]).sort_index()

            if isinstance(nivel, list):
                linhas_ubs = [idx for idx in df_geral.index if idx[1] != "TOTAL DISTRITO"]
                total_final_serie = df_geral.loc[linhas_ubs].sum(numeric_only=True).astype(int).to_frame().T
                idx_total_final = ('TOTAL FINAL', '')
            else:
                total_final_serie = df_geral.sum(numeric_only=True).astype(int).to_frame().T
                idx_total_final = 'TOTAL FINAL'

            df_geral_com_total = pd.concat([df_geral, total_final_serie.rename(index={0: idx_total_final})])
            st.markdown("### 🏁 Detalhamento Consolidado")
            st.dataframe(destacar_linhas_tabela(df_geral_com_total), use_container_width=True)
            
            st.markdown("---")
            
            col_d1, col_d2 = st.columns(2)
            
            buffer_xlsx = io.BytesIO()
            with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
                tot_geral_vac.to_excel(writer, sheet_name='TOTAL_POR_VACINA')
                for t_nome, df_t_val in tabelas_turnos.items():
                    sheet_name = t_nome.replace("(", "").replace(")", "").replace(" ", "_")[:31]
                    df_t_val.to_excel(writer, sheet_name=sheet_name)
                df_geral_com_total.to_excel(writer, sheet_name='TOTAL_GERAL_DETALHADO')
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
                'TitleStyle', parent=styles['Heading1'], fontSize=13, textColor=colors.HexColor('#1f77b4'), alignment=1, spaceAfter=6
            )
            section_style = ParagraphStyle(
                'SectionStyle', parent=styles['Heading2'], fontSize=9, textColor=colors.HexColor('#333333'), spaceBefore=4, spaceAfter=2
            )
            
            elements.append(Paragraph("<b>Relatório Consolidado - Sistema de Vacinação Dia D</b>", title_style))
            elements.append(Spacer(1, 2))
            
            for t_nome, df_t_val in tabelas_turnos.items():
                elements.append(Paragraph(f"<b>Turno: {t_nome}</b>", section_style))
                df_t_pdf = df_t_val.reset_index()
                if isinstance(nivel, list):
                    df_t_pdf.columns.values[0] = "Distrito"
                    df_t_pdf.columns.values[1] = "UBS"
                else:
                    df_t_pdf.columns.values[0] = "Distrito"
                
                table_data_t = [list(df_t_pdf.columns)] + [[str(val) for val in row] for row in df_t_pdf.values]
                t_turn = Table(table_data_t)
                
                style_pdf_t = [
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f77b4')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,0), 5.5),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                    ('TOPPADDING', (0,0), (-1,-1), 1),
                ]
                
                for r_idx, row in enumerate(df_t_pdf.values, start=1):
                    row_str = " ".join([str(x) for x in row]).upper()
                    if 'TOTAL PARCIAL' in row_str:
                        style_pdf_t.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#fff3cd')))
                        style_pdf_t.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))
                    elif 'TOTAL DISTRITO' in row_str:
                        style_pdf_t.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#d1ecf1')))
                        style_pdf_t.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))

                t_turn.setStyle(TableStyle(style_pdf_t))
                elements.append(t_turn)
                elements.append(Spacer(1, 3))

            elements.append(Paragraph("<b>Total Geral Consolidado por Unidade</b>", section_style))
            df_pdf = df_geral_com_total.reset_index()
            if isinstance(nivel, list):
                df_pdf.columns.values[0] = "Distrito"
                df_pdf.columns.values[1] = "UBS"
            else:
                df_pdf.columns.values[0] = "Distrito"

            table_data = [list(df_pdf.columns)] + [[str(val) for val in row] for row in df_pdf.values]
            t = Table(table_data)
            
            style_pdf_g = [
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2ca02c')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 5.5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                ('TOPPADDING', (0,0), (-1,-1), 1),
            ]
            
            for r_idx, row in enumerate(df_pdf.values, start=1):
                row_str = " ".join([str(x) for x in row]).upper()
                if 'TOTAL FINAL' in row_str:
                    style_pdf_g.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#d4edda')))
                    style_pdf_g.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))
                elif 'TOTAL DISTRITO' in row_str:
                    style_pdf_g.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#d1ecf1')))
                    style_pdf_g.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))

            t.setStyle(TableStyle(style_pdf_g))
            elements.append(t)
            doc.build(elements)
            
            col_d2.download_button(
                "📥 Baixar Relatório em PDF", 
                data=buffer_pdf.getvalue(), 
                file_name="Relatorio_Final.pdf", 
                mime="application/pdf",
                use_container_width=True
            )
            
        else:
            st.info("👈 Nenhum dado registrado no banco de dados ainda.")
    else: 
        st.warning("🔒 Acesso restrito apenas para administradores.")

with tab3:
    if is_admin:
        st.markdown("### 📜 Consulta ao Histórico de Dias D Realizados")
        try:
            df_lista_hist = conn.query("SELECT id, data_evento, nome_campanha, criado_em FROM historico_dias_d ORDER BY data_evento DESC", ttl=0)
        except:
            df_lista_hist = pd.DataFrame()
            
        if not df_lista_hist.empty:
            opcoes = [f"ID {r['id']} | {r['data_evento']} - {r['nome_campanha']}" for _, r in df_lista_hist.iterrows()]
            sel_evento = st.selectbox("Selecione a Campanha Passada para Pesquisar:", opcoes)
            
            id_sel = int(sel_evento.split(" | ")[0].replace("ID ", ""))
            
            df_evento = conn.query("SELECT * FROM historico_dias_d WHERE id = :id", params={"id": id_sel}, ttl=0)
            
            if not df_evento.empty:
                raw_json = df_evento.iloc[0]["dados_json"]
                df_banco_hist = pd.read_json(io.StringIO(raw_json))
                
                if 'lancado_por' not in df_banco_hist.columns:
                    df_banco_hist['lancado_por'] = 'Não Informado'
                else:
                    df_banco_hist['lancado_por'] = df_banco_hist['lancado_por'].fillna('Não Informado').replace('', 'Não Informado')

                df_banco_hist['quantidade'] = df_banco_hist['quantidade'].fillna(0).astype(int)
                st.success(f"📅 **Campanha:** {df_evento.iloc[0]['nome_campanha']} | **Data:** {df_evento.iloc[0]['data_evento']}")
                
                df_banco_hist['GRUPO_TURNO'] = df_banco_hist['vacina'].apply(lambda x: 'COVID' if ("COVID" in x.upper() or "PFIZER" in x.upper()) else 'ROTINA')
                modo_h = st.radio("🔍 Visualizar detalhamento por:", ["Distrito", "Estabelecimento (UBS)"], horizontal=True, key="radio_modo_hist")
                
                nivel_h = ['distrito', 'unidade_saude'] if modo_h == "Estabelecimento (UBS)" else 'distrito'
                lista_nivel_h = nivel_h if isinstance(nivel_h, list) else [nivel_h]
                
                tabelas_turnos_h = {}
                turnos_lista_h = ["Manhã (até as 12h)", "Tarde (das 12h às 16h)"]
                
                for t in turnos_lista_h:
                    df_t_h = df_banco_hist[df_banco_hist['turno'] == t]
                    if not df_t_h.empty:
                        cons_h = df_t_h.groupby(lista_nivel_h + ['GRUPO_TURNO'], dropna=False)['quantidade'].sum().unstack(fill_value=0)
                        for grp in ['ROTINA', 'COVID']:
                            if grp not in cons_h.columns:
                                cons_h[grp] = 0
                        cons_h['TOTAL'] = cons_h['ROTINA'] + cons_h['COVID']
                        cons_h = cons_h.astype(int)
                        
                        if modo_h == "Estabelecimento (UBS)":
                            dict_usr_th = df_t_h.groupby(['distrito', 'unidade_saude'])['lancado_por'].unique().apply(lambda u: ", ".join(sorted(set(u)))).to_dict()
                            cons_h['INFORMADO POR'] = [dict_usr_th.get(idx, '-') for idx in cons_h.index]

                            soma_dist_h = cons_h[['ROTINA', 'COVID', 'TOTAL']].groupby(level=0).sum().astype(int)
                            if not soma_dist_h.empty:
                                soma_dist_h['INFORMADO POR'] = '-'
                                soma_dist_h.index = pd.MultiIndex.from_tuples([(d, "TOTAL DISTRITO") for d in soma_dist_h.index])
                                cons_h = pd.concat([cons_h, soma_dist_h]).sort_index()
                        
                        if isinstance(nivel_h, list):
                            linhas_ubs_th = [idx for idx in cons_h.index if idx[1] != "TOTAL DISTRITO"]
                            tot_turno_sh = cons_h.loc[linhas_ubs_th, ['ROTINA', 'COVID', 'TOTAL']].sum(numeric_only=True).astype(int).to_frame().T
                            if modo_h == "Estabelecimento (UBS)":
                                tot_turno_sh['INFORMADO POR'] = '-'
                            cons_h_com_total = pd.concat([cons_h, tot_turno_sh.rename(index={0: ('TOTAL PARCIAL', 'TODOS OS POSTOS')})])
                        else:
                            tot_turno_sh = cons_h[['ROTINA', 'COVID', 'TOTAL']].sum(numeric_only=True).astype(int)
                            cons_h_com_total = pd.concat([cons_h, tot_turno_sh.to_frame().T.rename(index={0: 'TOTAL PARCIAL TURNO'})])

                        tabelas_turnos_h[t] = cons_h_com_total
                        st.markdown(f"#### ⏰ {t} (Histórico)")
                        st.dataframe(destacar_linhas_tabela(cons_h_com_total), use_container_width=True)
                    else:
                        st.markdown(f"#### ⏰ {t} (Histórico)")
                        st.info(f"Nenhum lançamento no turno da {t.split()[0]}.")

                st.markdown("---")

                tot_geral_vac_h = df_banco_hist.groupby('vacina')['quantidade'].sum().astype(int).to_frame().T
                tot_geral_vac_h.index = ['TOTAL MUNICÍPIO']
                st.markdown("### 💉 Total Geral por Vacina (Histórico)")
                st.dataframe(destacar_linhas_tabela(tot_geral_vac_h), use_container_width=True)
                st.markdown("---")

                df_banco_hist['VAC_UPPER'] = df_banco_hist['vacina'].str.upper()
                tabela_h = df_banco_hist.pivot_table(index=nivel_h, columns='VAC_UPPER', values='quantidade', aggfunc='sum', fill_value=0, dropna=False).astype(int)
                
                for v in lista_descontos:
                    if v not in tabela_h.columns: 
                        tabela_h[v] = 0
                
                rotina_tot_h = df_banco_hist[~df_banco_hist['vacina'].isin(lista_covid)].groupby(nivel_h, dropna=False)['quantidade'].sum().astype(int)
                soma_desc_h = tabela_h[lista_descontos].sum(axis=1).astype(int)
                df_geral_h = pd.DataFrame(index=tabela_h.index)
                df_geral_h['ROTINA (OUTRAS)'] = (rotina_tot_h - soma_desc_h).reindex(df_geral_h.index).fillna(0).astype(int)
                for v in lista_descontos: 
                    df_geral_h[v] = tabela_h[v].astype(int)
                
                cols_covid_h = [c for c in tabela_h.columns if c in lista_covid]
                df_geral_h['COVID'] = tabela_h[cols_covid_h].sum(axis=1).astype(int) if cols_covid_h else 0
                df_geral_h['TOTAL GERAL'] = (df_geral_h['ROTINA (OUTRAS)'] + soma_desc_h + df_geral_h['COVID']).astype(int)
                
                if modo_h == "Estabelecimento (UBS)":
                    soma_g_dist_h = df_geral_h.groupby(level=0).sum().astype(int)
                    if not soma_g_dist_h.empty:
                        soma_g_dist_h.index = pd.MultiIndex.from_tuples([(d, "TOTAL DISTRITO") for d in soma_g_dist_h.index])
                        df_geral_h = pd.concat([df_geral_h, soma_g_dist_h]).sort_index()

                if isinstance(nivel_h, list):
                    linhas_ubs_h = [idx for idx in df_geral_h.index if idx[1] != "TOTAL DISTRITO"]
                    tot_final_h = df_geral_h.loc[linhas_ubs_h].sum(numeric_only=True).astype(int).to_frame().T
                    idx_tf_h = ('TOTAL FINAL', '')
                else:
                    tot_final_h = df_geral_h.sum(numeric_only=True).astype(int).to_frame().T
                    idx_tf_h = 'TOTAL FINAL'

                df_geral_com_total_h = pd.concat([df_geral_h, tot_final_h.rename(index={0: idx_tf_h})])
                st.markdown("### 🏁 Detalhamento da Campanha Arquivada")
                st.dataframe(destacar_linhas_tabela(df_geral_com_total_h), use_container_width=True)
                
                st.markdown("---")
                
                # --- BOTÕES DE DOWNLOAD (EXCEL E PDF) PARA O HISTÓRICO ---
                col_dh1, col_dh2 = st.columns(2)
                
                buffer_xlsx_h = io.BytesIO()
                with pd.ExcelWriter(buffer_xlsx_h, engine='openpyxl') as writer:
                    tot_geral_vac_h.to_excel(writer, sheet_name='TOTAL_POR_VACINA')
                    for t_nome, df_t_val_h in tabelas_turnos_h.items():
                        sheet_name = t_nome.replace("(", "").replace(")", "").replace(" ", "_")[:31]
                        df_t_val_h.to_excel(writer, sheet_name=sheet_name)
                    df_geral_com_total_h.to_excel(writer, sheet_name='TOTAL_GERAL_DETALHADO')
                    df_banco_hist.to_excel(writer, sheet_name='HISTORICO_LANCAMENTOS', index=False)
                
                col_dh1.download_button(
                    "📥 Baixar Planilha do Histórico (Excel)", 
                    data=buffer_xlsx_h.getvalue(), 
                    file_name=f"Historico_Campanha_{id_sel}.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                buffer_pdf_h = io.BytesIO()
                doc_h = SimpleDocTemplate(buffer_pdf_h, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
                elements_h = []
                
                elements_h.append(Paragraph(f"<b>Relatório Histórico: {df_evento.iloc[0]['nome_campanha']} ({df_evento.iloc[0]['data_evento']})</b>", title_style))
                elements_h.append(Spacer(1, 2))
                
                for t_nome, df_t_val_h in tabelas_turnos_h.items():
                    elements_h.append(Paragraph(f"<b>Turno: {t_nome}</b>", section_style))
                    df_t_pdf_h = df_t_val_h.reset_index()
                    if isinstance(nivel_h, list):
                        df_t_pdf_h.columns.values[0] = "Distrito"
                        df_t_pdf_h.columns.values[1] = "UBS"
                    else:
                        df_t_pdf_h.columns.values[0] = "Distrito"
                    
                    table_data_th = [list(df_t_pdf_h.columns)] + [[str(val) for val in row] for row in df_t_pdf_h.values]
                    t_turn_h = Table(table_data_th)
                    
                    style_pdf_th = [
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f77b4')),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,0), 5.5),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                        ('TOPPADDING', (0,0), (-1,-1), 1),
                    ]
                    
                    for r_idx, row in enumerate(df_t_pdf_h.values, start=1):
                        row_str = " ".join([str(x) for x in row]).upper()
                        if 'TOTAL PARCIAL' in row_str:
                            style_pdf_th.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#fff3cd')))
                            style_pdf_th.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))
                        elif 'TOTAL DISTRITO' in row_str:
                            style_pdf_th.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#d1ecf1')))
                            style_pdf_th.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))

                    t_turn_h.setStyle(TableStyle(style_pdf_th))
                    elements_h.append(t_turn_h)
                    elements_h.append(Spacer(1, 3))

                elements_h.append(Paragraph("<b>Total Geral Consolidado por Unidade (Histórico)</b>", section_style))
                df_pdf_h = df_geral_com_total_h.reset_index()
                if isinstance(nivel_h, list):
                    df_pdf_h.columns.values[0] = "Distrito"
                    df_pdf_h.columns.values[1] = "UBS"
                else:
                    df_pdf_h.columns.values[0] = "Distrito"

                table_data_gh = [list(df_pdf_h.columns)] + [[str(val) for val in row] for row in df_pdf_h.values]
                t_gh = Table(table_data_gh)
                
                style_pdf_gh = [
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2ca02c')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,0), 5.5),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                    ('TOPPADDING', (0,0), (-1,-1), 1),
                ]
                
                for r_idx, row in enumerate(df_pdf_h.values, start=1):
                    row_str = " ".join([str(x) for x in row]).upper()
                    if 'TOTAL FINAL' in row_str:
                        style_pdf_gh.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#d4edda')))
                        style_pdf_gh.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))
                    elif 'TOTAL DISTRITO' in row_str:
                        style_pdf_gh.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#d1ecf1')))
                        style_pdf_gh.append(('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'))

                t_gh.setStyle(TableStyle(style_pdf_gh))
                elements_h.append(t_gh)
                doc_h.build(elements_h)
                
                col_dh2.download_button(
                    "📥 Baixar Relatório em PDF (Histórico)", 
                    data=buffer_pdf_h.getvalue(), 
                    file_name=f"Historico_Campanha_{id_sel}.pdf", 
                    mime="application/pdf",
                    use_container_width=True
                )
                
                with st.expander("🗑️ Excluir este Histórico"):
                    if st.button(f"Confirmar Exclusão do Registro ID {id_sel}", type="primary"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM historico_dias_d WHERE id = :id"), {"id": id_sel})
                            s.commit()
                        st.success("Registro excluído com sucesso!")
                        st.rerun()
        else:
            st.info("Nenhum Dia D arquivado no histórico até o momento.")
    else:
        st.warning("🔒 Acesso restrito apenas para administradores.")

with tab4:
    if is_admin:
        st.markdown("### 👥 Gerenciamento de Usuários Cadastrados")
        try:
            df_usuarios = conn.query("SELECT id, username, perfil, distrito, ubs FROM usuarios ORDER BY id", ttl=0)
        except:
            df_usuarios = pd.DataFrame()
            
        if not df_usuarios.empty:
            st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("#### ⚙️ Alterar Perfil, Unidade ou Senha do Usuário")
            
            usuario_selecionado = st.selectbox("Selecione o Usuário:", df_usuarios["username"].tolist(), key="sel_user_edicao")
            user_info = df_usuarios[df_usuarios["username"] == usuario_selecionado].iloc[0]
            
            current_perfil = user_info["perfil"]
            idx_perfil = 0 if current_perfil == "Técnico" else 1
            
            novo_perfil_edit = st.selectbox("Alterar Perfil", ["Técnico", "Administrador"], index=idx_perfil, key=f"perfil_{usuario_selecionado}")
            
            edit_distrito = "Geral"
            edit_ubs = "Geral"
            
            if novo_perfil_edit == "Técnico":
                db_dist = user_info["distrito"] if user_info["distrito"] in ubs_por_distrito else list(ubs_por_distrito.keys())[0]
                idx_dist = list(ubs_por_distrito.keys()).index(db_dist)
                
                edit_distrito = st.selectbox("Distrito", list(ubs_por_distrito.keys()), index=idx_dist, key=f"dist_{usuario_selecionado}")
                
                ubs_list = ubs_por_distrito.get(edit_distrito, [])
                db_ubs = user_info["ubs"] if user_info["ubs"] in ubs_list else ubs_list[0]
                idx_ubs = ubs_list.index(db_ubs) if db_ubs in ubs_list else 0
                
                edit_ubs = st.selectbox("UBS", ubs_list, index=idx_ubs, key=f"ubs_{usuario_selecionado}")
            
            nova_senha_admin = st.text_input("Nova Senha (opcional - deixe em branco para não alterar)", type="password", key=f"nova_senha_adm_{usuario_selecionado}")

            col1, col2 = st.columns(2)
            if col1.button("🔄 Atualizar Dados", key=f"btn_atualizar_{usuario_selecionado}"):
                try:
                    with conn.session as s:
                        if nova_senha_admin.strip():
                            hash_nova = hashlib.sha256(nova_senha_admin.strip().encode()).hexdigest()
                            s.execute(
                                text("UPDATE usuarios SET perfil = :pf, distrito = :d, ubs = :ub, senha = :p WHERE username = :u"),
                                {"pf": novo_perfil_edit, "d": edit_distrito, "ub": edit_ubs, "p": hash_nova, "u": usuario_selecionado}
                            )
                        else:
                            s.execute(
                                text("UPDATE usuarios SET perfil = :pf, distrito = :d, ubs = :ub WHERE username = :u"),
                                {"pf": novo_perfil_edit, "d": edit_distrito, "ub": edit_ubs, "u": usuario_selecionado}
                            )
                        s.commit()
                    st.success(f"✅ Utilizador '{usuario_selecionado}' atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")
                    
            if col2.button("🗑️ Excluir Utilizador", type="primary", key=f"btn_excluir_{usuario_selecionado}"):
                if usuario_selecionado == "admin":
                    st.error("⚠️ O utilizador principal 'admin' não pode ser excluído!")
                else:
                    try:
                        with conn.session as s:
                            s.execute(text("DELETE FROM usuarios WHERE username = :u"), {"u": usuario_selecionado})
                            s.commit()
                        st.success(f"🗑️ Utilizador '{usuario_selecionado}' excluído com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
        else:
            st.info("Nenhum utilizador cadastrado.")
    else:
        st.warning("🔒 Acesso restrito apenas para administradores.")
