import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import base64
import json
from PIL import Image
import io
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# Configuração da tela
st.set_page_config(page_title="GTT • Gestão de Tarefas & Tempo", page_icon="⏱️", layout="wide")

# --- ESTILO VISUAL INSPIRADO NO TRELLO & LOGO GTT ---
st.markdown("""
<style>
    .gtt-header {
        background: linear-gradient(135deg, #0052CC 0%, #026AA7 100%);
        padding: 16px 22px;
        border-radius: 12px;
        color: white;
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
        box-shadow: 0 4px 12px rgba(0, 82, 204, 0.2);
    }
    .gtt-title {
        font-size: 1.55rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.3px;
        color: #FFFFFF;
    }
    .gtt-subtitle {
        font-size: 0.9rem;
        margin: 2px 0 0 0;
        color: #DCE9F9;
    }
    .kanban-col-header {
        background-color: #EBECF0;
        color: #172B4D;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.98rem;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-left: 5px solid #026AA7;
    }
    .kanban-badge {
        background-color: #DFE1E6;
        color: #172B4D;
        padding: 2px 9px;
        border-radius: 12px;
        font-size: 0.82rem;
    }
</style>
""", unsafe_allow_html=True)

LOGO_GTT_SVG = """
<svg width="56" height="56" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" rx="14" fill="#FFFFFF"/>
  <rect x="4" y="4" width="56" height="56" rx="11" fill="#0052CC"/>
  <circle cx="46" cy="18" r="10" fill="#36B37E"/>
  <path d="M46 13V18.5L49.5 20.5" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M15 24H31M15 32H29" stroke="#85B8FF" stroke-width="2.5" stroke-linecap="round"/>
  <text x="14" y="49" fill="#FFFFFF" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="18" letter-spacing="1">GTT</text>
</svg>
"""

st.markdown(f"""
<div class="gtt-header">
    <div>{LOGO_GTT_SVG}</div>
    <div>
        <div class="gtt-title">Gestão de Tarefas & Tempo (GTT)</div>
        <div class="gtt-subtitle">Controle de Serviços & Organização • Loja 1 (Balcão/Oficina) & Loja 2 (Estoque)</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- CONEXÃO COM O BANCO DE DADOS NA NUVEM (SUPABASE) ---
SUPABASE_URL = "https://wccmtfatnvrpwcssvlwv.supabase.co"
SUPABASE_KEY = "sb_publishable_wlrUzSPQy9iUlxijchZ9oA_BXNi4dcT"
TABELA_URL = f"{SUPABASE_URL}/rest/v1/registros"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# --- EQUIPE COMPLETA (10 COLABORADORES) E PIN DE ACESSO (4 dígitos) ---
EQUIPE = {
    "Géslei (Agente Administrativo)": "1001",
    "Juliano (Vendedor)": "1002",
    "Laerte (Estoquista)": "1003",
    "Guilherme (Vendedor)": "1004",
    "Vinicius (Balconista)": "1005",
    "Cristiano (Estoquista)": "1006",
    "Esdras (Auxiliar Administrativo)": "1007",
    "Alessandro (Balconista)": "1008",
    "Isaac (Estoquista)": "1009",
    "Victor (Entregador)": "1010"
}

NOMES_CURTOS = {k.split(" (")[0]: k for k in EQUIPE.keys()}
OPCAO_LIVRE = "🕒 Disponível (Qualquer livre assume)"

# --- CATÁLOGO DE TAREFAS FIXAS E PESOS (PONTOS) ---
TAREFAS = {
    "Organizar e abastecer prateleiras": 50,
    "Organizar rolos de cordas": 25,
    "Organizar mangueiras de jardim": 25,
    "Descarte de resíduos semanal": 25,
    "Auditar estoque": 25,
    "Lançar notas / Atualizar preços": 25,
    "Atendimento telefônico / WhatsApp": 25,
    "Limpeza do ambiente": 25,
    "Organizar itens pesados": 15,
    "Medir / etiquetar retalhos de mangueira": 15,
    "Organizar cabos de aço": 15,
    "Outra atividade (Descrever)": 20
}

# --- HORA EXATA DE SÃO PAULO / BRASÍLIA (UTC-3) ---
def obter_hora_brasilia():
    try:
        agora_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        agora_sp = datetime.now(timezone.utc) - timedelta(hours=3)
    return agora_sp.strftime("%d/%m/%Y %H:%M")

# --- COMPRESSÃO LEVE EM MINIATURA ---
def processar_foto_miniatura(foto_enviada):
    if foto_enviada is None:
        return ""
    try:
        foto_enviada.seek(0)
        img = Image.open(foto_enviada)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((500, 500))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=62)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_base64}"
    except Exception as e:
        st.error(f"Erro ao processar imagem: {e}")
        return ""

# --- EMPACOTA E DESEMPACOTA FOTOS ANTES / DEPOIS NO MESMO CAMPO ---
def empacotar_fotos(antes_b64, depois_b64):
    if not antes_b64 and not depois_b64:
        return ""
    return json.dumps({"antes": antes_b64, "depois": depois_b64})

def extrair_fotos(valor_campo):
    if not isinstance(valor_campo, str) or not valor_campo.strip():
        return "", ""
    texto = valor_campo.strip()
    if texto.startswith("{"):
        try:
            dados = json.loads(texto)
            return dados.get("antes", ""), dados.get("depois", "")
        except Exception:
            return "", ""
    if texto.startswith("data:image"):
        return "", texto
    return "", ""

# --- CALCULA PORCENTAGEM REAL A PARTIR DOS PONTOS ---
def calcular_percentual_registro(row):
    if "percentual" in row and pd.notna(row["percentual"]):
        return int(row["percentual"])
    tarefa_nome = row.get("tarefa", "")
    pontos_reg = float(row.get("pontos", 0) or 0)
    if pontos_reg == 0:
        return 0
    peso_tarefa = TAREFAS.get(tarefa_nome, 20)
    if peso_tarefa > 0:
        calc = int(round((pontos_reg / peso_tarefa) * 100 / 10.0) * 10)
        return max(0, min(100, calc))
    return 0

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados():
    try:
        res = requests.get(f"{TABELA_URL}?select=*&order=id.desc", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            dados = res.json()
            if dados:
                return pd.DataFrame(dados)
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
    return pd.DataFrame(columns=["id", "data_hora", "colaborador", "tarefa", "pontos", "observacao", "foto_base64"])

def salvar_registro(registro):
    try:
        res = requests.post(TABELA_URL, json=registro, headers=HEADERS, timeout=10)
        if res.status_code in [200, 201]:
            return True
        registro_enxuto = {k: v for k, v in registro.items() if k not in ["unidade", "percentual"]}
        res2 = requests.post(TABELA_URL, json=registro_enxuto, headers=HEADERS, timeout=10)
        if res2.status_code in [200, 201]:
            return True
        st.error(f"Erro Supabase ({res2.status_code}): {res2.text}")
        return False
    except Exception as e:
        st.error(f"Erro ao salvar registro: {e}")
        return False

def atualizar_registro(registro_id, campos_atualizados):
    try:
        res = requests.patch(f"{TABELA_URL}?id=eq.{registro_id}", json=campos_atualizados, headers=HEADERS, timeout=10)
        if res.status_code in [200, 204]:
            return True
        campos_enxutos = {k: v for k, v in campos_atualizados.items() if k not in ["unidade", "percentual"]}
        res2 = requests.patch(f"{TABELA_URL}?id=eq.{registro_id}", json=campos_enxutos, headers=HEADERS, timeout=10)
        if res2.status_code in [200, 204]:
            return True
        st.error(f"Erro ao atualizar ({res2.status_code}): {res2.text}")
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar registro: {e}")
        return False

def excluir_registro_completo(registro_id):
    try:
        res = requests.delete(f"{TABELA_URL}?id=eq.{registro_id}", headers=HEADERS, timeout=10)
        return res.status_code in [200, 204]
    except Exception as e:
        st.error(f"Erro ao excluir registro: {e}")
        return False

# --- ABAS DO SISTEMA GTT ---
aba_trello, aba_direto, aba_indices, aba_historico = st.tabs([
    "🗂️ Quadro GTT (Trello)",
    "✅ Lançar Direto",
    "🏆 Índices",
    "📜 Concluídos & Histórico"
])

# ================= ABA 1: QUADRO KANBAN ESTILO TRELLO (4 COLUNAS) =================
with aba_trello:
    with st.expander("➕ Criar Novo Cartão de Serviço (Todos os Membros)", expanded=True):
        # 1) BOTÕES COM OS NOMES PARA QUEM CRIOU
        st.markdown("**1. ✍️ Quem criou esta tarefa? (Clique no seu nome):**")
        criador_curto = st.pills(
            "Quem criou:",
            options=list(NOMES_CURTOS.keys()),
            default="Géslei",
            selection_mode="single",
            label_visibility="collapsed",
            key="pills_criador"
        )
        if not criador_curto:
            criador_curto = "Géslei"
        criador_card = NOMES_CURTOS[criador_curto]

        # 2) BOTÕES COM OS NOMES PARA QUEM VAI EXECUTAR
        st.markdown("**2. 👷 Quem vai executar esta tarefa? (Escolha o responsável):**")
        opcoes_executor_pills = ["Livre (Qualquer um)"] + list(NOMES_CURTOS.keys())
        executor_curto = st.pills(
            "Quem vai executar:",
            options=opcoes_executor_pills,
            default="Livre (Qualquer um)",
            selection_mode="single",
            label_visibility="collapsed",
            key="pills_executor"
        )
        if not executor_curto or executor_curto == "Livre (Qualquer um)":
            responsavel_card = OPCAO_LIVRE
        else:
            responsavel_card = NOMES_CURTOS[executor_curto]

        c_new1, c_new2, c_new3 = st.columns([1.2, 1.3, 1.5])
        with c_new1:
            pin_criador = st.text_input(
                f"🔑 PIN de {criador_curto} (4 dígitos):",
                type="password",
                max_chars=4,
                placeholder="Digite seu PIN",
                key="trello_pin_criador"
            )
        with c_new2:
            unidade_card = st.radio("Unidade:", ["Loja 1 (Balcão/Oficina)", "Loja 2 (Estoque)"], horizontal=True, key="trello_unid")
        with c_new3:
            tarefa_card = st.selectbox("Serviço / Tarefa:", list(TAREFAS.keys()), key="trello_tarefa")
            tarefa_card_final = tarefa_card
            if tarefa_card == "Outra atividade (Descrever)":
                tarefa_card_final = st.text_input("Descreva o serviço:", placeholder="Ex: Melhorar a aparência do balcão", key="trello_tarefa_desc")
        
        c_det1, c_det2 = st.columns([1.5, 1.5])
        with c_det1:
            obs_card = st.text_input("Instruções / Detalhes do cartão (opcional):", placeholder="Ex: Deixar apenas o necessário", key="trello_obs")
        with c_det2:
            foto_inicial_card = st.file_uploader("📸 Foto de Capa / ANTES (opcional):", type=["jpg", "jpeg", "png"], key="trello_foto_init")
        
        if st.button(f"📌 Criar Cartão (Criado por {criador_curto} → Para {executor_curto})", type="primary", use_container_width=True):
            if pin_criador != EQUIPE[criador_card]:
                st.error(f"❌ PIN incorreto para {criador_curto}! Digite seu PIN de 4 dígitos.")
            elif not tarefa_card_final.strip():
                st.warning("⚠️ Descreva o serviço antes de adicionar o cartão.")
            else:
                with st.spinner("Criando cartão no quadro GTT..."):
                    agora_br = obter_hora_brasilia()
                    antes_b64 = processar_foto_miniatura(foto_inicial_card)
                    pacote_fotos = empacotar_fotos(antes_b64, "")
                    etiqueta_unid = "Loja 1" if "Loja 1" in unidade_card else "Loja 2"
                    obs_formatada = f"[{etiqueta_unid}] [Criado por: {criador_curto}] {obs_card.strip()}".strip()
                    
                    novo_cartao = {
                        "data_hora": agora_br,
                        "colaborador": responsavel_card,
                        "unidade": unidade_card,
                        "tarefa": tarefa_card_final.strip(),
                        "percentual": 0,
                        "pontos": 0,
                        "observacao": obs_formatada,
                        "foto_base64": pacote_fotos
                    }
                    if salvar_registro(novo_cartao):
                        st.success(f"✅ Cartão criado por {criador_curto} e enviado para '📋 A fazer'!")
                        st.rerun()

    # Filtros do Quadro
    col_f_tr1, col_f_tr2, col_f_tr3 = st.columns([2, 2, 1])
    with col_f_tr1:
        filtro_resp_trello = st.selectbox("Filtrar por Executor:", ["Todos", OPCAO_LIVRE] + list(EQUIPE.keys()), key="filtro_trello_resp")
    with col_f_tr2:
        filtro_loja_trello = st.selectbox("Filtrar por Unidade:", ["Todas", "Loja 1", "Loja 2"], key="filtro_trello_loja")
    with col_f_tr3:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar", use_container_width=True):
            st.rerun()

    df_trello = carregar_dados()
    if df_trello.empty:
        st.info("Nenhum cartão encontrado. Crie o primeiro cartão acima!")
    else:
        df_trello["progresso_%"] = df_trello.apply(calcular_percentual_registro, axis=1)
        
        if filtro_resp_trello != "Todos":
            df_trello = df_trello[df_trello["colaborador"] == filtro_resp_