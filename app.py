import streamlit as st
import pandas as pd
from datetime import datetime
import io
from complaint_processor import ComplaintProcessor
from data_validator import DataValidator
from utils import format_date, export_to_excel

def main():
    st.set_page_config(
        page_title="Análise de Reclamações - SLA Tracker",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Sistema de Análise de Reclamações")
    st.markdown("**Automatize a análise de SLA e gestão de prazos de relatórios de reclamações**")
    
    # Initialize session state
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
    if 'metrics' not in st.session_state:
        st.session_state.metrics = None
    if 'column_mapping' not in st.session_state:
        st.session_state.column_mapping = {}
    if 'mapping_confirmed' not in st.session_state:
        st.session_state.mapping_confirmed = False
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False

    # Sidebar for file upload and configuration
    with st.sidebar:
        st.header("📁 Upload de Arquivos")
        uploaded_files = st.file_uploader(
            "Selecione os arquivos de relatório",
            accept_multiple_files=True,
            type=['xlsx', 'xls', 'csv', 'ods'],
            help="Formatos suportados: Excel (.xlsx, .xls), CSV (.csv), OpenDocument (.ods)"
        )
        
        header_row = 1
        if uploaded_files:
            st.success(f"{len(uploaded_files)} arquivo(s) selecionado(s)")
            
            # Header row configuration
            st.subheader("⚙️ Configuração")
            header_row = st.number_input(
                "Linha do cabeçalho (1-based)",
                min_value=1,
                value=1,
                help="Especifique em qual linha estão os nomes das colunas"
            )
            
            # Button to start or reset processing
            if st.session_state.processed_data is None:
                if st.button("🔄 Processar Arquivos", type="primary"):
                    st.session_state.is_processing = True
                    st.session_state.mapping_confirmed = False
                    st.session_state.column_mapping = {}
                    st.rerun()
            else:
                if st.button("🔄 Iniciar Nova Análise"):
                    st.session_state.processed_data = None
                    st.session_state.metrics = None
                    st.session_state.is_processing = False
                    st.session_state.mapping_confirmed = False
                    st.session_state.column_mapping = {}
                    st.rerun()

    # Main logic based on state
    if st.session_state.get('is_processing'):
        if uploaded_files:
            process_files(uploaded_files, header_row)
        else:
            st.warning("Por favor, faça o upload de arquivos para processar.")
            st.session_state.is_processing = False
    elif st.session_state.get('processed_data') is not None:
        display_results()
    else:
        display_welcome_screen()

def process_files(uploaded_files, header_row):
    progress_bar = st.progress(0, text="Iniciando...")
    
    # Step 1: Validate files and extract column information
    progress_bar.progress(10, text="Validando arquivos...")
    
    file_info = []
    validation_errors = []
    for i, file in enumerate(uploaded_files):
        try:
            # Read file to get column names
            if file.name.endswith('.csv'):
                df_head = pd.read_csv(file, header=header_row - 1, nrows=0)
            else:
                df_head = pd.read_excel(file, header=header_row - 1, nrows=0)
            
            file.seek(0) # Reset file pointer
            file_info.append({
                'file': file,
                'name': file.name,
                'columns': list(df_head.columns)
            })
        except Exception as e:
            err_msg = (f"**{file.name}**: Não foi possível ler o cabeçalho na linha {header_row}. "
                       f"Verifique o arquivo ou o número da linha. (Erro: {e})")
            validation_errors.append(err_msg)

    if validation_errors:
        for error in validation_errors:
            st.error(error, icon="⚠️")

    if not file_info:
        st.error("Nenhum arquivo pôde ser validado com sucesso. O processo foi interrompido.")
        st.session_state.is_processing = False
        st.rerun()
        return

    progress_bar.progress(30, text="Aguardando mapeamento...")
    
    # Step 2: Column mapping interface
    if not st.session_state.mapping_confirmed:
        with st.sidebar:
            mapping_done = configure_column_mapping(file_info)
        if not mapping_done:
            st.info("👈 Configure o mapeamento de colunas na barra lateral e confirme para continuar.")
            return # Wait for user to submit the form

    # Step 3: Process files after mapping is confirmed
    progress_bar.progress(50, text="Processando dados...")
    
    processor = ComplaintProcessor()
    all_data = []
    processing_errors = []

    for i, info in enumerate(file_info):
        try:
            info['file'].seek(0)
            if info['name'].endswith('.csv'):
                df = pd.read_csv(info['file'], header=header_row - 1)
            else:
                df = pd.read_excel(info['file'], header=header_row - 1)
            
            processed_df, errors = processor.process_file(df, st.session_state.column_mapping, info['name'])
            
            if not processed_df.empty:
                all_data.append(processed_df)
            if errors:
                processing_errors.extend(errors)
                
            progress_bar.progress(50 + int(50 * (i + 1) / len(file_info)), text=f"Processando {info['name']}...")
        except Exception as e:
            processing_errors.append(f"Erro crítico ao processar {info['name']}: {e}")

    # Step 4: Combine results and calculate metrics
    if not all_data:
        st.error("Nenhum dado válido foi processado. Verifique o mapeamento de colunas e os dados nos arquivos.")
        st.session_state.is_processing = False
        st.rerun()
        return
        
    combined_df = pd.concat(all_data, ignore_index=True)
    metrics = processor.calculate_metrics(combined_df)
    
    st.session_state.processed_data = combined_df
    st.session_state.metrics = metrics
    
    if processing_errors:
        with st.expander("⚠️ Avisos de Processamento", expanded=True):
            for error in processing_errors:
                st.warning(error)
    
    st.success(f"Processamento concluído! {len(combined_df)} reclamações analisadas.")
    st.session_state.is_processing = False
    st.rerun()

def configure_column_mapping(file_info):
    st.subheader("🗂️ Mapeamento de Colunas")
    st.markdown("**Configure qual coluna corresponde a cada campo necessário:**")
    
    all_columns = sorted(list(set(col for info in file_info for col in info['columns'])))
    column_options = ["-- Selecione --"] + all_columns
    
    with st.form("column_mapping_form"):
        st.markdown("**Campos Obrigatórios:**")
        col1, col2 = st.columns(2)
        
        with col1:
            id_col = st.selectbox("ID da Reclamação *", column_options, help="Coluna com o identificador único da reclamação")
            opening_date_col = st.selectbox("Data de Abertura *", column_options, help="Coluna com a data de criação/abertura da reclamação")
        
        with col2:
            deadline_col = st.selectbox("Data do Prazo *", column_options, help="Coluna com a data limite para resposta")
            response_date_col = st.selectbox("Data da Resposta", column_options, help="Coluna com a data da resposta (pode estar vazia)")
        
        company_col = st.selectbox("Nome da Empresa *", column_options, help="Coluna com o nome da empresa reclamada")
        
        submitted = st.form_submit_button("✅ Confirmar Mapeamento", type="primary")
        
        if submitted:
            required_fields = [id_col, opening_date_col, deadline_col, company_col]
            if any(field == "-- Selecione --" for field in required_fields):
                st.error("Por favor, selecione todas as colunas obrigatórias marcadas com *")
                return False
            
            st.session_state.column_mapping = {
                'id_case': id_col,
                'opening_date': opening_date_col,
                'deadline_date': deadline_col,
                'response_date': response_date_col if response_date_col != "-- Selecione --" else None,
                'company_name': company_col
            }
            st.session_state.mapping_confirmed = True
            st.rerun()
    return st.session_state.mapping_confirmed

def display_welcome_screen():
    st.markdown("## 🚀 Como usar este sistema")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 1️⃣ Upload\n- Faça upload dos arquivos de relatório\n- Formatos: Excel, CSV, ODS\n- Múltiplos arquivos suportados")
    with col2:
        st.markdown("### 2️⃣ Configuração\n- Configure a linha do cabeçalho\n- Mapeie as colunas necessárias\n- Valide as configurações")
    with col3:
        st.markdown("### 3️⃣ Análise\n- Visualize métricas consolidadas\n- Filtre por empresa\n- Exporte os resultados")
    st.markdown("---")
    st.info("👈 **Comece fazendo upload dos arquivos na barra lateral**")

def display_results():
    if st.session_state.processed_data is None or st.session_state.metrics is None:
        return
    
    df = st.session_state.processed_data
    metrics = st.session_state.metrics
    
    st.header("📈 Dashboard de Métricas")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Reclamações", metrics['total_complaints'], help="Número total de reclamações processadas")
    with col2:
        st.metric("Respondidas", f"{metrics['total_responded']} ({metrics['responded_percentage']:.1f}%)", help="Reclamações que receberam resposta")
    with col3:
        st.metric("Dentro do Prazo", f"{metrics['within_deadline']} ({metrics['within_deadline_percentage']:.1f}%)", help="Respostas enviadas dentro do prazo estabelecido")
    with col4:
        st.metric("SLA Médio", f"{metrics['average_response_time']:.1f} dias", help="Tempo médio de resposta em dias")
    
    st.subheader("🚨 Alertas de Prazo")
    alert_col1, alert_col2, alert_col3, alert_col4 = st.columns(4)
    with alert_col1:
        st.metric("🔴 Urgente", len(df[df['alert_level'] == 'Em Cima do Prazo (≤1 dia)']), help="≤1 dia para vencer")
    with alert_col2:
        st.metric("🟡 Atenção", len(df[df['alert_level'] == 'Perto de Ultrapassar o Prazo (2-3 dias)']), help="2-3 dias para vencer")
    with alert_col3:
        st.metric("🟢 Flexível", len(df[df['alert_level'] == 'Prazo Flexível (≥5 dias)']), help="≥5 dias para vencer")
    with alert_col4:
        st.metric("⚫ Vencidas", len(df[df['status_pending'] == 'Vencida e Não Respondida']), help="Prazo já expirado")
    
    st.header("🔍 Filtros e Visualização")
    col1, col2 = st.columns([1, 1])
    with col1:
        companies = ['Todas'] + sorted(df['company_name'].unique().tolist())
        selected_company = st.selectbox("Filtrar por Empresa", companies)
    with col2:
        status_options = ['Todos', 'Respondida', 'Não Respondida', 'Vencida e Não Respondida']
        selected_status = st.selectbox("Filtrar por Status", status_options)
    
    filtered_df = df.copy()
    if selected_company != 'Todas':
        filtered_df = filtered_df[filtered_df['company_name'] == selected_company]
    if selected_status != 'Todos':
        if selected_status == 'Respondida':
            filtered_df = filtered_df[filtered_df['complaint_status'] == 'Respondida']
        elif selected_status == 'Não Respondida':
            filtered_df = filtered_df[filtered_df['complaint_status'] == 'Não Respondida']
        elif selected_status == 'Vencida e Não Respondida':
            filtered_df = filtered_df[filtered_df['status_pending'] == 'Vencida e Não Respondida']
    
    st.subheader(f"📋 Detalhes das Reclamações ({len(filtered_df)} registros)")
    if not filtered_df.empty:
        display_df = filtered_df.copy()
        date_columns = ['opening_date', 'deadline_date', 'response_date']
        for col in date_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: format_date(x) if pd.notna(x) else '')
        
        column_order = ['case_id', 'company_name', 'complaint_status', 'opening_date', 'deadline_date', 'response_date', 'response_time_days', 'deadline_status', 'alert_level', 'days_to_deadline']
        display_columns = [col for col in column_order if col in display_df.columns]
        display_df = display_df[display_columns].rename(columns={
            'case_id': 'ID da Reclamação', 'company_name': 'Empresa', 'complaint_status': 'Status',
            'opening_date': 'Data Abertura', 'deadline_date': 'Data Prazo', 'response_date': 'Data Resposta',
            'response_time_days': 'Tempo Resposta (dias)', 'deadline_status': 'Status Prazo',
            'alert_level': 'Nível de Alerta', 'days_to_deadline': 'Dias para Vencer'
        })
        
        def highlight_alerts(row):
            style = ""
            if 'Nível de Alerta' in row:
                alert = row['Nível de Alerta']
                if 'Em Cima do Prazo' in str(alert):
                    style = 'background-color: #ffebee; color: #37474f;'
                elif 'Perto de Ultrapassar' in str(alert):
                    style = 'background-color: #fff3e0; color: #37474f;'
                elif 'Vencida' in str(row.get('Status', '')):
                    style = 'background-color: #f3e5f5; color: #37474f;'
            
            if style:
                return [style] * len(row)
            return [''] * len(row)
        
        st.dataframe(display_df.style.apply(highlight_alerts, axis=1), use_container_width=True, height=400)
        
        st.subheader("📤 Exportar Resultados")
        col1, col2 = st.columns(2)
        with col1:
            excel_buffer_filtered = export_to_excel(filtered_df, metrics)
            st.download_button(label="📊 Baixar Dados Filtrados", data=excel_buffer_filtered, file_name=f"analise_filtrada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col2:
            excel_buffer_all = export_to_excel(df, metrics)
            st.download_button(label="📈 Baixar Todos os Dados", data=excel_buffer_all, file_name=f"analise_completa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Nenhum registro encontrado com os filtros aplicados.")

if __name__ == "__main__":
    main()