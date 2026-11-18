import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import base64
from PIL import Image
import io
from datetime import datetime, timedelta

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
    "Prefer": "return=minimal"
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

# --- FUNÇÃO PARA COMPRIMIR E PREPARAR FOTO ---
def processar_foto(foto_enviada):
    if foto_enviada is None:
        return ""
    img = Image.open(foto_enviada)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail((800, 800))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_base64}"

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
    return pd.DataFrame(columns=["id", "data_hora", "colaborador", "unidade", "tarefa", "percentual", "pontos", "observacao", "foto_base64"])

def salvar_registro(registro):
    try:
        res = requests.post(TABELA_URL, json=registro, headers=HEADERS, timeout=10)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"Erro ao salvar registro: {e}")
        return False

def atualizar_foto_registro(registro_id, nova_foto_base64):
    try:
        res = requests.patch(f"{TABELA_URL}?id=eq.{registro_id}", json={"foto_base64": nova_foto_base64}, headers=HEADERS, timeout=10)
        return res.status_code in [200, 204]
    except Exception as e:
        st.error(f"Erro ao atualizar foto: {e}")
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
        
    percentual = st.slider("Porcentagem concluída:", min_value=10, max_value=100, value=100, step=10)
    observacao = st.text_input("Observação (opcional):", placeholder="Ex: Prateleira B concluída / Retalhos 3/4 medidos")
    foto = st.file_uploader("Foto da atividade (opcional - abre câmera no celular):", type=["jpg", "jpeg", "png"])
    
    if foto is not None:
        st.image(foto, caption="Prévia da foto anexada", width=250)
        
    peso_base = TAREFAS[tarefa_escolhida]
    pontos_calculados = round((peso_base * percentual) / 100, 1)
    st.info(f"Pontuação desta entrega: **{pontos_calculados} pts**")
    
    if st.button("Confirmar Lançamento", type="primary", use_container_width=True):
        if pin_digitado != EQUIPE[colaborador]:
            st.error("❌ PIN incorreto! Verifique seu código de 4 dígitos.")
        elif not tarefa_final.strip():
            st.warning("⚠️ Por favor, descreva a atividade realizada.")
        else:
            with st.spinner("Salvando na nuvem..."):
                agora_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
                foto_b64 = processar_foto(foto)
                novo_reg = {
                    "data_hora": agora_br,
                    "colaborador": colaborador,
                    "unidade": unidade,
                    "tarefa": tarefa_final.strip(),
                    "percentual": percentual,
                    "pontos": pontos_calculados,
                    "observacao": observacao.strip(),
                    "foto_base64": foto_b64
                }
                if salvar_registro(novo_reg):
                    st.success(f"✅ Lançado com sucesso! +{pontos_calculados} pts para {colaborador.split(' (')[0]}.")
                    st.balloons()
                else:
                    st.error("Falha ao salvar. Tente novamente.")

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

# ================= ABA 3: HISTÓRICO E GESTÃO DE FOTOS =================
with aba3:
    st.subheader("Histórico de Atividades")
    df = carregar_dados()
    if df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        filtro_colab = st.selectbox("Filtrar por colaborador:", ["Todos"] + list(EQUIPE.keys()))
        df_exibir = df if filtro_colab == "Todos" else df[df["colaborador"] == filtro_colab]
        
        # Filtra apenas as colunas que realmente existem no DataFrame (evita KeyError)
        colunas_desejadas = ["data_hora", "colaborador", "unidade", "tarefa", "percentual", "pontos", "observacao"]
        colunas_validas = [c for c in colunas_desejadas if c in df_exibir.columns]
        st.dataframe(df_exibir[colunas_validas], use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📸 Gerenciar Foto / Registro")
        
        opcoes_reg = {
            f"#{row.get('id', idx)} | {row.get('data_hora', '')} - {str(row.get('colaborador', '')).split(' (')[0]} ({row.get('tarefa', '')})": row
            for idx, row in df_exibir.iterrows()
        }
        
        if opcoes_reg:
            selecionado_label = st.selectbox("Selecione o lançamento:", list(opcoes_reg.keys()))
            reg_atual = opcoes_reg[selecionado_label]
            reg_id = reg_atual.get("id")
            colab_dono = reg_atual.get("colaborador", "")
            foto_existente = reg_atual.get("foto_base64", "")
            
            # Exibe a foto atual se existir
            if isinstance(foto_existente, str) and foto_existente.startswith("data:image"):
                st.image(foto_existente, caption="Foto anexada atualmente", use_container_width=True)
            else:
                st.info("Este lançamento ainda não possui foto anexada.")
            
            st.markdown("#### 🔧 Alterar Foto ou Excluir")
            st.caption(f"Digite o PIN de **{str(colab_dono).split(' (')[0]}** ou o PIN do **Administrador (Géslei)** para confirmar:")
            pin_confirmacao = st.text_input("PIN de autorização:", type="password", max_chars=4, key="pin_gerenciar")
            
            nova_foto_upload = st.file_uploader("Enviar nova foto (substitui a atual ou adiciona foto depois de organizado):", type=["jpg", "jpeg", "png"], key="nova_foto_hist")
            
            col_b1, col_b2, col_b3 = st.columns(3)
            
            # Botão 1: Salvar / Substituir Foto
            with col_b1:
                if st.button("💾 Salvar Nova Foto", use_container_width=True):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido para alterar este registro.")
                    elif nova_foto_upload is None:
                        st.warning("⚠️ Selecione ou tire uma foto primeiro acima.")
                    else:
                        nova_b64 = processar_foto(nova_foto_upload)
                        if atualizar_foto_registro(reg_id, nova_b64):
                            st.success("✅ Foto atualizada com sucesso!")
                            st.rerun()
            
            # Botão 2: Excluir Apenas a Foto
            with col_b2:
                if st.button("🖼️ Excluir Só a Foto", use_container_width=True):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido para excluir a foto.")
                    elif not (isinstance(foto_existente, str) and foto_existente.startswith("data:image")):
                        st.warning("⚠️ Este registro não tem foto para excluir.")
                    else:
                        if atualizar_foto_registro(reg_id, ""):
                            st.success("✅ Foto removida! A tarefa e os pontos foram mantidos.")
                            st.rerun()
            
            # Botão 3: Excluir Registro Inteiro
            with col_b3:
                if st.button("🗑️ Excluir Registro", use_container_width=True):
                    if pin_confirmacao not in [EQUIPE.get(colab_dono), EQUIPE["Géslei (Agente Administrativo)"]]:
                        st.error("❌ PIN inválido para excluir este registro.")
                    else:
                        if excluir_registro_completo(reg_id):
                            st.success("✅ Registro excluído completamente!")
                            st.rerun()