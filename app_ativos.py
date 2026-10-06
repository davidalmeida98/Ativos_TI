import streamlit as st
import pandas as pd
from datetime import datetime, date
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

def formatar_data_iso(data_input) -> str:
    """Garante que a data seja enviada no formato YYYY-MM-DD exigido pelo Supabase."""
    if isinstance(data_input, (date, datetime)):
        return data_input.strftime("%Y-%m-%d")
    
    texto = str(data_input).strip()
    if not texto or texto == "None" or texto == "N/A":
        return datetime.now().strftime("%Y-%m-%d")
    
    # Se já estiver em YYYY-MM-DD
    try:
        dt = datetime.strptime(texto, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    # Se estiver em DD-MM-YYYY ou DD-MM-YY
    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%d/%m/%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(texto, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    return datetime.now().strftime("%Y-%m-%d")

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
# 3. LEITURA E COMBINAÇÃO DAS TABELAS (BONS + RUINS)
# ==========================================
COLUNAS_ESPERADAS = [
    "Tipo", "Serial", "Marca", "Status_Geral", "Usuario", "CPF", 
    "Setor_Operacao", "Termo", "Data_Registro", "Status_Coleta", 
    "Numero_Chamado", "Defeito_Descricao", "Observacoes", "Tabela_Origem"
]

def carregar_todos_ativos():
    lista_df = []
    
    # 1. Carrega ativos_bons
    try:
        res_bons = supabase.table("ativos_bons").select("*").execute()
        df_b = pd.DataFrame(res_bons.data)
        if not df_b.empty:
            df_b.rename(columns={
                "tipo": "Tipo", "serial": "Serial", "marca": "Marca", "status": "Status_Geral",
                "usuario": "Usuario", "cpf": "CPF", "setor_operacao": "Setor_Operacao", 
                "termo": "Termo", "data": "Data_Registro", "status_coleta": "Status_Coleta",
                "numero_chamado": "Numero_Chamado", "defeito_descricao": "Defeito_Descricao",
                "observacoes": "Observacoes"
            }, inplace=True)
            df_b["Tabela_Origem"] = "ativos_bons"
            lista_df.append(df_b)
    except Exception as e:
        st.error(f"Erro ao carregar ativos operacionais: {e}")

    # 2. Carrega ativos_ruins
    try:
        res_ruins = supabase.table("ativos_ruins").select("*").execute()
        df_r = pd.DataFrame(res_ruins.data)
        if not df_r.empty:
            df_r.rename(columns={
                "tipo": "Tipo", "serial": "Serial", "marca": "Marca", 
                "status": "Status_Geral", "status_coleta": "Status_Coleta",
                "numero_chamado": "Numero_Chamado", "defeito_descricao": "Defeito_Descricao",
                "usuario_anterior": "Usuario", "setor_anterior": "Setor_Operacao",
                "data_registro": "Data_Registro"
            }, inplace=True)
            
            df_r["Status_Geral"] = df_r["Status_Geral"].replace({"DEFEITO": "Depósito TI - Defeito (Ruim)"})
            df_r["Tabela_Origem"] = "ativos_ruins"
            lista_df.append(df_r)
    except Exception as e:
        st.error(f"Erro ao carregar ativos com defeito: {e}")

    if not lista_df:
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

    df_unificado = pd.concat(lista_df, ignore_index=True)

    for col in COLUNAS_ESPERADAS:
        if col not in df_unificado.columns:
            df_unificado[col] = "N/A"

    return df_unificado

# ==========================================
# 4. BARRA LATERAL
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

# Contadores rápidos
total_ativos = len(df_ativos) if not df_ativos.empty else 0
home_office = len(df_ativos[df_ativos["Status_Geral"].astype(str).str.contains("Home", na=False)]) if not df_ativos.empty else 0
deposito_bom = len(df_ativos[df_ativos["Status_Geral"].astype(str).str.contains("Bom|ESTOQUE", na=False)]) if not df_ativos.empty else 0
deposito_ruim = len(df_ativos[df_ativos["Status_Geral"].astype(str).str.contains("Defeito|Ruim|DEFEITO", na=False)]) if not df_ativos.empty else 0
coletados = len(df_ativos[df_ativos["Status_Geral"].astype(str).str.contains("Coletado|Baixa", na=False)]) if not df_ativos.empty else 0

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
with tab1:
    st.subheader("📋 Inventário Geral")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    busca = sanitizar_texto(col_f1.text_input("🔍 Buscar por Série, Usuário, Setor ou Marca:", key="busca_geral"))
    filtro_status = col_f2.selectbox("Filtrar por Status / Localização:", ["Todos"] + LISTA_STATUS, key="f_st")
    filtro_tipo = col_f3.selectbox("Filtrar por Tipo:", ["Todos", "Notebook", "Desktop"], key="f_tp")

    df_view = df_ativos.copy()
    if not df_view.empty:
        if filtro_status != "Todos":
            df_view = df_view[df_view["Status_Geral"].astype(str).str.contains(filtro_status.split()[0], case=False, na=False)]
        if filtro_tipo != "Todos":
            df_view = df_view[df_view["Tipo"] == filtro_tipo]
        if busca:
            mask = df_view.fillna("").astype(str).apply(lambda r: r.str.contains(busca, case=False).any(), axis=1)
            df_view = df_view[mask]

        st.markdown(f"Exibindo **{len(df_view)}** equipamento(s):")
        st.markdown("---")

        for idx, row in df_view.iterrows():
            serial = row.get("Serial", "N/A")
            tipo_eq = row.get("Tipo", "Notebook")
            marca = row.get("Marca", "N/A")
            st_geral = str(row.get("Status_Geral", "Depósito TI - Bom (Reserva)"))
            usuario = str(row.get("Usuario", "")) if pd.notna(row.get("Usuario")) and str(row.get("Usuario")) != "None" else ""
            cpf = str(row.get("CPF", "")) if pd.notna(row.get("CPF")) and str(row.get("CPF")) != "None" else ""
            setor = str(row.get("Setor_Operacao", "")) if pd.notna(row.get("Setor_Operacao")) and str(row.get("Setor_Operacao")) != "None" else ""
            termo = row.get("Termo", "N/A")
            data_reg = str(row.get("Data_Registro", datetime.now().strftime("%Y-%m-%d")))
            st_coleta = row.get("Status_Coleta", "N/A")
            num_chamado = str(row.get("Numero_Chamado", "")) if pd.notna(row.get("Numero_Chamado")) and str(row.get("Numero_Chamado")) != "None" else ""
            defeito = str(row.get("Defeito_Descricao", "")) if pd.notna(row.get("Defeito_Descricao")) and str(row.get("Defeito_Descricao")) != "None" else ""
            obs = str(row.get("Observacoes", "")) if pd.notna(row.get("Observacoes")) and str(row.get("Observacoes")) != "None" else ""
            tabela_origem = row.get("Tabela_Origem", "ativos_bons")

            icone = "🏠" if "Home" in st_geral else ("🟢" if "Bom" in st_geral or "ESTOQUE" in st_geral else ("🔴" if "Defeito" in st_geral or "DEFEITO" in st_geral else "🚚"))

            titulo_header = f"{icone} [{tipo_eq}] Série: {serial} | Status: {st_geral} | Usuário: {usuario if usuario else 'N/A'}"

            with st.expander(titulo_header):
                st.markdown("### 📝 Editar Informações do Ativo")
                
                c_e1, c_e2, c_e3 = st.columns(3)
                
                with c_e1:
                    st.write(f"**Nº de Série:** {serial}")
                    st.write(f"**Tipo:** {tipo_eq}")
                    st.write(f"**Marca:** {marca}")
                    
                    idx_st = 0
                    for i, s_opt in enumerate(LISTA_STATUS):
                        if s_opt.split()[0].lower() in st_geral.lower():
                            idx_st = i
                            break
                    novo_st_geral = st.selectbox("Status / Localização
