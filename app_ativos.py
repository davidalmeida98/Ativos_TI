import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="Gestão Unificada de Ativos TI", layout="wide")

# Oculta menus e cabeçalhos do Streamlit
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

DOMINIO_PADRAO = "@sistema.local"

def sanitizar_texto(texto: str) -> str:
    if not texto:
        return ""
    return str(texto).strip()

def tratar_usuario_ou_email(entrada: str) -> str:
    entrada = sanitizar_texto(entrada).lower()
    if not entrada:
        return ""
    if "@" not in entrada:
        return f"{entrada}{DOMINIO_PADRAO}"
    return entrada

def formatar_nome_exibicao(email: str) -> str:
    if email and email.endswith(DOMINIO_PADRAO):
        return email.replace(DOMINIO_PADRAO, "")
    return email

# ==========================================
# 1. CONFIGURAÇÃO DO SUPABASE
# ==========================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://iipvcbqyrwmwjbizavlw.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlpcHZjYnF5cndtd2piaXphdmx3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA4NzQ4OTQsImV4cCI6MjEwNjQ1MDg5NH0.yXtk30yQrmzwFFbMBFgoTt2-S7qnhzoyEWlWs9qywp4")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Controle de sessão por navegador
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None

# ==========================================
# 2. TELA DE LOGIN OBRIGATÓRIA
# ==========================================
if not st.session_state.user_authenticated:
    st.title("🔒 Acesso ao Sistema de Ativos TI")
    st.subheader("Login Obrigatório")
    
    usuario_input = st.text_input("Usuário ou E-mail", key="login_email")
    senha_login = st.text_input("Senha", type="password", key="login_senha")
    
    if st.button("Entrar", type="primary", key="btn_entrar"):
        if usuario_input and senha_login:
            email_final = tratar_usuario_ou_email(usuario_input)
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email_final,
                    "password": senha_login
                })
                if res.user:
                    st.session_state.user_authenticated = True
                    st.session_state.user_email = res.user.email
                    st.success("Login efetuado com sucesso!")
                    st.rerun()
            except Exception:
                st.error("Erro ao fazer login: Usuário ou senha incorretos.")
        else:
            st.warning("Preencha o usuário e a senha.")

    st.stop()

# ==========================================
# 3. LEITURA DE DADOS (TABELA UNIFICADA)
# ==========================================
def carregar_todos_ativos():
    try:
        # Busca da tabela principal de ativos
        response = supabase.table("ativos_bons").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=[
                "Tipo", "Serial", "Marca", "Status_Geral", "Usuario", "CPF", 
                "Setor_Operacao", "Termo", "Data", "Status_Coleta", 
                "Numero_Chamado", "Defeito_Descricao", "Observacoes"
            ])
        df.rename(columns={
            "tipo": "Tipo", "serial": "Serial", "marca": "Marca", "status": "Status_Geral",
            "usuario": "Usuario", "cpf": "CPF", "setor_operacao": "Setor_Operacao", 
            "termo": "Termo", "data": "Data", "status_coleta": "Status_Coleta",
            "numero_chamado": "Numero_Chamado", "defeito_descricao": "Defeito_Descricao",
            "observacoes": "Observacoes"
        }, inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar banco de dados: {e}")
        return pd.DataFrame()

# ==========================================
# 4. BARRA LATERAL (LOGOUT E INFORMAÇÕES)
# ==========================================
nome_usuario_atual = formatar_nome_exibicao(st.session_state.user_email)
st.sidebar.write(f"👤 Usuário Conectado: **{nome_usuario_atual}**")

if st.sidebar.button("Sair (Logout)", key="btn_logout"):
    st.session_state.user_authenticated = False
    st.session_state.user_email = None
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.rerun()

st.sidebar.markdown("---")

# ==========================================
# 5. INTERFACE PRINCIPAL
# ==========================================
st.title("🖥️ Gestão Unificada de Ativos TI")

df_ativos = carregar_todos_ativos()

# Contadores rápidos de Status
total_ativos = len(df_ativos) if not df_ativos.empty else 0
home_office = len(df_ativos[df_ativos["Status_Geral"] == "Em Uso (Home Office)"]) if not df_ativos.empty else 0
deposito_bom = len(df_ativos[df_ativos["Status_Geral"] == "Depósito TI - Bom (Reserva)"]) if not df_ativos.empty else 0
deposito_ruim = len(df_ativos[df_ativos["Status_Geral"] == "Depósito TI - Defeito (Ruim)"]) if not df_ativos.empty else 0
coletados = len(df_ativos[df_ativos["Status_Geral"] == "Coletado / Baixado"]) if not df_ativos.empty else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📦 Total de Ativos", total_ativos)
c2.metric("🏠 Home Office", home_office)
c3.metric("🟢 Depósito (Bom)", deposito_bom)
c4.metric("🔴 Depósito (Ruim)", deposito_ruim)
c5.metric("🚚 Coletados / Baixa", coletados)

st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    "📋 Lista Geral de Ativos (Consulta & Edição)", 
    "➕ Cadastrar Novo Ativo", 
    "📊 Exportar Relatório"
])

LISTA_STATUS = [
    "Em Uso (Home Office)", 
    "Depósito TI - Bom (Reserva)", 
    "Depósito TI - Defeito (Ruim)", 
    "Coletado / Baixado"
]

# --- TAB 1: LISTA GERAL & EDIÇÃO ---
with
