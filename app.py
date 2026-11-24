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

# Configuração da tela (layout amplo no PC para ver as 3 colunas do Trello e responsivo no celular)
st.set_page_config(page_title="Tarefas SAN • Quadro Trello", page_icon="🗂️", layout="wide")

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
        img.thumbnail((450, 450))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=60)
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

# --- TÍTULO E ABAS ---
st.title("🗂️ Controle de Serviços & Tempo Ocioso")
st.caption("Quadro estilo Trello • Loja 1 (Balcão/Oficina) & Loja 2 (Estoque)")

aba_trello, aba_direto, aba_indices, aba_historico = st.tabs([
    "🗂️ Quadro Trello",
    "✅ Lançar Direto",
    "🏆 Índices",
    "📜 Histórico"
])

# ================= ABA 1: QUADRO KANBAN ESTILO TRELLO =================
with aba_trello:
    # Barra superior de criação rápida de cartão + filtros
    with st.expander("➕ Criar Novo Cartão de Serviço (A Fazer)", expanded=False):
        c_new1, c_new2, c_new3 = st.columns(3)
        with c_new1:
            criador_card = st.selectbox("Quem está criando?", list(EQUIPE.keys()), key="trello_criador")
            pin_criador = st.text_input("PIN de confirmação:", type="password", max_chars=4, key="trello_pin_criador")
        with c_new2:
            responsavel_card = st.selectbox("Atribuir para:", [OPCAO_LIVRE] + list(EQUIPE.keys()), key="trello_resp")
            unidade_card = st.radio("Unidade:", ["Loja 1 (Balcão/Oficina)", "Loja 2 (Estoque)"], horizontal=True, key="trello_unid")
        with c_new3:
            tarefa_card = st.selectbox("Serviço / Tarefa:", list(TAREFAS.keys()), key="trello_tarefa")
            tarefa_card_final = tarefa_card
            if tarefa_card == "Outra atividade (Descrever)":
                tarefa_card_final = st.text_input("Descreva o serviço:", placeholder="Ex: Organizar gôndola de conexões", key="trello_tarefa_desc")
        
        obs_card = st.text_input("Detalhes / Instruções do cartão (opcional):", placeholder="Ex: Prioridade para hoje à tarde", key="trello_obs")
        foto_inicial_card = st.file_uploader("📸 Foto ANTES opcional (já anexar na abertura do cartão):", type=["jpg", "jpeg", "png"], key="trello_foto_init")
        
        if st.button("📌 Adicionar Cartão no Quadro", type="primary", use_container_width=True):
            if pin_criador != EQUIPE[criador_card]:
                st.error("❌ PIN incorreto! Digite o PIN de quem está criando o cartão.")
            elif not tarefa_card_final.strip():
                st.warning("⚠️ Descreva o serviço antes de adicionar o cartão.")
            else:
                with st.spinner("Criando cartão no quadro..."):
                    agora_br = obter_hora_brasilia()
                    antes_b64 = processar_foto_miniatura(foto_inicial_card)
                    pacote_fotos = empacotar_fotos(antes_b64, "")
                    etiqueta_unid = "Loja 1" if "Loja 1" in unidade_card else "Loja 2"
                    obs_formatada = f"[{etiqueta_unid}] {obs_card.strip()}".strip()
                    
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
                        st.success("✅ Cartão adicionado na coluna '📋 A Fazer'!")
                        st.rerun()

    # Filtros do Quadro
    col_f_tr1, col_f_tr2, col_f_tr3 = st.columns([2, 2, 1])
    with col_f_tr1:
        filtro_resp_trello = st.selectbox("Filtrar por Responsável:", ["Todos", OPCAO_LIVRE] + list(EQUIPE.keys()), key="filtro_trello_resp")
    with col_f_tr2:
        filtro_loja_trello = st.selectbox("Filtrar por Unidade:", ["Todas", "Loja 1", "Loja 2"], key="filtro_trello_loja")
    with col_f_tr3:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar Quadro", use_container_width=True):
            st.rerun()

    df_trello = carregar_dados()
    if df_trello.empty:
        st.info("Nenhum cartão encontrado no quadro. Clique em '➕ Criar Novo Cartão de Serviço' acima para começar!")
    else:
        df_trello["progresso_%"] = df_trello.apply(calcular_percentual_registro, axis=1)
        
        if filtro_resp_trello != "Todos":
            df_trello = df_trello[df_trello["colaborador"] == filtro_resp_trello]
        if filtro_loja_trello != "Todas":
            df_trello = df_trello[df_trello["observacao"].astype(str).str.contains(filtro_loja_trello, na=False)]

        df_afazer = df_trello[df_trello["progresso_%"] == 0]
        df_andamento = df_trello[(df_trello["progresso_%"] > 0) & (df_trello["progresso_%"] < 100)]
        df_concluido = df_trello[df_trello["progresso_%"] >= 100].head(15)  # Mostra os 15 últimos concluídos para manter o quadro leve

        col_k1, col_k2, col_k3 = st.columns(3)

        # Função auxiliar para desenhar cada cartão estilo Trello
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

            # Etiqueta visual de loja
            badge_loja = "🔵 Loja 1" if "[Loja 1]" in obs_txt else ("🟠 Loja 2" if "[Loja 2]" in obs_txt else "⚪ Geral")
            obs_limpa = obs_txt.replace("[Loja 1]", "").replace("[Loja 2]", "").strip()

            with st.container(border=True):
                st.markdown(f"**{tarefa_txt}**")
                st.caption(f"{badge_loja} • 🏆 {peso_tarefa} pts • 🕒 {data_txt}")
                
                if colab_atual == OPCAO_LIVRE:
                    st.warning(f"👤 {OPCAO_LIVRE}")
                else:
                    st.markdown(f"👤 **{nome_curto}** • Progresso: **{perc}%** ({pts_atuais} pts)")
                
                if obs_limpa:
                    st.caption(f"📝 {obs_limpa}")

                # Miniaturas Antes / Depois dentro do cartão
                if antes_b64.startswith("data:image") or depois_b64.startswith("data:image"):
                    c_m1, c_m2 = st.columns(2)
                    with c_m1:
                        if antes_b64.startswith("data:image"):
                            st.image(antes_b64, caption="Antes", width=110)
                    with c_m2:
                        if depois_b64.startswith("data:image"):
                            st.image(depois_b64, caption="Depois", width=110)

                # Ações rápidas do cartão conforme a coluna
                if estagio in ["afazer", "andamento"]:
                    with st.expander("⚡ Mover / Atualizar Cartão"):
                        quem_move = st.selectbox(
                            "Colaborador:",
                            list(EQUIPE.keys()),
                            index=list(EQUIPE.keys()).index(colab_atual) if colab_atual in EQUIPE else 0,
                            key=f"sel_colab_{reg_id}"
                        )
                        pin_move = st.text_input("PIN (4 dígitos):", type="password", max_chars=4, key=f"pin_move_{reg_id}")
                        
                        valor_sugerido = 20 if estagio == "afazer" else min(100, perc + 20)
                        novo_progresso = st.slider(
                            "Novo progresso (%):",
                            min_value=10,
                            max_value=100,
                            value=valor_sugerido,
                            step=10,
                            key=f"prog_move_{reg_id}"
                        )
                        
                        foto_up_card = st.file_uploader(
                            "📸 Anexar Foto (Antes se iniciando / Depois se concluindo):",
                            type=["jpg", "jpeg", "png"],
                            key=f"foto_move_{reg_id}"
                        )
                        
                        col_btn_m1, col_btn_m2 = st.columns(2)
                        with col_btn_m1:
                            if st.button("💾 Salvar & Mover", type="primary", use_container_width=True, key=f"btn_move_{reg_id}"):
                                if pin_move not in [EQUIPE[quem_move], EQUIPE["Géslei (Agente Administrativo)"]]:
                                    st.error("❌ PIN incorreto.")
                                else:
                                    novos_pontos = round((peso_tarefa * novo_progresso) / 100, 1)
                                    antes_novo = antes_b64
                                    depois_novo = depois_b64
                                    
                                    if foto_up_card is not None:
                                        img_proc = processar_foto_miniatura(foto_up_card)
                                        if novo_progresso < 100 and not antes_b64:
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
                        with col_btn_m2:
                            if st.button("✅ Concluir 100%", use_container_width=True, key=f"btn_done_{reg_id}"):
                                if pin_move not in [EQUIPE[quem_move], EQUIPE["Géslei (Agente Administrativo)"]]:
                                    st.error("❌ PIN incorreto.")
                                else:
                                    depois_novo = processar_foto_miniatura(foto_up_card) if foto_up_card else depois_b64
                                    payload = {
                                        "colaborador": quem_move,
                                        "percentual": 100,
                                        "pontos": float(peso_tarefa),
                                        "data_hora": obter_hora_brasilia(),
                                        "foto_base64": empacotar_fotos(antes_b64, depois_novo)
                                    }
                                    if atualizar_registro(reg_id, payload):
                                        st.success("🎉 Concluído!")
                                        st.rerun()

        # Coluna 1: A FAZER
        with col_k1:
            st.subheader(f"📋 A Fazer ({len(df_afazer)})")
            if df_afazer.empty:
                st.caption("Nenhum serviço pendente.")
            for _, row in df_afazer.iterrows():
                renderizar_cartao(row, "afazer")

        # Coluna 2: EM ANDAMENTO
        with col_k2:
            st.subheader(f"⚙️ Em Andamento ({len(df_andamento)})")
            if df_andamento.empty:
                st.caption("Nenhum serviço em execução.")
            for _, row in df_andamento.iterrows():
                renderizar_cartao(row, "andamento")

        # Coluna 3: CONCLUÍDO
        with col_k3:
            st.subheader(f"✅ Concluído ({len(df_concluido)})")
            if df_concluido.empty:
                st.caption("Nenhum serviço concluído ainda.")
            for _, row in df_concluido.iterrows():
                renderizar_cartao(row, "concluido")

# ================= ABA 2: LANÇAMENTO DIRETO =================
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

# ================= ABA 3: ÍNDICES E RANKING =================
with aba_indices:
    st.subheader("Ranking & Desempenho")
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
            
            fig = px.bar(ranking, x="pontos", y="Nome", orientation="h", text="pontos", color="pontos", color_continuous_scale="Reds")
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=350, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

# ================= ABA 4: HISTÓRICO E GESTÃO DE FOTOS =================
with aba_historico:
    st.subheader("Histórico Geral & Gestão de Fotos")
    if st.button("🔄 Atualizar Lista", key="btn_refresh_hist"):
        st.rerun()
        
    df = carregar_dados()
    if df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        df["progresso_%"] = df.apply(calcular_percentual_registro, axis=1)
        
        filtro_colab = st.selectbox("Filtrar por colaborador:", ["Todos", OPCAO_LIVRE] + list(EQUIPE.keys()))
        df_exibir = df if filtro_colab == "Todos" else df[df["colaborador"] == filtro_colab]
        
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