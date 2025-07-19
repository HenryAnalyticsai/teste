import streamlit as st
import pandas as pd
import json
from PIL import Image
import os 
import locale 
from datetime import datetime 

# Definir o caminho absoluto do arquivo JSON
JSON_FILE_PATH = r"C:\Users\User\OneDrive\ENERGILETRICA\saida.json" 

# Configurar o locale para português do Brasil para formatação de números
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    st.warning("Não foi possível configurar o locale 'pt_BR.UTF-8'. A formatação de números pode não ser a esperada.")
    locale.setlocale(locale.LC_ALL, '') 

# Função para carregar os dados do JSON
@st.cache_data 
def load_data(json_file_path):
    """Carrega os dados de um arquivo JSON de um caminho específico."""
    if not os.path.exists(json_file_path):
        st.error(f"Erro: O arquivo '{json_file_path}' não foi encontrado. Verifique o caminho e a existência do arquivo.")
        return pd.DataFrame() 
        
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao carregar ou ler o arquivo JSON em '{json_file_path}': {e}")
        return pd.DataFrame()


# Função agregadora personalizada para priorizar status
def custom_status_agg(series):
    """
    Agrega uma série de status, priorizando a ordem: FINALIZADO > EM ANDAMENTO > EM ABERTO.
    Esta função é usada na pivotagem de LINHA_MONTAGEM.
    """
    status_order = ["FINALIZADO", "EM ANDAMENTO", "EM ABERTO"]
    
    unique_statuses = series.dropna().astype(str).str.upper().unique()
    
    for status in status_order:
        if status in unique_statuses:
            return status
    return None 

# Função para determinar o status geral de um projeto
def get_project_overall_status(row, status_cols):
    """
    Determina o status geral de um projeto com base nas suas fases, 
    priorizando FINALIZADO > EM ANDAMENTO > EM ABERTO.
    """
    project_phases_statuses = row[status_cols].dropna().astype(str).str.upper().tolist()
    
    if "FINALIZADO" in project_phases_statuses and all(s == "FINALIZADO" for s in project_phases_statuses):
        return "FINALIZADO"
    elif "EM ANDAMENTO" in project_phases_statuses:
        return "EM ANDAMENTO"
    elif "EM ABERTO" in project_phases_statuses and not any(s in ["EM ANDAMENTO", "FINALIZADO"] for s in project_phases_statuses):
        return "EM ABERTO"
    return "DESCONHECIDO" 

# Função para processar os dados e formatar para o dashboard
def process_data(df):
    """
    Processa o DataFrame para criar a estrutura de tabela desejada,
    com as linhas de montagem como colunas e os status como valores.
    """
    fases_montagem_ordem = ["CHAPARIA", "BARRAMENTO", "FIAÇÃO", "ACABAMENTO", "TESTE"]

    df_relevant = df[['ID_PROJETO', 'PROJETO', 'OBRA', 'PRAZO_DE_ENTREGA', 'LINHA_MONTAGEM', 'SITUACAO_PROJETO']].copy()

    # Converter 'PRAZO_DE_ENTREGA' para datetime ANTES da pivotagem
    df_relevant['PRAZO_DE_ENTREGA'] = pd.to_datetime(df_relevant['PRAZO_DE_ENTREGA'], errors='coerce')


    df_pivot = df_relevant.pivot_table(
        index=["ID_PROJETO", "PROJETO", "OBRA", "PRAZO_DE_ENTREGA"], 
        columns="LINHA_MONTAGEM",                     
        values="SITUACAO_PROJETO",                    
        aggfunc=custom_status_agg 
    ).reset_index()

    df_pivot.columns.name = None
    
    base_columns = ["PROJETO", "OBRA", "PRAZO_DE_ENTREGA"]
    ordered_columns = base_columns + [col for col in fases_montagem_ordem if col in df_pivot.columns]
    
    other_columns = [col for col in df_pivot.columns if col not in base_columns and col not in fases_montagem_ordem and col != 'ID_PROJETO']
    ordered_columns.extend(other_columns)

    final_columns = [col for col in ordered_columns if col in df_pivot.columns]
    
    # Ordenar o DataFrame pelo 'PRAZO_DE_ENTREGA' do mais recente para o mais antigo
    df_pivot = df_pivot[final_columns].sort_values(by='PRAZO_DE_ENTREGA', ascending=False)

    # Formatar 'PRAZO_DE_ENTREGA' para DD/MM/AAAA APÓS a ordenação
    df_pivot['PRAZO_DE_ENTREGA'] = df_pivot['PRAZO_DE_ENTREGA'].dt.strftime('%d/%m/%Y').fillna('')

    return df_pivot

# --- Função para Aplicar Estilo (Fundo e Texto) para CÉLULAS DA TABELA ---
def apply_status_colors_to_cells(cell_val):
    """
    Retorna a string de estilo CSS para a cor de fundo e a cor do texto
    baseada no valor do status para uma única célula.
    """
    if pd.isna(cell_val): 
        return ''
    
    status_val = str(cell_val).upper() 

    if status_val == "EM ABERTO":
        return 'background-color: #333333; color: white;' 
    elif status_val == "EM ANDAMENTO":
        return 'background-color: yellow; color: black;'    
    elif status_val == "FINALIZADO":
        return 'background-color: #90EE90; color: #006400;' 
    return '' 

# Funções para obter estilo de cor e fundo para os BIGNUMBERS
def get_bignumber_bg_color(status_name):
    """Retorna a cor de fundo para o bignumber."""
    status_name = str(status_name).upper()
    if status_name == "EM ABERTO":
        return '#444444' 
    elif status_name == "EM ANDAMENTO":
        return '#FFFFCC' 
    elif status_name == "FINALIZADO":
        return '#C8E6C9' 
    return '#E0E0E0' 

def get_bignumber_text_color(status_name):
    """Retorna a cor do texto para o bignumber para contraste."""
    status_name = str(status_name).upper()
    if status_name == "EM ABERTO":
        return 'white' 
    elif status_name == "EM ANDAMENTO":
        return 'black'    
    elif status_name == "FINALIZADO":
        return '#006400' 
    return 'black' 


# Configurações da página do Streamlit
st.set_page_config(layout="wide", page_title="Dashboard Operacional", page_icon="📊")

st.title("ENERGILÉTRICA | DASHBOARD OPERACIONAL")

# --- NOVO: Informação de data e hora da última modificação do JSON (AGORA POSICIONADA AQUI) ---
if os.path.exists(JSON_FILE_PATH):
    try:
        mod_timestamp = os.path.getmtime(JSON_FILE_PATH)
        mod_datetime = datetime.fromtimestamp(mod_timestamp)
        formatted_mod_time = mod_datetime.strftime("%d/%m/%Y às %H:%M:%S")
        # Usando st.info para o formato inicial
        st.info(f"Última atualização da base de dados {formatted_mod_time}")
    except Exception as e:
        st.warning(f"Não foi possível obter a data de modificação do arquivo JSON: {e}")
else:
    st.warning("Caminho do arquivo JSON não encontrado para verificar a data de modificação.")

st.markdown("---") # Linha divisória após o título e informação de data/hora


# Carregar os dados
try:
    df_raw = load_data(JSON_FILE_PATH) 
    
    if df_raw.empty:
        st.stop() 

    df_dashboard = process_data(df_raw.copy()) 
    
    # --- Cálculo dos BIGNUMBERS ---
    status_cols_for_overall = ["CHAPARIA", "BARRAMENTO", "FIAÇÃO", "ACABAMENTO", "TESTE"]

    df_dashboard['STATUS_GERAL_PROJETO'] = df_dashboard.apply(
        lambda row: get_project_overall_status(row, status_cols_for_overall), axis=1
    )

    total_projetos = df_dashboard['PROJETO'].nunique()
    projetos_em_aberto = df_dashboard[df_dashboard['STATUS_GERAL_PROJETO'] == 'EM ABERTO']['PROJETO'].nunique()
    projetos_em_andamento = df_dashboard[df_dashboard['STATUS_GERAL_PROJETO'] == 'EM ANDAMENTO']['PROJETO'].nunique()
    projetos_finalizados = df_dashboard[df_dashboard['STATUS_GERAL_PROJETO'] == 'FINALIZADO']['PROJETO'].nunique()

    # --- Exibição dos BIGNUMBERS com Realce de Fundo e Formatação ---
    st.subheader("Resumo dos Projetos")

    col1, col2, col3, col4 = st.columns(4)

    # Função auxiliar para renderizar a caixa do bignumber
    def render_bignumber_box(count, label, status_type=None):
        bg_color = get_bignumber_bg_color(status_type) if status_type else get_bignumber_bg_color("TOTAL")
        text_color = get_bignumber_text_color(status_type) if status_type else get_bignumber_text_color("TOTAL")
        
        # Formata o número com separador de milhares em PT-BR
        formatted_count = locale.format_string("%d", count, grouping=True)

        st.markdown(f"""
            <div style="
                background-color: {bg_color};
                padding: 10px;
                border-radius: 8px;
                text-align: center;
                margin-bottom: 10px;
            ">
                <div style="font-size: 2.5em; font-weight: bold; color: {text_color};">{formatted_count}</div>
                <div style="font-size: 1.2em; color: {text_color};">{label}</div>
            </div>
        """, unsafe_allow_html=True)

    with col1:
        render_bignumber_box(total_projetos, "Projetos Totais", "TOTAL")
    with col2:
        render_bignumber_box(projetos_em_aberto, "Em Aberto", "EM ABERTO")
    with col3:
        render_bignumber_box(projetos_em_andamento, "Em Andamento", "EM ANDAMENTO")
    with col4:
        render_bignumber_box(projetos_finalizados, "Finalizados", "FINALIZADO")
    
    st.markdown("---") 


    # --- Colunas onde o estilo será aplicado ---
    status_cols_to_style = ["CHAPARIA", "BARRAMENTO", "FIAÇÃO", "ACABAMENTO", "TESTE"]

    # --- Aplicar o estilo ao DataFrame usando Pandas Styler ---
    styled_df_pandas = df_dashboard.copy().style.applymap(apply_status_colors_to_cells, subset=status_cols_to_style)
    
    st.subheader("Visão Geral dos Projetos e Fases de Montagem")
    
    st.dataframe(
        styled_df_pandas, 
        use_container_width=True, 
        hide_index=True, 
        column_config={ 
            "PROJETO": st.column_config.TextColumn("PROJETO", help="Número/código do projeto"),
            "OBRA": st.column_config.TextColumn("OBRA", help="Nome da obra associada ao projeto"),
            "PRAZO_DE_ENTREGA": st.column_config.TextColumn("PRAZO DE ENTREGA", help="Data limite para entrega do projeto (DD/MM/AAAA)"),
            "CHAPARIA": st.column_config.TextColumn("CHAPARIA", help="Status da fase de Chaparia"),
            "BARRAMENTO": st.column_config.TextColumn("BARRAMENTO", help="Status da fase de Barramento"),
            "FIAÇÃO": st.column_config.TextColumn("FIAÇÃO", help="Status da fase de Fiação"),
            "ACABAMENTO": st.column_config.TextColumn("ACABAMENTO", help="Status da fase de Acabamento"), 
            "TESTE": st.column_config.TextColumn("TESTE", help="Status da fase de Teste"), 
            "STATUS_GERAL_PROJETO": None 
        }
    )

    st.markdown("---") 

except Exception as e:
    st.error(f"Ocorreu um erro geral no aplicativo: {e}")

# Rodapé
st.markdown("<div style='text-align: center; font-size: 0.9em; color: gray;'>Desenvolvido por Henry Analytics AI - v.1.0</div>", unsafe_allow_html=True)