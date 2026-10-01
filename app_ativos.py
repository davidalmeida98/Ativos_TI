import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="Gestão de Ativos TI - Cloud", layout="wide")

# ==========================================
# 1. CONFIGURAÇÃO DO SUPABASE
# ==========================================
SUPABASE_URL = "https://iipvcbqyrwmwjbizavlw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlpcHZjYnF5cndtd2piaXphdmx3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA4NzQ4OTQsImV4cCI6MjEwNjQ1MDg5NH0.yXtk30yQrmzwFFbMBFgoTt2-S7qnhzoyEWlWs9qywp4"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Recupera a sessão salva no Supabase (caso já tenha feito login anteriormente)
if "user" not in st.session_state or st.session_state.user is None:
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            st.session_state.user = session.user
        else:
            st.session_state.user = None
    except Exception:
        st.session_state.user = None

# ==========================================
# 2. TELA DE LOGIN (PÚBLICA)
# ==========================================
if st.session_state.user is None:
    st.title("🔒 Acesso ao Sistema de Ativos TI")
    
    st.subheader("Login")
    email_login = st.text_input("E-mail", key="login_email")
    senha_login = st.text_input("Senha", type="password", key="login_senha")
    
    if st.button("Entrar", type="primary", key="btn_entrar"):
        if email_login and senha_login:
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email_login,
                    "password": senha_login
                })
                st.session_state.user = res.user
                st.success("Login efetuado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao fazer login: {e}")
        else:
            st.warning("Preencha o e-mail e a senha.")

    st.stop()  # Impede a visualização do painel se não estiver logado
# ==========================================
# 3. BARRA LATERAL (LOGOUT E CADASTRO PRIVADO)
# ==========================================
st.sidebar.write(f"👤 Usuário: **{st.session_state.user.email}**")

if st.sidebar.button("Sair (Logout)", key="btn_logout"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")

# Área Restrita na Barra Lateral para Cadastrar Novos Usuários
with st.sidebar.expander("➕ Cadastrar Novo Usuário"):
    novo_email = st.text_input("E-mail do novo usuário", key="cad_email")
    nova_senha = st.text_input("Senha inicial", type="password", key="cad_senha")
    
    if st.button("Criar Conta", key="btn_criar_usuario"):
        if novo_email and nova_senha:
            try:
                res = supabase.auth.sign_up({
                    "email": novo_email,
                    "password": nova_senha
                })
                st.success(f"Conta criada para {novo_email}!")
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")
        else:
            st.warning("Preencha e-mail e senha.")

# ==========================================
# 4. LEITURA DE DADOS DO SUPABASE
# ==========================================
def carregar_bons():
    try:
        response = supabase.table("ativos_bons").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=["Tipo", "Serial", "Marca", "Status", "Modalidade", "Usuario", "CPF", "Setor_Operacao", "Termo", "Data", "Observacoes"])
        df.rename(columns={
            "tipo": "Tipo", "serial": "Serial", "marca": "Marca", "status": "Status",
            "modalidade": "Modalidade", "usuario": "Usuario", "cpf": "CPF",
            "setor_operacao": "Setor_Operacao", "termo": "Termo", "data": "Data", "observacoes": "Observacoes"
        }, inplace=True)
        return df
    except Exception:
        return pd.DataFrame(columns=["Tipo", "Serial", "Marca", "Status", "Modalidade", "Usuario", "CPF", "Setor_Operacao", "Termo", "Data", "Observacoes"])

def carregar_ruins():
    try:
        response = supabase.table("ativos_ruins").select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return pd.DataFrame(columns=["Tipo", "Serial", "Marca", "Nova_Leva", "Status", "Status_Coleta", "Numero_Chamado", "Defeito_Descricao", "Usuario_Anterior", "Setor_Anterior", "Data_Registro", "Data_Coleta"])
        df.rename(columns={
            "tipo": "Tipo", "serial": "Serial", "marca": "Marca", "nova_leva": "Nova_Leva",
            "status": "Status", "status_coleta": "Status_Coleta", "numero_chamado": "Numero_Chamado",
            "defeito_descricao": "Defeito_Descricao", "usuario_anterior": "Usuario_Anterior",
            "setor_anterior": "Setor_Anterior", "data_registro": "Data_Registro", "data_coleta": "Data_Coleta"
        }, inplace=True)
        return df
    except Exception:
        return pd.DataFrame(columns=["Tipo", "Serial", "Marca", "Nova_Leva", "Status", "Status_Coleta", "Numero_Chamado", "Defeito_Descricao", "Usuario_Anterior", "Setor_Anterior", "Data_Registro", "Data_Coleta"])

# ==========================================
# 5. INTERFACE PRINCIPAL
# ==========================================
st.title("🖥️ Gestão de Ativos TI (Nuvem)")

df_bons = carregar_bons()
df_ruins = carregar_ruins()

# Métricas
aguardando = len(df_ruins[df_ruins["Status_Coleta"] == "Aguardando Coleta"]) if not df_ruins.empty else 0
coletados = len(df_ruins[df_ruins["Status_Coleta"].str.contains("Coletado", na=False)]) if not df_ruins.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Bons (Home Office / Depósito TI)", len(df_bons))
c2.metric("🔴 Ruins / Defeito", len(df_ruins))
c3.metric("⏳ Aguardando Coleta", aguardando)
c4.metric("📦 Coletados", coletados)

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "🟢 Ativos Bons (Home Office / Depósito TI)", 
    "🔴 Ativos Ruins & Coleta em Massa", 
    "➕ Cadastrar Equipamentos", 
    "📊 Exportar Relatórios"
])

# TAB 1: ATIVOS BONS
with tab1:
    st.subheader("🟢 Ativos Operacionais e em Estoque")
    col_b1, col_b2 = st.columns(2)
    busca_bom = col_b1.text_input("Buscar por Nº de Série, Usuário ou Setor:", key="busca_bom").strip()
    filtro_tipo_bom = col_b2.selectbox("Filtrar Tipo:", ["Todos", "Notebook", "Desktop"])
    
    df_b = df_bons.copy()
    if not df_b.empty:
        if filtro_tipo_bom != "Todos":
            df_b = df_b[df_b["Tipo"] == filtro_tipo_bom]
        if busca_bom:
            mask = df_b.fillna("").astype(str).apply(lambda r: r.str.contains(busca_bom, case=False).any(), axis=1)
            df_b = df_b[mask]
        st.dataframe(df_b[["Tipo", "Serial", "Marca", "Modalidade", "Usuario", "CPF", "Setor_Operacao", "Termo", "Data", "Observacoes"]], use_container_width=True)
    else:
        st.info("Nenhum ativo bom cadastrado até o momento.")

# TAB 2: ATIVOS RUINS & COLETA
with tab2:
    st.subheader("🔴 Triagem de Defeitos e Atualização de Coleta em Massa")
    df_r = df_ruins.copy()
    
    if not df_r.empty:
        col_f1, col_f2, col_f3 = st.columns(3)
        busca_ruim = col_f1.text_input("Buscar por Nº de Série, Marca ou Chamado:", key="busca_ruim").strip()
        filtro_tipo_ruim = col_f2.selectbox("Filtrar Tipo:", ["Todos", "Notebook", "Desktop"], key="f_tp_r")
        filtro_coleta = col_f3.selectbox("Status da Coleta:", ["Todos", "Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora"])
        
        if filtro_tipo_ruim != "Todos":
            df_r = df_r[df_r["Tipo"] == filtro_tipo_ruim]
        if filtro_coleta != "Todos":
            df_r = df_r[df_r["Status_Coleta"] == filtro_coleta]
        if busca_ruim:
            mask_r = df_r.fillna("").astype(str).apply(lambda r: r.str.contains(busca_ruim, case=False).any(), axis=1)
            df_r = df_r[mask_r]

        st.markdown("---")
        with st.expander("🚚 Atualização de Coleta em Lote (Selecionar Múltiplos)", expanded=False):
            df_r_sel = df_r.copy()
            df_r_sel["Selecionar"] = False
            
            edited_df = st.data_editor(
                df_r_sel[["Selecionar", "Tipo", "Serial", "Marca", "Nova_Leva", "Status_Coleta", "Numero_Chamado", "Defeito_Descricao"]],
                column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False)},
                disabled=["Tipo", "Serial", "Marca", "Nova_Leva", "Numero_Chamado", "Defeito_Descricao"],
                hide_index=True,
                key="editor_coleta"
            )
            
            col_m1, col_m2 = st.columns(2)
            novo_status_massa = col_m1.selectbox("Alterar Status de Coleta dos Selecionados Para:", ["Coletado pela Vivo", "Coletado pela Empresa Locadora", "Em Processo de Baixa", "Aguardando Coleta"])
            
            if col_m2.button("🚀 Aplicar Alteração nos Itens Marcados"):
                itens_selecionados = edited_df[edited_df["Selecionar"] == True]["Serial"].tolist()
                if not itens_selecionados:
                    st.error("Nenhum equipamento foi selecionado!")
                else:
                    for ser in itens_selecionados:
                        payload = {"status_coleta": novo_status_massa}
                        if "Coletado" in novo_status_massa:
                            payload["data_coleta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        supabase.table("ativos_ruins").update(payload).eq("serial", ser).execute()
                    st.success(f"Status de {len(itens_selecionados)} equipamento(s) atualizado!")
                    st.rerun()

        st.markdown("---")
        for idx, row in df_r.iterrows():
            serial = row.get("Serial", "N/A")
            tipo_eq = row.get("Tipo", "Notebook")
            marca = row.get("Marca", "N/A")
            nova_leva = row.get("Nova_Leva", "Não")
            st_coleta = row.get("Status_Coleta", "Aguardando Coleta")
            defeito = row.get("Defeito_Descricao", "N/A")
            chamado = row.get("Numero_Chamado", "")
            
            icone = "⏳" if st_coleta == "Aguardando Coleta" else "📦"
            with st.expander(f"{icone} [{tipo_eq}] Série: {serial} | Marca: {marca} | Coleta: {st_coleta}"):
                c_left, c_right = st.columns(2)
                with c_left:
                    st.write(f"**Tipo:** {tipo_eq}")
                    st.write(f"**Nº de Série:** {serial}")
                    st.write(f"**Marca / Modelo:** {marca}")
                    st.write(f"**É da Nova Leva?:** {nova_leva}")
                with c_right:
                    opcoes_coleta = ["Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora", "Em Processo de Baixa"]
                    idx_coleta = opcoes_coleta.index(st_coleta) if st_coleta in opcoes_coleta else 0
                    novo_st_coleta = st.selectbox("Situação da Coleta:", opcoes_coleta, index=idx_coleta, key=f"col_{serial}")
                    novo_chamado = st.text_input("Nº do Chamado:", value=str(chamado) if pd.notna(chamado) else "", key=f"cham_{serial}")
                    novo_defeito = st.text_input("Descrição do Defeito:", value=str(defeito), key=f"def_{serial}")
                    
                if st.button("Salvar Ficha", key=f"btn_r_{serial}"):
                    update_data = {
                        "status_coleta": novo_st_coleta,
                        "numero_chamado": novo_chamado,
                        "defeito_descricao": novo_defeito
                    }
                    supabase.table("ativos_ruins").update(update_data).eq("serial", serial).execute()
                    st.success("Atualizado no banco!")
                    st.rerun()
    else:
        st.info("Nenhum equipamento com defeito cadastrado.")

# TAB 3: CADASTRO DE EQUIPAMENTOS
with tab3:
    st.subheader("➕ Entrada de Equipamentos")
    tipo_registro = st.radio("Estado Inicial:", ["🟢 BOM / Operacional (Home Office ou Depósito TI)", "🔴 RUIM / Com Defeito"])
    
    with st.form("form_novo", clear_on_submit=True):
        c_f1, c_f2 = st.columns(2)
        tipo_eq_in = c_f1.selectbox("Tipo de Equipamento:", ["Notebook", "Desktop"])
        serial_in = c_f2.text_input("Número de Série (Obrigatório):")
        marca_in = st.selectbox("Marca:", ["Positivo", "HP", "Lenovo", "Dell", "VAIO", "Outra"])
        
        if "BOM" in tipo_registro:
            modalidade_in = st.selectbox("Localização / Modalidade:", ["Home Office", "Depósito TI (Reserva)"])
            usuario_in = st.text_input("Nome do Usuário:")
            cpf_in = st.text_input("CPF:")
            setor_in = st.text_input("Setor / Operação:")
            termo_in = st.selectbox("Status do Termo:", ["ASSINADO", "PENDENTE", "N/A"])
            obs_in = st.text_input("Observações:")
        else:
            nova_leva_in = st.radio("É da Nova Leva?", ["Sim", "Não"])
            st_coleta_in = st.selectbox("Status Inicial da Coleta:", ["Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora"])
            chamado_in = st.text_input("Nº do Chamado:")
            defeito_in = st.text_input("Descrição do Defeito:")
            
        submeter = st.form_submit_button("Salvar no Banco Cloud")
        
        if submeter:
            if not serial_in.strip():
                st.error("Preencha o Número de Série!")
            else:
                if "BOM" in tipo_registro:
                    payload = {
                        "tipo": tipo_eq_in, "serial": serial_in.strip(), "marca": marca_in,
                        "status": "ENTREGUE" if modalidade_in == "Home Office" else "ESTOQUE",
                        "modalidade": modalidade_in, "usuario": usuario_in, "cpf": cpf_in,
                        "setor_operacao": setor_in, "termo": termo_in,
                        "data": datetime.now().strftime("%Y-%m-%d"), "observacoes": obs_in
                    }
                    supabase.table("ativos_bons").insert(payload).execute()
                else:
                    payload = {
                        "tipo": tipo_eq_in, "serial": serial_in.strip(), "marca": marca_in,
                        "nova_leva": nova_leva_in, "status": "DEFEITO", "status_coleta": st_coleta_in,
                        "numero_chamado": chamado_in, "defeito_descricao": defeito_in,
                        "data_registro": datetime.now().strftime("%Y-%m-%d")
                    }
                    supabase.table("ativos_ruins").insert(payload).execute()
                st.success("Equipamento salvo com sucesso!")
                st.rerun()

# TAB 4: EXPORTAÇÃO
with tab4:
    st.subheader("📊 Exportar Relatórios")
    col_d1, col_d2 = st.columns(2)
    if not df_bons.empty:
        csv_b = df_bons.to_csv(index=False, sep=";").encode("utf-8-sig")
        col_d1.download_button("📥 Baixar Ativos BONS (CSV)", csv_b, "ativos_bons.csv", "text/csv")
    if not df_ruins.empty:
        csv_r = df_ruins.to_csv(index=False, sep=";").encode("utf-8-sig")
        col_d2.download_button("📥 Baixar Ativos RUINS (CSV)", csv_r, "ativos_ruins.csv", "text/csv")
