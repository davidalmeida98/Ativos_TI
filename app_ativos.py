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
    if isinstance(data_input, (date, datetime)):
        return data_input.strftime("%Y-%m-%d")
    
    texto = str(data_input).strip()
    if not texto or texto in ("None", "N/A", "nan"):
        return datetime.now().strftime("%Y-%m-%d")
    
    try:
        dt = datetime.strptime(texto, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
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
    
    with st.form("form_login_principal", clear_on_submit=False):
        usuario_input = st.text_input("Usuário ou E-mail", key="login_email")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        btn_entrar = st.form_submit_button("Entrar", type="primary")
        
        if btn_entrar:
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
# 3. LEITURA E TRATAMENTO DOS DADOS
# ==========================================
COLUNAS_ESPERADAS = [
    "Tipo", "Serial", "Marca", "Status_Geral", "Usuario", "CPF", 
    "Setor_Operacao", "Termo", "Data_Registro", "Status_Coleta", 
    "Numero_Chamado", "Defeito_Descricao", "Observacoes", "Tabela_Origem"
]

def normalizar_status_bon(row):
    status_raw = str(row.get("status", "")).upper()
    modalidade_raw = str(row.get("modalidade", "")).lower()
    
    if "ENTREGUE" in status_raw or "home" in modalidade_raw:
        return "Em Uso (Home Office)"
    elif "ESTOQUE" in status_raw or "deposito" in modalidade_raw or "reserva" in modalidade_raw:
        return "Depósito TI - Bom (Reserva)"
    elif "COLETADO" in status_raw or "BAIXA" in status_raw:
        return "Coletado / Baixado"
    else:
        return "Depósito TI - Bom (Reserva)"

def carregar_todos_ativos():
    lista_df = []
    
    # 1. Carrega ativos_bons
    try:
        res_bons = supabase.table("ativos_bons").select("*").execute()
        df_b = pd.DataFrame(res_bons.data)
        if not df_b.empty:
            df_b["Status_Geral"] = df_b.apply(normalizar_status_bon, axis=1)
            df_b.rename(columns={
                "tipo": "Tipo", "serial": "Serial", "marca": "Marca",
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
                "status_coleta": "Status_Coleta", "numero_chamado": "Numero_Chamado", 
                "defeito_descricao": "Defeito_Descricao", "usuario_anterior": "Usuario", 
                "setor_anterior": "Setor_Operacao", "data_registro": "Data_Registro"
            }, inplace=True)
            
            df_r["Status_Geral"] = "Depósito TI - Defeito (Ruim)"
            df_r["Tabela_Origem"] = "ativos_ruins"
            lista_df.append(df_r)
    except Exception as e:
        st.error(f"Erro ao carregar ativos com defeito: {e}")

    if not lista_df:
        return pd.DataFrame(columns=COLUNAS_ESPERADAS)

    df_unificado = pd.concat(lista_df, ignore_index=True)
    df_unificado = df_unificado.drop_duplicates(subset=["Serial"], keep="last")

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

# Contadores
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
    "➕ Cadastrar / Atualizar Ativo", 
    "📊 Exportar Relatório"
])

LISTA_STATUS = [
    "Em Uso (Home Office)", 
    "Depósito TI - Bom (Reserva)", 
    "Depósito TI - Defeito (Ruim)", 
    "Coletado / Baixado"
]

# --- TAB 1: LISTA GERAL, EDIÇÃO & EXCLUSÃO ---
with tab1:
    st.subheader("📋 Inventário Geral")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    busca = sanitizar_texto(col_f1.text_input("🔍 Buscar por Série, Usuário, Setor ou Marca:", key="busca_geral"))
    filtro_status = col_f2.selectbox("Filtrar por Status / Localização:", ["Todos"] + LISTA_STATUS, key="f_st")
    filtro_tipo = col_f3.selectbox("Filtrar por Tipo:", ["Todos", "Notebook", "Desktop"], key="f_tp")

    df_view = df_ativos.copy()
    if not df_view.empty:
        if filtro_status != "Todos":
            df_view = df_view[df_view["Status_Geral"] == filtro_status]
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
            data_reg_raw = str(row.get("Data_Registro", datetime.now().strftime("%Y-%m-%d")))
            st_coleta = row.get("Status_Coleta", "N/A")
            num_chamado = str(row.get("Numero_Chamado", "")) if pd.notna(row.get("Numero_Chamado")) and str(row.get("Numero_Chamado")) != "None" else ""
            defeito = str(row.get("Defeito_Descricao", "")) if pd.notna(row.get("Defeito_Descricao")) and str(row.get("Defeito_Descricao")) != "None" else ""
            obs = str(row.get("Observacoes", "")) if pd.notna(row.get("Observacoes")) and str(row.get("Observacoes")) != "None" else ""
            tabela_origem = row.get("Tabela_Origem", "ativos_bons")

            icone = "🏠" if "Home" in st_geral else ("🟢" if "Bom" in st_geral else ("🔴" if "Defeito" in st_geral else "🚚"))

            titulo_header = f"{icone} [{tipo_eq}] Série: {serial} | Status: {st_geral} | Usuário: {usuario if usuario else 'N/A'}"

            with st.expander(titulo_header):
                st.markdown("### 📝 Editar Informações do Ativo")
                
                c_e1, c_e2, c_e3 = st.columns(3)
                
                with c_e1:
                    st.write(f"**Nº de Série:** {serial}")
                    st.write(f"**Tipo:** {tipo_eq}")
                    st.write(f"**Marca:** {marca}")
                    
                    idx_st = LISTA_STATUS.index(st_geral) if st_geral in LISTA_STATUS else 1
                    novo_st_geral = st.selectbox("Status / Localização:", LISTA_STATUS, index=idx_st, key=f"st_{serial}_{idx}")

                with c_e2:
                    novo_usuario = st.text_input("Nome do Usuário:", value=usuario, key=f"usr_{serial}_{idx}")
                    novo_cpf = st.text_input("CPF:", value=cpf, key=f"cpf_{serial}_{idx}")
                    novo_setor = st.text_input("Setor / Operação:", value=setor, key=f"set_{serial}_{idx}")
                    
                    opcoes_termo = ["ASSINADO", "PENDENTE", "N/A"]
                    idx_termo = opcoes_termo.index(termo) if termo in opcoes_termo else 2
                    novo_termo = st.selectbox("Status do Termo:", opcoes_termo, index=idx_termo, key=f"trm_{serial}_{idx}")

                with c_e3:
                    nova_data_str = st.text_input("Data de Registro / Alteração (AAAA-MM-DD):", value=formatar_data_iso(data_reg_raw), key=f"dt_{serial}_{idx}")
                    opcoes_coleta = ["N/A", "Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora"]
                    idx_coleta = opcoes_coleta.index(st_coleta) if st_coleta in opcoes_coleta else 0
                    novo_st_coleta = st.selectbox("Situação da Coleta:", opcoes_coleta, index=idx_coleta, key=f"col_{serial}_{idx}")
                    novo_chamado = st.text_input("Nº do Chamado:", value=num_chamado, key=f"cham_{serial}_{idx}")

                c_bot1, c_bot2 = st.columns(2)
                novo_defeito = c_bot1.text_input("Descrição do Defeito (Se houver):", value=defeito, key=f"def_{serial}_{idx}")
                nova_obs = c_bot2.text_input("Observações Gerais:", value=obs, key=f"obs_{serial}_{idx}")

                col_btn_salvar, col_btn_deletar = st.columns([3, 1])

                with col_btn_salvar:
                    if st.button("💾 Salvar Alterações", key=f"btn_save_{serial}_{idx}"):
                        data_formatada = formatar_data_iso(nova_data_str)
                        
                        status_db = "ENTREGUE" if "Home" in novo_st_geral else ("ESTOQUE" if "Bom" in novo_st_geral else ("DEFEITO" if "Defeito" in novo_st_geral else "COLETADO"))
                        modalidade_db = "Home Office" if "Home" in novo_st_geral else "Depósito TI (Reserva)"

                        payload_update = {
                            "status": status_db,
                            "usuario": sanitizar_texto(novo_usuario),
                            "cpf": sanitizar_texto(novo_cpf),
                            "setor_operacao": sanitizar_texto(novo_setor),
                            "termo": novo_termo,
                            "status_coleta": novo_st_coleta,
                            "numero_chamado": sanitizar_texto(novo_chamado),
                            "defeito_descricao": sanitizar_texto(novo_defeito),
                            "observacoes": sanitizar_texto(nova_obs)
                        }
                        if tabela_origem == "ativos_bons":
                            payload_update["data"] = data_formatada
                            payload_update["modalidade"] = modalidade_db
                        else:
                            payload_update["data_registro"] = data_formatada

                        try:
                            supabase.table(tabela_origem).update(payload_update).eq("serial", serial).execute()
                            st.success(f"Ativo {serial} atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar alterações: {e}")

                with col_btn_deletar:
                    # Trava de segurança para exclusão
                    key_del = f"confirm_del_{serial}_{idx}"
                    if key_del not in st.session_state:
                        st.session_state[key_del] = False

                    if not st.session_state[key_del]:
                        if st.button("🗑️ Excluir Ativo", key=f"btn_del_init_{serial}_{idx}"):
                            st.session_state[key_del] = True
                            st.rerun()
                    else:
                        st.warning("Tem certeza?")
                        c_d1, c_d2 = st.columns(2)
                        if c_d1.button("✅ Sim", key=f"btn_del_confirm_{serial}_{idx}"):
                            try:
                                supabase.table(tabela_origem).delete().eq("serial", serial).execute()
                                st.session_state[key_del] = False
                                st.success(f"Ativo {serial} excluído permanentemente!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")
                        if c_d2.button("❌ Não", key=f"btn_del_cancel_{serial}_{idx}"):
                            st.session_state[key_del] = False
                            st.rerun()
    else:
        st.info("Nenhum ativo cadastrado na base de dados.")

# --- TAB 2: CADASTRO / ATUALIZAÇÃO INTELIGENTE ---
with tab2:
    st.subheader("➕ Cadastrar ou Devolver Equipamento")
    st.caption("💡 Se a Série já existir no sistema, os dados do equipamento serão atualizados automaticamente sem duplicar.")
    
    with st.form("form_novo_ativo_completo", clear_on_submit=True):
        st.markdown("##### 1. Dados Principais do Equipamento")
        c_cad1, c_cad2, c_cad3, c_cad4 = st.columns(4)
        tipo_in = c_cad1.selectbox("Tipo:", ["Notebook", "Desktop"])
        serial_in = sanitizar_texto(c_cad2.text_input("Nº de Série (Obrigatório):"))
        marca_in = c_cad3.selectbox("Marca:", ["Positivo", "HP", "Lenovo", "Dell", "VAIO", "Outra"])
        status_in = c_cad4.selectbox("Novo Status / Localização:", LISTA_STATUS)

        st.markdown("---")
        st.markdown("##### 2. Dados do Usuário & Operação")
        c_cad5, c_cad6, c_cad7, c_cad8 = st.columns(4)
        usuario_in = c_cad5.text_input("Nome do Usuário:")
        cpf_in = c_cad6.text_input("CPF do Usuário:")
        setor_in = c_cad7.text_input("Setor / Operação:")
        termo_in = c_cad8.selectbox("Status do Termo:", ["ASSINADO", "PENDENTE", "N/A"])

        st.markdown("---")
        st.markdown("##### 3. Informações de Defeito / Coleta / Observações")
        c_cad9, c_cad10, c_cad11, c_cad12 = st.columns(4)
        data_in = c_cad9.date_input("Data da Operação:", value=date.today(), format="DD/MM/YYYY")
        st_coleta_in = c_cad10.selectbox("Status de Coleta:", ["N/A", "Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora"])
        chamado_in = c_cad11.text_input("Nº do Chamado (Opcional):")
        defeito_in = c_cad12.text_input("Descrição do Defeito (Se houver):")
        
        obs_in = st.text_input("Observações Gerais:")

        btn_cadastrar = st.form_submit_button("🚀 Salvar / Atualizar Ativo na Base", type="primary")

        if btn_cadastrar:
            if not serial_in:
                st.error("O Número de Série é obrigatório!")
            else:
                data_formatada = formatar_data_iso(data_in)
                status_db = "ENTREGUE" if "Home" in status_in else ("ESTOQUE" if "Bom" in status_in else ("DEFEITO" if "Defeito" in status_in else "COLETADO"))
                modalidade_db = "Home Office" if "Home" in status_in else "Depósito TI (Reserva)"

                existe_bons = supabase.table("ativos_bons").select("serial").eq("serial", serial_in).execute()
                existe_ruins = supabase.table("ativos_ruins").select("serial").eq("serial", serial_in).execute()

                if "Defeito" in status_in:
                    payload = {
                        "tipo": tipo_in,
                        "serial": serial_in,
                        "marca": marca_in,
                        "status": "DEFEITO",
                        "usuario_anterior": sanitizar_texto(usuario_in),
                        "setor_anterior": sanitizar_texto(setor_in),
                        "data_registro": data_formatada,
                        "status_coleta": st_coleta_in,
                        "numero_chamado": sanitizar_texto(chamado_in),
                        "defeito_descricao": sanitizar_texto(defeito_in)
                    }
                    if existe_ruins.data:
                        supabase.table("ativos_ruins").update(payload).eq("serial", serial_in).execute()
                    else:
                        supabase.table("ativos_ruins").insert(payload).execute()
                    if existe_bons.data:
                        supabase.table("ativos_bons").delete().eq("serial", serial_in).execute()
                else:
                    payload = {
                        "tipo": tipo_in,
                        "serial": serial_in,
                        "marca": marca_in,
                        "status": status_db,
                        "modalidade": modalidade_db,
                        "usuario": sanitizar_texto(usuario_in),
                        "cpf": sanitizar_texto(cpf_in),
                        "setor_operacao": sanitizar_texto(setor_in),
                        "termo": termo_in,
                        "data": data_formatada,
                        "status_coleta": st_coleta_in,
                        "numero_chamado": sanitizar_texto(chamado_in),
                        "defeito_descricao": sanitizar_texto(defeito_in),
                        "observacoes": sanitizar_texto(obs_in)
                    }
                    if existe_bons.data:
                        supabase.table("ativos_bons").update(payload).eq("serial", serial_in).execute()
                    else:
                        supabase.table("ativos_bons").insert(payload).execute()
                    if existe_ruins.data:
                        supabase.table("ativos_ruins").delete().eq("serial", serial_in).execute()

                st.success(f"Equipamento {serial_in} atualizado/cadastrado com sucesso!")
                st.rerun()

# --- TAB 3: EXPORTAÇÃO ---
with tab3:
    st.subheader("📊 Exportar Relatórios")
    if not df_ativos.empty:
        csv_data = df_ativos.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "📥 Baixar Relatório Completo de Ativos (CSV)", 
            csv_data, 
            "relatorio_ativos_unificado.csv", 
            "text/csv"
        )
    else:
        st.info("Nenhum dado disponível para exportação.")
