import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
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

def sanitizar_texto(texto) -> str:
    if texto is None or pd.isna(texto):
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
    if not texto or texto in ("None", "N/A", "nan", ""):
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
                except Exception as err:
                    st.error(f"Erro ao fazer login: {err}")
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

LISTA_STATUS = [
    "Em Uso (Home Office / Remoto)", 
    "Alocado em Unidade / Operação / Setor",
    "Data Center / Sala de Servidores / Rack",
    "Infraestrutura Predial / Portaria / Acesso",
    "Depósito TI - Bom (Reserva Tecnológica)", 
    "Depósito TI - Defeito / Manutenção", 
    "Em Trânsito / Transferência / Devolvido"
]

LISTA_TIPOS = [
    "Notebook", 
    "Desktop", 
    "Servidor", 
    "Ativo de Rede (Switch/Router/Firewall)", 
    "Nobreak / Estabilizador", 
    "Monitor", 
    "Periférico / Outro"
]

def normalizar_status_bon(row):
    status_raw = str(row.get("status", "")).upper()
    modalidade_raw = str(row.get("modalidade", "")).lower()
    
    if "SERVER" in status_raw or "data center" in modalidade_raw or "rack" in modalidade_raw or "servidor" in modalidade_raw:
        return "Data Center / Sala de Servidores / Rack"
    elif "PORTARIA" in status_raw or "portaria" in modalidade_raw or "acesso" in modalidade_raw:
        return "Infraestrutura Predial / Portaria / Acesso"
    elif "OPERAÇÃO" in status_raw or "operacao" in modalidade_raw or "presencial" in modalidade_raw or "unidade" in modalidade_raw:
        return "Alocado em Unidade / Operação / Setor"
    elif "ENTREGUE" in status_raw or "home" in modalidade_raw:
        return "Em Uso (Home Office / Remoto)"
    elif "ESTOQUE" in status_raw or "deposito" in modalidade_raw or "reserva" in modalidade_raw:
        return "Depósito TI - Bom (Reserva Tecnológica)"
    elif "COLETADO" in status_raw or "BAIXA" in status_raw or "TRANSITO" in status_raw:
        return "Em Trânsito / Transferência / Devolvido"
    else:
        return "Depósito TI - Bom (Reserva Tecnológica)"

def carregar_todos_ativos():
    lista_df = []
    
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
            
            df_r["Status_Geral"] = "Depósito TI - Defeito / Manutenção"
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

total_ativos = len(df_ativos) if not df_ativos.empty else 0
home_office = len(df_ativos[df_ativos["Status_Geral"] == "Em Uso (Home Office / Remoto)"]) if not df_ativos.empty else 0
unidades_operacao = len(df_ativos[df_ativos["Status_Geral"] == "Alocado em Unidade / Operação / Setor"]) if not df_ativos.empty else 0
datacenter_infra = len(df_ativos[df_ativos["Status_Geral"].isin(["Data Center / Sala de Servidores / Rack", "Infraestrutura Predial / Portaria / Acesso"])]) if not df_ativos.empty else 0
deposito_bom = len(df_ativos[df_ativos["Status_Geral"] == "Depósito TI - Bom (Reserva Tecnológica)"]) if not df_ativos.empty else 0
deposito_ruim = len(df_ativos[df_ativos["Status_Geral"] == "Depósito TI - Defeito / Manutenção"]) if not df_ativos.empty else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("📦 Total de Ativos", total_ativos)
c2.metric("🏠 Home Office", home_office)
c3.metric("🏢 Operação / Unidades", unidades_operacao)
c4.metric("🖥️ Data Center / Infra", datacenter_infra)
c5.metric("🟢 Depósito (Bom)", deposito_bom)
c6.metric("🔴 Defeito / Manutenção", deposito_ruim)

st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    "📋 Lista Geral de Ativos (Consulta & Edição)", 
    "➕ Cadastrar / Atualizar Ativo", 
    "📊 Exportar Relatório"
])

# --- TAB 1: LISTA GERAL, EDIÇÃO & EXCLUSÃO ---
with tab1:
    st.subheader("📋 Inventário Geral")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    busca = sanitizar_texto(col_f1.text_input("🔍 Buscar por Série, Usuário, Setor, Marca ou IP/Tag:", key="busca_geral"))
    filtro_status = col_f2.selectbox("Filtrar por Status / Localização:", ["Todos"] + LISTA_STATUS, key="f_st")
    filtro_tipo = col_f3.selectbox("Filtrar por Tipo de Equipamento:", ["Todos"] + LISTA_TIPOS, key="f_tp")

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
            serial_original = sanitizar_texto(row.get("Serial")) or "N/A"
            tipo_eq = sanitizar_texto(row.get("Tipo")) or "Notebook"
            marca = sanitizar_texto(row.get("Marca")) or "Generica"
            st_geral = sanitizar_texto(row.get("Status_Geral")) or "Depósito TI - Bom (Reserva Tecnológica)"
            usuario = sanitizar_texto(row.get("Usuario"))
            cpf = sanitizar_texto(row.get("CPF"))
            setor = sanitizar_texto(row.get("Setor_Operacao"))
            termo = sanitizar_texto(row.get("Termo")) or "N/A"
            data_reg_raw = str(row.get("Data_Registro", datetime.now().strftime("%Y-%m-%d")))
            st_coleta = sanitizar_texto(row.get("Status_Coleta")) or "N/A"
            num_chamado = sanitizar_texto(row.get("Numero_Chamado"))
            defeito = sanitizar_texto(row.get("Defeito_Descricao"))
            obs = sanitizar_texto(row.get("Observacoes"))
            tabela_origem = row.get("Tabela_Origem", "ativos_bons")

            icone = "🏠" if "Home" in st_geral else ("🖥️" if "Data Center" in st_geral else ("🚪" if "Infraestrutura" in st_geral else ("🏢" if "Unidade" in st_geral else ("🟢" if "Bom" in st_geral else ("🔴" if "Defeito" in st_geral else "🚚")))))

            titulo_header = f"{icone} [{tipo_eq}] Série: {serial_original} | Marca: {marca} | Status: {st_geral} | Resp./Local: {usuario if usuario else (setor if setor else 'N/A')}"

            with st.expander(titulo_header):
                st.markdown("### 📝 Editar Informações do Ativo")
                
                c_e1, c_e2, c_e3 = st.columns(3)
                
                with c_e1:
                    novo_serial = st.text_input("Nº de Série / Asset Tag:", value=serial_original, key=f"srl_{serial_original}_{idx}")
                    
                    idx_tipo = LISTA_TIPOS.index(tipo_eq) if tipo_eq in LISTA_TIPOS else 0
                    novo_tipo = st.selectbox("Tipo de Equipamento:", LISTA_TIPOS, index=idx_tipo, key=f"tp_{serial_original}_{idx}")
                    
                    nova_marca = st.text_input("Marca / Fabricante:", value=marca, key=f"mc_{serial_original}_{idx}")
                    
                    idx_st = LISTA_STATUS.index(st_geral) if st_geral in LISTA_STATUS else 4
                    novo_st_geral = st.selectbox("Status / Categoria de Localização:", LISTA_STATUS, index=idx_st, key=f"st_{serial_original}_{idx}")

                with c_e2:
                    novo_usuario = st.text_input("Usuário / Responsável Técnico:", value=usuario, key=f"usr_{serial_original}_{idx}")
                    novo_cpf = st.text_input("CPF / Identificação:", value=cpf, key=f"cpf_{serial_original}_{idx}")
                    novo_setor = st.text_input("Localização Detalhada (Ex: PA-05, Rack 02, Guarita, Sala TI):", value=setor, key=f"set_{serial_original}_{idx}")
                    
                    opcoes_termo = ["ASSINADO", "PENDENTE", "N/A"]
                    idx_termo = opcoes_termo.index(termo) if termo in opcoes_termo else 2
                    novo_termo = st.selectbox("Status do Termo / Alocação:", opcoes_termo, index=idx_termo, key=f"trm_{serial_original}_{idx}")

                with c_e3:
                    nova_data_str = st.text_input("Data de Registro / Modificação (AAAA-MM-DD):", value=formatar_data_iso(data_reg_raw), key=f"dt_{serial_original}_{idx}")
                    opcoes_coleta = ["N/A", "Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora"]
                    idx_coleta = opcoes_coleta.index(st_coleta) if st_coleta in opcoes_coleta else 0
                    novo_st_coleta = st.selectbox("Situação da Coleta / Devolução:", opcoes_coleta, index=idx_coleta, key=f"col_{serial_original}_{idx}")
                    novo_chamado = st.text_input("Nº do Chamado / Ticket:", value=num_chamado, key=f"cham_{serial_original}_{idx}")

                c_bot1, c_bot2 = st.columns(2)
                novo_defeito = c_bot1.text_input("Descrição de Defeito / Observação Técnica:", value=defeito, key=f"def_{serial_original}_{idx}")
                nova_obs = c_bot2.text_input("Observações Gerais / Hostname / IP:", value=obs, key=f"obs_{serial_original}_{idx}")

                col_btn_salvar, col_btn_deletar = st.columns([3, 1])

                with col_btn_salvar:
                    if st.button("💾 Salvar Alterações", key=f"btn_save_{serial_original}_{idx}"):
                        data_formatada = formatar_data_iso(nova_data_str)
                        
                        status_db = "ENTREGUE" if novo_st_geral in ["Em Uso (Home Office / Remoto)", "Alocado em Unidade / Operação / Setor", "Data Center / Sala de Servidores / Rack", "Infraestrutura Predial / Portaria / Acesso"] else ("ESTOQUE" if "Bom" in novo_st_geral else ("DEFEITO" if "Defeito" in novo_st_geral else "COLETADO"))
                        modalidade_db = novo_st_geral

                        payload_update = {
                            "serial": sanitizar_texto(novo_serial),
                            "tipo": novo_tipo,
                            "marca": sanitizar_texto(nova_marca),
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
                            supabase.table(tabela_origem).update(payload_update).eq("serial", serial_original).execute()
                            st.success(f"Ativo {novo_serial} atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar no Supabase: {e}")

                with col_btn_deletar:
                    key_del = f"confirm_del_{serial_original}_{idx}"
                    if key_del not in st.session_state:
                        st.session_state[key_del] = False

                    if not st.session_state[key_del]:
                        if st.button("🗑️ Excluir Ativo", key=f"btn_del_init_{serial_original}_{idx}"):
                            st.session_state[key_del] = True
                            st.rerun()
                    else:
                        st.warning("Tem certeza?")
                        c_d1, c_d2 = st.columns(2)
                        if c_d1.button("✅ Sim", key=f"btn_del_confirm_{serial_original}_{idx}"):
                            try:
                                supabase.table(tabela_origem).delete().eq("serial", serial_original).execute()
                                st.session_state[key_del] = False
                                st.success(f"Ativo {serial_original} excluído permanentemente!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")
                        if c_d2.button("❌ Não", key=f"btn_del_cancel_{serial_original}_{idx}"):
                            st.session_state[key_del] = False
                            st.rerun()
    else:
        st.info("Nenhum ativo cadastrado na base de dados.")

# --- TAB 2: CADASTRO / ATUALIZAÇÃO INTELIGENTE ---
with tab2:
    st.subheader("➕ Cadastrar ou Atualizar Equipamento / Servidor / Infraestrutura")
    st.caption("💡 Se o Número de Série já existir no sistema, os dados serão atualizados automaticamente sem duplicar.")
    
    # Processamento fora do form via sessão para garantir gravação sem perda
    tipo_in = st.selectbox("Tipo de Equipamento:", LISTA_TIPOS, key="cad_tipo")
    serial_in = sanitizar_texto(st.text_input("Nº de Série / Tag (Obrigatório):", key="cad_serial"))
    marca_in = st.text_input("Marca / Fabricante (Ex: Dell, HP, Lenovo, Cisco, Positivo):", value="Dell", key="cad_marca")
    status_in = st.selectbox("Status / Categoria de Localização:", LISTA_STATUS, key="cad_status")

    st.markdown("---")
    usuario_in = st.text_input("Usuário / Resp. Técnico (Ex: Nome, Adm, Infra TI):", key="cad_user")
    cpf_in = st.text_input("CPF / ID (Opcional):", key="cad_cpf")
    setor_in = st.text_input("Detalhes da Localização (Ex: Rack 01, PA-12, Portaria 2):", key="cad_setor")
    termo_in = st.selectbox("Status do Termo / Alocação:", ["ASSINADO", "PENDENTE", "N/A"], key="cad_termo")

    st.markdown("---")
    data_in = st.date_input("Data da Operação:", value=date.today(), format="DD/MM/YYYY", key="cad_data")
    st_coleta_in = st.selectbox("Situação da Coleta / Remessa:", ["N/A", "Aguardando Coleta", "Coletado pela Vivo", "Coletado pela Empresa Locadora"], key="cad_coleta")
    chamado_in = st.text_input("Nº do Chamado / Ticket (Opcional):", key="cad_chamado")
    defeito_in = st.text_input("Descrição do Defeito / Obs. Técnica:", key="cad_defeito")
    obs_in = st.text_input("Observações Gerais / IP / Hostname / Tag:", key="cad_obs")

    if st.button("🚀 Salvar / Atualizar Ativo na Base", type="primary", key="btn_exec_cad"):
        if not serial_in:
            st.error("O Número de Série é obrigatório!")
        else:
            data_formatada = formatar_data_iso(data_in)
            status_db = "ENTREGUE" if status_in in ["Em Uso (Home Office / Remoto)", "Alocado em Unidade / Operação / Setor", "Data Center / Sala de Servidores / Rack", "Infraestrutura Predial / Portaria / Acesso"] else ("ESTOQUE" if "Bom" in status_in else ("DEFEITO" if "Defeito" in status_in else "COLETADO"))
            modalidade_db = status_in

            try:
                existe_bons = supabase.table("ativos_bons").select("serial").eq("serial", serial_in).execute()
                existe_ruins = supabase.table("ativos_ruins").select("serial").eq("serial", serial_in).execute()

                if "Defeito" in status_in:
                    payload = {
                        "tipo": tipo_in,
                        "serial": serial_in,
                        "marca": sanitizar_texto(marca_in),
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
                        "marca": sanitizar_texto(marca_in),
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
            except Exception as e:
                st.error(f"❌ Erro ao cadastrar/atualizar no Supabase: {e}")

# --- TAB 3: EXPORTAÇÃO COMPATÍVEL E DIRETA ---
with tab3:
    st.subheader("📊 Exportar Relatórios")
    if not df_ativos.empty:
        buffer = io.BytesIO()
        df_ativos.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
        buffer.seek(0)
        
        st.download_button(
            label="📥 Baixar Relatório Completo de Ativos (CSV)",
            data=buffer,
            file_name=f"relatorio_ativos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="btn_download_csv"
        )
    else:
        st.info("Nenhum dado disponível para exportação.")
