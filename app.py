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
    
    # Sidebar for file upload and configuration
    with st.sidebar:
        st.header("📁 Upload de Arquivos")
        uploaded_files = st.file_uploader(
            "Selecione os arquivos de relatório",
            accept_multiple_files=True,
            type=['xlsx', 'xls', 'csv', 'ods'],
            help="Formatos suportados: Excel (.xlsx, .xls), CSV (.csv), OpenDocument (.ods)"
        )
        
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
            
            # Process files button
            if st.button("🔄 Processar Arquivos", type="primary"):
                process_files(uploaded_files, header_row)
    
    # Main content area
    if st.session_state.processed_data is not None:
        display_results()
    else:
        display_welcome_screen()

def process_files(uploaded_files, header_row):
    """Process uploaded files with column mapping"""
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Validate files and extract column information
        status_text.text("Validando arquivos...")
        progress_bar.progress(10)
        
        validator = DataValidator()
        file_info = []
        
        for i, file in enumerate(uploaded_files):
            try:
                # Read file to get column names
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file, header=header_row-1, nrows=0)
                else:
                    df = pd.read_excel(file, header=header_row-1, nrows=0)
                
                file_info.append({
                    'file': file,
                    'name': file.name,
                    'columns': list(df.columns)
                })
            except Exception as e:
                st.error(f"Erro ao ler arquivo {file.name}: {str(e)}")
                return
        
        progress_bar.progress(30)
        
        # Step 2: Column mapping interface
        status_text.text("Configurando mapeamento de colunas...")
        
        if not configure_column_mapping(file_info):
            return
        
        progress_bar.progress(50)
        
        # Step 3: Process files
        status_text.text("Processando dados...")
        
        processor = ComplaintProcessor()
        all_data = []
        processing_errors = []
        
        for i, info in enumerate(file_info):
            try:
                # Reset file pointer
                info['file'].seek(0)
                
                # Read file data
                if info['name'].endswith('.csv'):
                    df = pd.read_csv(info['file'], header=header_row-1)
                else:
                    df = pd.read_excel(info['file'], header=header_row-1)
                
                # Process data
                processed_df, errors = processor.process_file(
                    df, 
                    st.session_state.column_mapping,
                    info['name']
                )
                
                if not processed_df.empty:
                    all_data.append(processed_df)
                
                if errors:
                    processing_errors.extend(errors)
                
                progress_bar.progress(50 + (40 * (i + 1) / len(file_info)))
                
            except Exception as e:
                error_msg = f"Erro ao processar {info['name']}: {str(e)}"
                processing_errors.append(error_msg)
                st.error(error_msg)
        
        progress_bar.progress(90)
        
        # Step 4: Combine results and calculate metrics
        if all_data:
            status_text.text("Calculando métricas...")
            
            combined_df = pd.concat(all_data, ignore_index=True)
            metrics = processor.calculate_metrics(combined_df)
            
            st.session_state.processed_data = combined_df
            st.session_state.metrics = metrics
            
            progress_bar.progress(100)
            status_text.text("✅ Processamento concluído!")
            
            # Show processing summary
            if processing_errors:
                with st.expander("⚠️ Avisos de Processamento", expanded=False):
                    for error in processing_errors:
                        st.warning(error)
            
            st.success(f"Processamento concluído! {len(combined_df)} reclamações processadas.")
            st.rerun()
        else:
            st.error("Nenhum dado válido foi processado. Verifique os arquivos e o mapeamento de colunas.")
    
    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")

def configure_column_mapping(file_info):
    """Configure column mapping interface"""
    st.subheader("🗂️ Mapeamento de Colunas")
    st.markdown("**Configure qual coluna corresponde a cada campo necessário:**")
    
    # Get all unique column names from all files
    all_columns = set()
    for info in file_info:
        all_columns.update(info['columns'])
    
    all_columns = sorted(list(all_columns))
    column_options = ["-- Selecione --"] + all_columns
    
    # Column mapping form
    with st.form("column_mapping_form"):
        st.markdown("**Campos Obrigatórios:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            id_col = st.selectbox(
                "ID da Reclamação *",
                column_options,
                help="Coluna com o identificador único da reclamação"
            )
            
            opening_date_col = st.selectbox(
                "Data de Abertura *",
                column_options,
                help="Coluna com a data de criação/abertura da reclamação"
            )
        
        with col2:
            deadline_col = st.selectbox(
                "Data do Prazo *",
                column_options,
                help="Coluna com a data limite para resposta"
            )
            
            response_date_col = st.selectbox(
                "Data da Resposta",
                column_options,
                help="Coluna com a data da resposta (pode estar vazia)"
            )
        
        company_col = st.selectbox(
            "Nome da Empresa *",
            column_options,
            help="Coluna com o nome da empresa reclamada"
        )
        
        submitted = st.form_submit_button("✅ Confirmar Mapeamento", type="primary")
        
        if submitted:
            # Validate required fields
            required_fields = [id_col, opening_date_col, deadline_col, company_col]
            if any(field == "-- Selecione --" for field in required_fields):
                st.error("Por favor, selecione todas as colunas obrigatórias marcadas com *")
                return False
            
            # Save mapping
            st.session_state.column_mapping = {
                'id_case': id_col,
                'opening_date': opening_date_col,
                'deadline_date': deadline_col,
                'response_date': response_date_col if response_date_col != "-- Selecione --" else None,
                'company_name': company_col
            }
            
            st.success("✅ Mapeamento configurado com sucesso!")
            return True
    
    return False

def display_welcome_screen():
    """Display welcome screen with instructions"""
    st.markdown("## 🚀 Como usar este sistema")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 1️⃣ Upload
        - Faça upload dos arquivos de relatório
        - Formatos: Excel, CSV, ODS
        - Múltiplos arquivos suportados
        """)
    
    with col2:
        st.markdown("""
        ### 2️⃣ Configuração
        - Configure a linha do cabeçalho
        - Mapeie as colunas necessárias
        - Valide as configurações
        """)
    
    with col3:
        st.markdown("""
        ### 3️⃣ Análise
        - Visualize métricas consolidadas
        - Filtre por empresa
        - Exporte os resultados
        """)
    
    st.markdown("---")
    st.info("👈 **Comece fazendo upload dos arquivos na barra lateral**")

def display_results():
    """Display processing results and metrics"""
    if st.session_state.processed_data is None or st.session_state.metrics is None:
        return
    
    df = st.session_state.processed_data
    metrics = st.session_state.metrics
    
    # Metrics dashboard
    st.header("📈 Dashboard de Métricas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total de Reclamações",
            metrics['total_complaints'],
            help="Número total de reclamações processadas"
        )
    
    with col2:
        st.metric(
            "Respondidas",
            f"{metrics['total_responded']} ({metrics['responded_percentage']:.1f}%)",
            help="Reclamações que receberam resposta"
        )
    
    with col3:
        st.metric(
            "Dentro do Prazo",
            f"{metrics['within_deadline']} ({metrics['within_deadline_percentage']:.1f}%)",
            help="Respostas enviadas dentro do prazo estabelecido"
        )
    
    with col4:
        st.metric(
            "SLA Médio",
            f"{metrics['average_response_time']:.1f} dias",
            help="Tempo médio de resposta em dias"
        )
    
    # Alert summary
    st.subheader("🚨 Alertas de Prazo")
    
    alert_col1, alert_col2, alert_col3, alert_col4 = st.columns(4)
    
    with alert_col1:
        urgent_count = len(df[df['alert_level'] == 'Em Cima do Prazo (≤1 dia)'])
        st.metric("🔴 Urgente", urgent_count, help="≤1 dia para vencer")
    
    with alert_col2:
        warning_count = len(df[df['alert_level'] == 'Perto de Ultrapassar o Prazo (2-3 dias)'])
        st.metric("🟡 Atenção", warning_count, help="2-3 dias para vencer")
    
    with alert_col3:
        flexible_count = len(df[df['alert_level'] == 'Prazo Flexível (≥5 dias)'])
        st.metric("🟢 Flexível", flexible_count, help="≥5 dias para vencer")
    
    with alert_col4:
        overdue_count = len(df[df['status_pending'] == 'Vencida e Não Respondida'])
        st.metric("⚫ Vencidas", overdue_count, help="Prazo já expirado")
    
    # Filters
    st.header("🔍 Filtros e Visualização")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Company filter
        companies = ['Todas'] + sorted(df['company_name'].unique().tolist())
        selected_company = st.selectbox("Filtrar por Empresa", companies)
    
    with col2:
        # Status filter
        status_options = ['Todos', 'Respondida', 'Não Respondida', 'Vencida e Não Respondida']
        selected_status = st.selectbox("Filtrar por Status", status_options)
    
    # Apply filters
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
    
    # Display filtered results
    st.subheader(f"📋 Detalhes das Reclamações ({len(filtered_df)} registros)")
    
    if not filtered_df.empty:
        # Prepare display dataframe
        display_df = filtered_df.copy()
        
        # Format dates for display
        date_columns = ['opening_date', 'deadline_date', 'response_date']
        for col in date_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: format_date(x) if pd.notna(x) else '')
        
        # Reorder columns for better display
        column_order = [
            'case_id', 'company_name', 'complaint_status', 'opening_date', 
            'deadline_date', 'response_date', 'response_time_days', 
            'deadline_status', 'alert_level', 'days_to_deadline'
        ]
        
        display_columns = [col for col in column_order if col in display_df.columns]
        display_df = display_df[display_columns]
        
        # Rename columns for better readability
        column_names = {
            'case_id': 'ID da Reclamação',
            'company_name': 'Empresa',
            'complaint_status': 'Status',
            'opening_date': 'Data Abertura',
            'deadline_date': 'Data Prazo',
            'response_date': 'Data Resposta',
            'response_time_days': 'Tempo Resposta (dias)',
            'deadline_status': 'Status Prazo',
            'alert_level': 'Nível de Alerta',
            'days_to_deadline': 'Dias para Vencer'
        }
        
        display_df = display_df.rename(columns=column_names)
        
        # Color coding for alerts
        def highlight_alerts(row):
            if 'Nível de Alerta' in row:
                alert = row['Nível de Alerta']
                if 'Em Cima do Prazo' in str(alert):
                    return ['background-color: #ffebee'] * len(row)
                elif 'Perto de Ultrapassar' in str(alert):
                    return ['background-color: #fff3e0'] * len(row)
                elif 'Vencida' in str(row.get('Status', '')):
                    return ['background-color: #f3e5f5'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            display_df.style.apply(highlight_alerts, axis=1),
            use_container_width=True,
            height=400
        )
        
        # Export functionality
        st.subheader("📤 Exportar Resultados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar Dados Filtrados", type="secondary"):
                excel_buffer = export_to_excel(filtered_df, metrics)
                st.download_button(
                    label="⬇️ Baixar Excel",
                    data=excel_buffer,
                    file_name=f"analise_reclamacoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            if st.button("📈 Exportar Todos os Dados", type="secondary"):
                excel_buffer = export_to_excel(df, metrics)
                st.download_button(
                    label="⬇️ Baixar Excel Completo",
                    data=excel_buffer,
                    file_name=f"analise_completa_reclamacoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("Nenhum registro encontrado com os filtros aplicados.")

if __name__ == "__main__":
    main()
