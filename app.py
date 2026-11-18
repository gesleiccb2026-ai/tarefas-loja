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
    "Limpeza e organização da oficina/balcão": 20,
    "Medir e identificar retalhos de mangueiras": 15,
    "Avaliar itens de estoque baixo": 15
}

PESOS_PERSONALIZADOS = {
    "Tarefa Rápida / Simples (15 pts)": 15,
    "Tarefa Média / Rotina (25 pts)": 25,
    "Tarefa Pesada / Demorada (50 pts)": 50
}

# --- FUNÇÃO PARA COMPRIMIR E CONVERTER FOTO ---
def processar_foto(arquivo_foto):
    if arquivo_foto is None:
        return "Não"
    try:
        img = Image.open(arquivo_foto)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((600, 600))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=65)
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_str}"
    except Exception:
        return "Anexada"

# --- FUNÇÕES DE DADOS NA NUVEM ---
def carregar_dados():
    try:
        resp = requests.get(f"{TABELA_URL}?select=*&order=id.asc", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            dados = resp.json()
            if dados:
                df = pd.DataFrame(dados)
                df = df.rename(columns={
                    "data_hora": "Data",
                    "data_iso": "Data_ISO",
                    "colaborador": "Colaborador",
                    "loja": "Loja",
                    "tarefa": "Tarefa",
                    "progresso": "Conclusao (%)",
                    "pontos": "Pontos",
                    "obs": "Obs",
                    "foto": "Foto"
                })
                return df
    except Exception as e:
        st.error(f"Erro ao conectar com o banco: {e}")
    return pd.DataFrame(columns=[
        "id", "Data", "Data_ISO", "Colaborador", "Loja", "Tarefa", 
        "Conclusao (%)", "Pontos", "Obs", "Foto"
    ])

def salvar_dados(registro):
    try:
        resp = requests.post(TABELA_URL, json=registro, headers=HEADERS, timeout=15)
        return resp.status_code in [200, 201]
    except Exception as e:
        st.error(f"Erro ao salvar na nuvem: {e}")
        return False

# --- INTERFACE DO APP ---
st.title("📋 Organização & Tempo Ocioso")
st.caption("Controle de atividades • Loja 1 & Loja 2 (Estoque)")

aba1, aba2, aba3 = st.tabs(["✅ Registrar", "🏆 Índices", "📜 Histórico"])

# ABA 1: REGISTRO DE TAREFA
with aba1:
    st.subheader("Lançar Atividade")
    
    colab = st.selectbox("Quem é você?", list(EQUIPE.keys()))
    pin_digitado = st.text_input("Seu PIN de 4 dígitos:", type="password", max_chars=4, placeholder="Ex: 1001")
    
    loja = st.radio("Unidade:", ["Loja 1 (Balcão/Oficina)", "Loja 2 (Estoque)"], horizontal=True)
    
    opcoes_tarefas = list(TAREFAS.keys()) + ["➕ Outra tarefa (digitar nova)"]
    tarefa_selecionada = st.selectbox("Tarefa realizada:", opcoes_tarefas)
    
    if tarefa_selecionada == "➕ Outra tarefa (digitar nova)":
        tarefa_final = st.text_input("Descreva a nova tarefa:", placeholder="Ex: Conferir chegada de mercadoria / Organizar conexões")
        nivel_peso = st.selectbox("Grau de esforço / pontuação:", list(PESOS_PERSONALIZADOS.keys()))
        peso_base = PESOS_PERSONALIZADOS[nivel_peso]
    else:
        tarefa_final = tarefa_selecionada
        peso_base = TAREFAS[tarefa_selecionada]
    
    progresso = st.slider("Porcentagem concluída:", min_value=10, max_value=100, value=100, step=10)
    obs = st.text_input("Observação (opcional):", placeholder="Ex: Prateleira B concluída / Retalhos 3/4 medidos")
    
    foto = st.file_uploader("Foto da atividade (opcional - abre câmera no celular):", type=["jpg", "jpeg", "png"])
    
    # Pré-visualização imediata da foto selecionada
    if foto is not None:
        st.image(foto, caption="Prévia da foto anexada", width=250)
    
    pontos = round((progresso / 100) * peso_base, 1)
    st.info(f"Pontuação desta entrega: **{pontos} pts**")
    
    if st.button("Confirmar Lançamento", type="primary", use_container_width=True):
        if pin_digitado != EQUIPE[colab]:
            st.error("❌ PIN incorreto! Digite o seu código de 4 dígitos para confirmar.")
        elif not tarefa_final or not tarefa_final.strip():
            st.error("❌ Por favor, digite o nome da nova tarefa antes de confirmar.")
        else:
            agora = datetime.now()
            foto_codificada = processar_foto(foto)
            novo = {
                "data_hora": agora.strftime("%d/%m/%Y %H:%M"),
                "data_iso": agora.strftime("%Y-%m-%d"),
                "colaborador": colab,
                "loja": loja,
                "tarefa": tarefa_final.strip(),
                "progresso": float(progresso),
                "pontos": float(pontos),
                "obs": obs,
                "foto": foto_codificada
            }
            if salvar_dados(novo):
                st.success(f"✅ Salvo na nuvem para {colab.split()[0]}! (+{pontos} pts)")
                st.rerun()
            else:
                st.error("⚠️ Não foi possível salvar. Verifique a conexão com a internet.")

# ABA 2: PAINEL DE ÍNDICES E RANKING
with aba2:
    st.subheader("Índices de Desempenho")
    df = carregar_dados()
    
    if df.empty:
        st.info("Ainda não há registros na nuvem. Faça um lançamento na aba 'Registrar'!")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            periodo = st.selectbox("Período:", ["Todo o Período", "Esta Semana (7 dias)", "Este Mês (30 dias)"])
        with col_f2:
            filtro_loja = st.selectbox("Unidade:", ["Todas as Lojas", "Loja 1 (Balcão/Oficina)", "Loja 2 (Estoque)"])
        
        df_filtrado = df.copy()
        hoje = datetime.now().date()
        
        if "Data_ISO" in df_filtrado.columns:
            df_filtrado["Data_dt"] = pd.to_datetime(df_filtrado["Data_ISO"], errors="coerce").dt.date
            if periodo == "Esta Semana (7 dias)":
                df_filtrado = df_filtrado[df_filtrado["Data_dt"] >= (hoje - timedelta(days=7))]
            elif periodo == "Este Mês (30 dias)":
                df_filtrado = df_filtrado[df_filtrado["Data_dt"] >= (hoje - timedelta(days=30))]
                
        if filtro_loja != "Todas as Lojas":
            df_filtrado = df_filtrado[df_filtrado["Loja"] == filtro_loja]
            
        if df_filtrado.empty:
            st.warning("Nenhum registro encontrado para este filtro.")
        else:
            resumo = df_filtrado.groupby("Colaborador").agg(
                Pontos=("Pontos", "sum"),
                Tarefas=("Tarefa", "count"),
                Media_Conclusao=("Conclusao (%)", "mean")
            ).reset_index().sort_values(by="Pontos", ascending=False)
            
            total_pts = resumo["Pontos"].sum()
            resumo["Índice (%)"] = round((resumo["Pontos"] / total_pts) * 100, 1)
            resumo["Media_Conclusao"] = round(resumo["Media_Conclusao"], 0).astype(int)
            
            fig = px.bar(
                resumo, x="Pontos", y="Colaborador", orientation="h",
                text="Índice (%)", color="Pontos", color_continuous_scale="Blues",
                title=f"Participação ({periodo})"
            )
            fig.update_traces(texttemplate='%{text}%', textposition='outside')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False, height=420)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(
                resumo[["Colaborador", "Índice (%)", "Pontos", "Tarefas", "Media_Conclusao"]],
                use_container_width=True, hide_index=True
            )

# ABA 3: HISTÓRICO RECENTE E VISUALIZADOR DE FOTOS
with aba3:
    st.subheader("Histórico de Atividades")
    df = carregar_dados()
    if not df.empty:
        df_exibir = df.iloc[::-1].copy()
        df_exibir["Status Foto"] = df_exibir["Foto"].apply(
            lambda x: "📷 Ver foto abaixo" if isinstance(x, str) and x.startswith("data:image") else ("Anexada" if x == "Anexada" else "Sem foto")
        )
        colunas_exibir = [c for c in ["Data", "Colaborador", "Loja", "Tarefa", "Conclusao (%)", "Pontos", "Obs", "Status Foto"] if c in df_exibir.columns]
        st.dataframe(df_exibir[colunas_exibir], use_container_width=True, hide_index=True)

        # Visualizador de fotos salvas
        registros_com_foto = df_exibir[df_exibir["Foto"].astype(str).str.startswith("data:image")]
        if not registros_com_foto.empty:
            st.markdown("---")
            st.subheader("📷 Visualizar Foto Anexada")
            opcoes_foto = {
                f"{row['Data']} - {row['Colaborador'].split()[0]} ({row['Tarefa']})": row["Foto"]
                for _, row in registros_com_foto.iterrows()
            }
            selecao_foto = st.selectbox("Selecione o registro para abrir a imagem:", list(opcoes_foto.keys()))
            st.image(opcoes_foto[selecao_foto], use_container_width=True)