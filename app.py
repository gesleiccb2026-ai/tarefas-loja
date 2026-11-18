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

# Configuração da tela (otimizada para celular)
st.set_page_config(page_title="Tarefas & Organização", page_icon="📋", layout="centered")

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
    if "percentual" in row and pd.notna(row["percentual"]) and int(row["percentual"]) > 0:
        return int(row["percentual"])
    tarefa_nome = row.get("tarefa", "")
    pontos_reg = float(row.get("pontos", 0) or 0)
    peso_tarefa = TAREFAS.get(tarefa_nome, 20)
    if peso_tarefa > 0 and pontos_reg > 0:
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
        # Envia primeiro com todas as colunas; se alguma coluna opcional não existir na tabela, reenvia sem ela
        res = requests.post(TABELA_URL, json=registro, headers=HEADERS, timeout=10)
        if res.status_code in [200, 201]:
            return True
        # Fallback caso 'unidade' ou 'percentual' não existam no schema do Supabase
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
        # Fallback se 'percentual' não existir na tabela
        campos_enxutos = {k: v for k, v in campos_atualizados.items() if k != "percentual"}
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
st.title("📋 Organização & Tempo Ocioso")
st.caption("Controle de atividades • Loja 1 & Loja 2 (Estoque)")

aba1, aba2, aba3 = st.tabs(["✅ Registrar", "🏆 Índices", "📜 Histórico"])

# ================= ABA 1: REGISTRO =================
with aba1:
    st.subheader("Lançar Atividade")
    colaborador = st.selectbox("Quem é você?", list(EQUIPE.keys()))
    pin_digitado = st.text_input("Seu PIN de 4 dígitos:", type="password", max_chars=4, placeholder="Ex: 1001")
    
    unidade = st.radio("Unidade:", ["Loja 1 (Balcão/Oficina)", "Loja 2 (Estoque)"], horizontal=True)
    tarefa_escolhida = st.selectbox("Tarefa realizada:", list(TAREFAS.keys()))
    
    tarefa_final = tarefa_escolhida
    if tarefa_escolhida == "Outra atividade (Descrever)":
        tarefa_final = st.text_input("Descreva a atividade realizada:", placeholder="Ex: Organização da vitrine de conexões")
        
    percentual = st.slider("Porcentagem concluída (avance conforme o progresso):", min_value=0, max_value=100, value=0, step=10)
    observacao = st.text_input("Observação (opcional):", placeholder="Ex: Prateleira B concluída / Retalhos 3/4 medidos")
    
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
    
    if st.button("Confirmar Lançamento", type="primary", use_container_width=True):
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
                
                obs_com_unidade = f"[{unidade.split(' ')[0]} {unidade.split(' ')[1]}] {observacao.strip()}".strip()
                
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

# ================= ABA 2: ÍNDICES E RANKING =================
with aba2:
    st.subheader("Ranking & Desempenho")
    df = carregar_dados()
    if df.empty:
        st.info("Ainda não há atividades registradas.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Total de Tarefas", len(df))
        col2.metric("Pontos Acumulados", f"{df['pontos'].sum():.1f} pts")
        
        ranking = df.groupby("colaborador", as_index=False)["pontos"].sum().sort_values(by="pontos", ascending=False)
        ranking["Nome"] = ranking["colaborador"].apply(lambda x: x.split(" (")[0])
        
        fig = px.bar(ranking, x="pontos", y="Nome", orientation="h", text="pontos", color="pontos", color_continuous_scale="Reds")
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ================= ABA 3: HISTÓRICO E GESTÃO DE FOTOS / AVANÇO =================
with aba3:
    st.subheader("Histórico de Atividades")
    if st.button("🔄 Atualizar Lista", key="btn_refresh_hist"):
        st.rerun()
        
    df = carregar_dados()
    if df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        df["progresso_%"] = df.apply(calcular_percentual_registro, axis=1)
        
        filtro_colab = st.selectbox("Filtrar por colaborador:", ["Todos"] + list(EQUIPE.keys()))
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
            
            # Exibe Antes e Depois lado a lado em miniatura
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
            
            # Slider vinculado ao registro específico para mostrar a porcentagem atual real
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