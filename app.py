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

st.set_page_config(page_title="GTT • Gestão de Tarefas & Tempo", page_icon="⏱️", layout="wide")

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

SUPABASE_URL = "https://wccmtfatnvrpwcssvlwv.supabase.co"
SUPABASE_KEY = "sb_publishable_wlrUzSPQy9iUlxijchZ9oA_BXNi4dcT"
TABELA_URL = f"{SUPABASE_URL}/rest/v1/registros"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

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

def obter_hora_brasilia():
    try:
        agora_sp = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        agora_sp = datetime.now(timezone.utc) - timedelta(hours=3)
    return agora_sp.strftime("%d/%m/%Y %H:%M")

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

aba_trello, aba_direto, aba_indices, aba_historico = st.tabs([
    "🗂️ Quadro GTT (Trello)",
    "✅ Lançar Direto",
    "🏆 Índices",
    "📜 Concluídos & Histórico"
])

with aba_trello:
    with st.expander("➕ Criar Novo Cartão de Serviço (Todos os Membros)", expanded=True):
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

    col_f_tr1, col_f_tr2, col_f_tr3 = st.columns([2, 2, 1])
    with col_f_tr1:
        filtro_resp = st.selectbox("Filtrar por Executor:", ["Todos", OPCAO_LIVRE] + list(EQUIPE.keys()), key="filtro_trello_resp")
    with col_f_tr2:
        filtro_loja = st.selectbox("Filtrar por Unidade:", ["Todas", "Loja 1", "Loja 2"], key="filtro_trello_loja")
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
        
        if filtro_resp != "Todos":
            df_trello = df_trello[df_trello["colaborador"] == filtro_resp]
        if filtro_loja != "Todas":
            df_trello = df_trello[df_trello["observacao"].astype(str).str.contains(filtro_loja, na=False)]

        df_afazer = df_trello[df_trello["progresso_%"] == 0]
        df_andamento = df_trello[(df_trello["progresso_%"] > 0) & (df_trello["progresso_%"] < 90)]
        df_aprovacao = df_trello[df_trello["progresso_%"] == 90]
        df_concluido = df_trello[df_trello["progresso_%"] >= 100].head(12)

        col_k1, col_k2, col_k3, col_k4 = st.columns(4)

        def renderizar_cartao(row, estagio):
            reg_id = row.get("id")
            colab_atual = str(row.get("colaborador", OPCAO_LIVRE))
            nome_curto = colab_atual.split(" (")[0]
            tarefa_txt = str(row.get("tarefa", ""))
            obs_txt = str(row.get("observacao", "") or "")
            data_txt = str(row.get("data_hora", ""))
            perc = int(row.get("progresso_%", 0))
            peso_tarefa = TAREFAS.get(tarefa_txt, 20)
            pts_atuais = float(row.get("pontos", 0) or 0)
            antes_b64, depois_b64 = extrair_fotos(row.get("foto_base64", ""))

            badge_loja = "🔵 Loja 1" if "[Loja 1]" in obs_txt else ("🟠 Loja 2" if "[Loja 2]" in obs_txt else "⚪ Geral")
            
            criador_info = ""
            obs_sem_tags = obs_txt.replace("[Loja 1]", "").replace("[Loja 2]", "").strip()
            if "[Criado por:" in obs_sem_tags:
                partes = obs_sem_tags.split("]", 1)
                criador_info = partes[0].replace("[", "").strip()
                obs_limpa = partes[1].strip() if len(partes) > 1 else ""
            else:
                obs_limpa = obs_sem_tags

            with st.container(border=True):
                if depois_b64.startswith("data:image"):
                    st.image(depois_b64, use_container_width=True)
                elif antes_b64.startswith("data:image"):
                    st.image(antes_b64, use_container_width=True)

                st.markdown(f"**{tarefa_txt}**")
                if obs_limpa:
                    st.caption(f"{obs_limpa}")
                
                info_meta = f"{badge_loja} • 🏆 {peso_tarefa} pts • 🕒 {data_txt}"
                if criador_info:
                    info_meta += f" • ✍️ {criador_info}"
                st.caption(info_meta)
                
                if colab_atual == OPCAO_LIVRE:
                    st.warning("👷 Executor: Livre para assumir")
                else:
                    st.markdown(f"👷 **{nome_curto}** • **{perc}%** ({pts_atuais} pts)")

                if antes_b64.startswith("data:image") and depois_b64.startswith("data:image"):
                    cm1, cm2 = st.columns(2)
                    with cm1:
                        st.image(antes_b64, caption="Antes", use_container_width=True)
                    with cm2:
                        st.image(depois_b64, caption="Depois", use_container_width=True)

                if estagio in ["afazer", "andamento", "aprovacao"]:
                    label_acao = "👀 Aprovar / Concluir" if estagio == "aprovacao" else "⚡ Mover / Concluir"
                    with st.expander(label_acao):
                        quem_move = st.selectbox(
                            "Quem está executando:",
                            list(EQUIPE.keys()),
                            index=list(EQUIPE.keys()).index(colab_atual) if colab_atual in EQUIPE else 0,
                            key=f"sel_colab_{reg_id}"
                        )
                        pin_move = st.text_input("PIN (4 dígitos):", type="password", max_chars=4, key=f"pin_move_{reg_id}")
                        
                        if estagio == "aprovacao":
                            st.info("Validação do gestor (PIN 1001) para concluir 100% ou devolver.")
                            foto_up_card = st.file_uploader("📸 Foto adicional (opcional):", type=["jpg", "jpeg", "png"], key=f"foto_aprov_{reg_id}")
                            ca1, ca2 = st.columns(2)
                            with ca1:
                                if st.button("✅ Aprovar (100%)", type="primary", use_container_width=True, key=f"btn_ok_{reg_id}"):
                                    if pin_move != EQUIPE["Géslei (Agente Administrativo)"]:
                                        st.error("❌ Apenas o PIN do Gestor (1001) aprova.")
                                    else:
                                        depois_novo = processar_foto_miniatura(foto_up_card) if foto_up_card else depois_b64
                                        payload = {
                                            "percentual": 100,
                                            "pontos": float(peso_tarefa),
                                            "data_hora": obter_hora_brasilia(),
                                            "foto_base64": empacotar_fotos(antes_b64, depois_novo)
                                        }
                                        if atualizar_registro(reg_id, payload):
                                            st.success("🎉 Movido para Concluídos!")
                                            st.rerun()
                            with ca2:
                                if st.button("↩️ Devolver (50%)", use_container_width=True, key=f"btn_dev_{reg_id}"):
                                    if pin_move != EQUIPE["Géslei (Agente Administrativo)"]:
                                        st.error("❌ Apenas o PIN do Gestor (1001) devolve.")
                                    else:
                                        payload = {
                                            "percentual": 50,
                                            "pontos": round(peso_tarefa * 0.5, 1),
                                            "data_hora": obter_hora_brasilia()
                                        }
                                        if atualizar_registro(reg_id, payload):
                                            st.warning("Devolvido para Em andamento.")
                                            st.rerun()
                        else:
                            valor_sugerido = 20 if estagio == "afazer" else min(90, perc + 30)
                            novo_progresso = st.slider(
                                "Progresso (90% = Aprovação / 100% = Concluídos):",
                                min_value=10,
                                max_value=100,
                                value=valor_sugerido,
                                step=10,
                                key=f"prog_move_{reg_id}"
                            )
                            foto_up_card = st.file_uploader(
                                "📸 Foto (Antes ou Depois):",
                                type=["jpg", "jpeg", "png"],
                                key=f"foto_move_{reg_id}"
                            )
                            cb1, cb2 = st.columns(2)
                            with cb1:
                                if st.button("💾 Salvar & Mover", type="primary", use_container_width=True, key=f"btn_move_{reg_id}"):
                                    if pin_move not in [EQUIPE[quem_move], EQUIPE["Géslei (Agente Administrativo)"]]:
                                        st.error("❌ PIN incorreto.")
                                    else:
                                        novos_pontos = round((peso_tarefa * novo_progresso) / 100, 1)
                                        antes_novo = antes_b64
                                        depois_novo = depois_b64
                                        if foto_up_card is not None:
                                            img_proc = processar_foto_miniatura(foto_up_card)
                                            if novo_progresso < 90 and not antes_b64:
                                                antes_novo = img_proc
                                            else:
                                                depois_novo = img_proc
                                        payload = {
                                            "colaborador": quem_move,
                                            "percentual": novo_progresso,
                                            "pontos": novos_pontos,
                                            "data_hora": obter_hora_brasilia(),
                                            "foto_base64": empacotar_fotos(antes_novo, depois_novo)
                                        }
                                        if atualizar_registro(reg_id, payload):
                                            st.success("✅ Cartão atualizado!")
                                            st.rerun()
                            with cb2:
                                if st.button("👀 Enviar p/ Aprovação", use_container_width=True, key=f"btn_apr_{reg_id}"):
                                    if pin_move not in [EQUIPE[quem_move], EQUIPE["Géslei (Agente Administrativo)"]]:
                                        st.error("❌ PIN incorreto.")
                                    else:
                                        depois_novo = processar_foto_miniatura(foto_up_card) if foto_up_card else depois_b64
                                        payload = {
                                            "colaborador": quem_move,
                                            "percentual": 90,
                                            "pontos": round(peso_tarefa * 0.9, 1),
                                            "data_hora": obter_hora_brasilia(),
                                            "foto_base64": empacotar_fotos(antes_b64, depois_novo)
                                        }
                                        if atualizar_registro(reg_id, payload):
                                            st.success("Enviado para aprovação!")
                                            st.rerun()

        with col_k1:
            st.markdown(f'<div class="kanban-col-header"><span>📋 A fazer</span><span class="kanban-badge">{len(df_afazer)}</span></div>', unsafe_allow_html=True)
            if df_afazer.empty:
                st.caption("Nenhum cartão pendente.")
            for _, row in df_afazer.iterrows():
                renderizar_cartao(row, "afazer")

        with col_k2:
            st.markdown(f'<div class="kanban-col-header" style="border-left-color:#FFAB00;"><span>⚙️ Em andamento</span><span class="kanban-badge">{len(df_andamento)}</span></div>', unsafe_allow_html=True)
            if df_andamento.empty:
                st.caption("Nenhum cartão em execução.")
            for _, row in df_andamento.iterrows():
                renderizar_cartao(row, "andamento")

        with col_k3:
            st.markdown(f'<div class="kanban-col-header" style="border-left-color:#6554C0;"><span>👀 Aguardando aprovação</span><span class="kanban-badge">{len(df_aprovacao)}</span></div>', unsafe_allow_html=True)
            if df_aprovacao.empty:
                st.caption("Nada aguardando validação.")
            for _, row in df_aprovacao.iterrows():
                renderizar_cartao(row, "aprovacao")

        with col_k4:
            st.markdown(f'<div class="kanban-col-header" style="border-left-color:#36B37E;"><span>✅ Concluídos</span><span class="kanban-badge">{len(df_concluido)}</span></div>', unsafe_allow_html=True)
            if df_concluido.empty:
                st.caption("Nenhum cartão concluído.")
            for _, row in df_concluido.iterrows():
                renderizar_cartao(row, "concluido")

with aba_direto:
    st.subheader("Lançar Atividade Já Realizada")
    colaborador = st.selectbox("Quem é você?", list(EQUIPE.keys()), key="dir_colab")
    pin_digitado = st.text_input("Seu PIN de 4 dígitos:", type="password", max_chars=4, placeholder="Ex: 1001", key="dir_pin")
    
    unidade = st.radio("Unidade:", ["Loja 1 (Balcão/Oficina)", "Loja 2 (Estoque)"], horizontal=True, key="dir_unid")
    tarefa_escolhida = st.selectbox("Tarefa realizada:", list(TAREFAS.keys()), key="dir_tarefa")
    
    tarefa_final = tarefa_escolhida
    if tarefa_escolhida == "Outra atividade (Descrever)":
        tarefa_final = st.text_input("Descreva a atividade realizada:", placeholder="Ex: Organização da vitrine de conexões", key="dir_desc")
        
    percentual = st.slider("Porcentagem concluída (avance conforme o progresso):", min_value=0, max_value=100, value=0, step=10, key="dir_perc")
    observacao = st.text_input("Observação (opcional):", placeholder="Ex: Prateleira B concluída / Retalhos 3/4 medidos", key="dir_obs")
    
    st.markdown("**Fotos da atividade (opcional - miniatura leve):**")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        foto_antes = st.file_uploader("📸 Foto ANTES", type=["jpg", "jpeg", "png"], key="foto_antes_reg")
        if foto_antes is not None:
            st.image(foto_antes, caption="Antes (miniatura)", width=150)
    with col_f2:
        foto_depois = st.file_uploader("✨ Foto DEPOIS", type=["jpg", "jpeg", "png"], key="foto_depois_reg")
        if foto_depois is not None:
            st.image(foto_depois, caption="Depois (miniatura)", width=150)
        
    peso_base = TAREFAS[tarefa_escolhida]
    pontos_calculados = round((peso_base * percentual) / 100, 1)
    st.info(f"Progresso: **{percentual}%** • Pontuação desta entrega: **{pontos_calculados} pts**")
    
    if st.button("Confirmar Lançamento", type="primary", use_container_width=True, key="dir_btn"):
        if pin_digitado != EQUIPE[colaborador]:
            st.error("❌ PIN incorreto! Verifique seu código de 4 dígitos.")
        elif percentual == 0:
            st.warning("⚠️ Avance a barra de porcentagem (mínimo 10%) para registrar o progresso da atividade.")
        elif not tarefa_final.strip():
            st.warning("⚠️ Por favor, descreva a atividade realizada.")
        else:
            with st.spinner("Salvando fotos e registro na nuvem..."):
                agora_br = obter_hora_brasilia()
                antes_b64 = processar_foto_miniatura(foto_antes)
                depois_b64 = processar_foto_miniatura(foto_depois)
                pacote_fotos = empacotar_fotos(antes_b64, depois_b64)
                
                etiqueta_unid = "Loja 1" if "Loja 1" in unidade else "Loja 2"
                obs_com_unidade = f"[{etiqueta_unid}] {observacao.strip()}".strip()
                
                novo_reg = {
                    "data_hora": agora_br,
                    "colaborador": colaborador,
                    "unidade": unidade,
                    "tarefa": tarefa_final.strip(),
                    "percentual": percentual,
                    "pontos": pontos_calculados,
                    "observacao": obs_com_unidade,
                    "foto_base64": pacote_fotos
                }
                if salvar_registro(novo_reg):
                    st.success(f"✅ Lançado às {agora_br}! +{pontos_calculados} pts ({percentual}%) para {colaborador.split(' (')[0]}.")
                    st.balloons()

with aba_indices:
    st.subheader("Ranking & Desempenho • GTT")
    df = carregar_dados()
    if df.empty:
        st.info("Ainda não há atividades registradas.")
    else:
        df_validos = df[df["pontos"] > 0]
        if df_validos.empty:
            st.info("Ainda não há pontos concluídos ou em andamento.")
        else:
            col1, col2 = st.columns(2)
            col1.metric("Total de Tarefas Pontuadas", len(df_validos))
            col2.metric("Pontos Acumulados", f"{df_validos['pontos'].sum():.1f} pts")
            
            ranking = df_validos.groupby("colaborador", as_index=False)["pontos"].sum().sort_values(by="pontos", ascending=False)
            ranking["Nome"] = ranking["colaborador"].apply(lambda x: x.split(" (")[0])
            
            fig = px.bar(ranking, x="pontos", y="Nome", orientation="h", text="pontos", color="pontos", color_continuous_scale="Blues")
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=350, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

with aba_historico:
    st.subheader("Tarefas Concluídas & Histórico Geral")
    if st.button("🔄 Atualizar Lista", key="btn_refresh_hist"):
        st.rerun()
        
    df = carregar_dados()
    if df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        df["progresso_%"] = df.apply(calcular_percentual_registro, axis=1)
        
        col_fh1, col_fh2 = st.columns(2)
        with col_fh1:
            filtro_status_hist = st.radio(
                "Exibir:",
                ["✅ Apenas Concluídos (100%)", "📋 Todos os Registros"],
                horizontal=True,
                key="filtro_hist_status"
            )
        with col_fh2:
            filtro_colab = st.selectbox("Filtrar por colaborador:", ["Todos", OPCAO_LIVRE] + list(EQUIPE.keys()))
            
        df_exibir = df.copy()
        if filtro_status_hist == "✅ Apenas Concluídos (100%)":
            df_exibir = df_exibir[df_exibir["progresso_%"] >= 100]
        if filtro_colab != "Todos":
            df_exibir = df_exibir[df_exibir["colaborador"] == filtro_colab]
        
        colunas_desejadas = ["data_hora", "colaborador", "tarefa", "progresso_%", "pontos", "observacao"]
        colunas_validas = [c for c in colunas_desejadas if c in df_exibir.columns]
        st.dataframe(df_exibir[colunas_validas], use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📸 Gerenciar Antes/Depois, Avanço ou Excluir")
        
        opcoes_reg = {
            f"#{row.get('id', idx)} | {row.get('data_hora', '')} - {str(row.get('colaborador', '')).split(' (')[0]} ({row.get('tarefa', '')} - {row.get('progresso_%', 0)}%)": row
            for idx, row in df_exibir.iterrows()
        }
        
        if opcoes_reg:
            selecionado_label = st.selectbox("Selecione o lançamento:", list(opcoes_reg.keys()))
            reg_atual = opcoes_reg[selecionado_label]
            reg_id = reg_atual.get("id")
            colab_dono = reg_atual.get("colaborador", "")
            tarefa_reg = reg_atual.get("tarefa", "")
            perc_atual = int(reg_atual.get("progresso_%", 0))
            antes_atual, depois_atual = extrair_fotos(reg_atual.get("foto_base64", ""))
            
            c_img1, c_img2 = st.columns(2)
            with c_img1:
                st.markdown("**📸 Antes**")
                if antes_atual.startswith("data:image"):
                    st.image(antes_atual, width=220)
                else:
                    st.caption("Sem foto de Antes.")
            with c_img2:
                st.markdown("**✨ Depois**")
                if depois_atual.startswith("data:image"):
                    st.image(depois_atual, width=220)
                else:
                    st.caption("Sem foto de Depois.")
            
            st.markdown("#### 🔧 Atualizar Registro")
            st.caption(f"Digite o PIN de **{str(colab_dono).split(' (')[0]}** ou o PIN do **Administrador (Géslei)** para confirmar:")
            pin_confirmacao = st.text_input("PIN de autorização:", type="password", max_chars=4, key=f"pin_ger_{reg_id}")
            
            novo_perc = st.slider(
                "Atualizar porcentagem concluída:",
                min_value=0,
                max_value=100,
                value=perc_atual,
                step=10,
                key=f"slider_hist_{reg_id}"
            )
            
            c_up1, c_up2 = st.columns(2)
            with c_up1:
                nova_antes = st.file_uploader("Trocar/Adicionar ANTES:", type=["jpg", "jpeg", "png"], key=f"up_antes_{reg_id}")
            with c_up2:
                nova_depois = st.file_uploader("Trocar/Adicionar DEPOIS:", type=["jpg", "jpeg", "png"], key=f"up_depois_{reg_id}")
            
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            
            with col_b1:
                if st.button("💾 Salvar Alterações", use_container_width=True, key=f"btn_save_{reg_id}"):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido.")
                    else:
                        antes_final = processar_foto_miniatura(nova_antes) if nova_antes else antes_atual
                        depois_final = processar_foto_miniatura(nova_depois) if nova_depois else depois_atual
                        peso = TAREFAS.get(tarefa_reg, 20)
                        novos_pts = round((peso * novo_perc) / 100, 1)
                        
                        payload = {
                            "foto_base64": empacotar_fotos(antes_final, depois_final),
                            "percentual": novo_perc,
                            "pontos": novos_pts
                        }
                        if atualizar_registro(reg_id, payload):
                            st.success("✅ Atualizado com sucesso!")
                            st.rerun()
            
            with col_b2:
                if st.button("🗑️ Excluir Antes", use_container_width=True, key=f"btn_del_a_{reg_id}"):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido.")
                    elif not antes_atual:
                        st.warning("⚠️ Não há foto de Antes.")
                    else:
                        if atualizar_registro(reg_id, {"foto_base64": empacotar_fotos("", depois_atual)}):
                            st.success("✅ Foto Antes removida!")
                            st.rerun()
                            
            with col_b3:
                if st.button("🗑️ Excluir Depois", use_container_width=True, key=f"btn_del_d_{reg_id}"):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido.")
                    elif not depois_atual:
                        st.warning("⚠️ Não há foto de Depois.")
                    else:
                        if atualizar_registro(reg_id, {"foto_base64": empacotar_fotos(antes_atual, "")}):
                            st.success("✅ Foto Depois removida!")
                            st.rerun()
            
            with col_b4:
                if st.button("❌ Apagar Registro", use_container_width=True, key=f"btn_del_all_{reg_id}"):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido.")
                    else:
                        if excluir_registro_completo(reg_id):
                            st.success("✅ Registro excluído!")
                            st.rerun()
