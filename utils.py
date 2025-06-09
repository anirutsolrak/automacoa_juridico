import pandas as pd
import numpy as np
from datetime import datetime
from typing import Any, Dict
import io

def format_date(date_obj: Any) -> str:
    """Format date object for display"""
    if pd.isna(date_obj):
        return ""
    
    if isinstance(date_obj, str):
        return date_obj
    
    try:
        if hasattr(date_obj, 'strftime'):
            return date_obj.strftime('%d/%m/%Y')
        else:
            return str(date_obj)
    except:
        return str(date_obj)

def format_number(number: Any, decimals: int = 1) -> str:
    """Format number for display"""
    if pd.isna(number):
        return "N/A"
    
    try:
        return f"{float(number):.{decimals}f}"
    except:
        return str(number)

def safe_division(numerator: float, denominator: float) -> float:
    """Perform safe division avoiding division by zero"""
    if denominator == 0:
        return 0.0
    return numerator / denominator

def export_to_excel(df: pd.DataFrame, metrics: Dict[str, Any]) -> bytes:
    """
    Export processed data and metrics to Excel format
    
    Args:
        df: Processed complaints dataframe
        metrics: Calculated metrics dictionary
        
    Returns:
        Excel file as bytes
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Processed Data
        export_df = df.copy()
        
        # Format dates for export
        date_columns = ['opening_date', 'deadline_date', 'response_date']
        for col in date_columns:
            if col in export_df.columns:
                export_df[col] = export_df[col].apply(lambda x: format_date(x) if pd.notna(x) else '')
        
        # Rename columns for better readability
        column_names = {
            'case_id': 'ID da Reclamação',
            'company_name': 'Empresa',
            'opening_date': 'Data de Abertura',
            'deadline_date': 'Data do Prazo',
            'response_date': 'Data da Resposta',
            'complaint_status': 'Status da Reclamação',
            'response_time_days': 'Tempo de Resposta (dias)',
            'deadline_status': 'Status do Prazo',
            'days_to_deadline': 'Dias para o Prazo',
            'status_pending': 'Status de Pendência',
            'alert_level': 'Nível de Alerta',
            'source_file': 'Arquivo de Origem',
            'source_row': 'Linha de Origem'
        }
        
        export_df = export_df.rename(columns=column_names)
        export_df.to_excel(writer, sheet_name='Dados Processados', index=False)
        
        # Sheet 2: Metrics Summary
        metrics_data = []
        
        # General metrics
        metrics_data.extend([
            ['MÉTRICAS GERAIS', ''],
            ['Total de Reclamações', metrics['total_complaints']],
            ['Total Respondidas', f"{metrics['total_responded']} ({metrics['responded_percentage']:.1f}%)"],
            ['Total Não Respondidas', metrics['total_not_responded']],
            ['Tempo Médio de Resposta', f"{metrics['average_response_time']:.1f} dias"],
            [''],
            
            ['CUMPRIMENTO DE PRAZOS', ''],
            ['Respondidas Dentro do Prazo', f"{metrics['within_deadline']} ({metrics['within_deadline_percentage']:.1f}%)"],
            ['Respondidas Fora do Prazo', metrics['total_responded'] - metrics['within_deadline']],
            [''],
            
            ['PENDÊNCIAS', ''],
            ['No Prazo (Não Respondidas)', metrics['in_deadline_not_responded']],
            ['Vencidas (Não Respondidas)', metrics['overdue_not_responded']],
            [''],
            
            ['ALERTAS DE PRAZO', '']
        ])
        
        # Alert breakdown
        for alert_type, count in metrics['alert_breakdown'].items():
            metrics_data.append([alert_type, count])
        
        metrics_data.extend([
            [''],
            ['Data de Processamento', metrics['processing_date'].strftime('%d/%m/%Y %H:%M:%S')]
        ])
        
        metrics_df = pd.DataFrame(metrics_data, columns=['Métrica', 'Valor'])
        metrics_df.to_excel(writer, sheet_name='Métricas', index=False)
        
        # Sheet 3: Company Breakdown
        if not metrics['company_breakdown'].empty:
            company_df = metrics['company_breakdown'].reset_index()
            company_df.to_excel(writer, sheet_name='Por Empresa', index=False)
        
        # Sheet 4: Alert Summary
        alert_summary = df.groupby(['company_name', 'alert_level']).size().unstack(fill_value=0)
        if not alert_summary.empty:
            alert_summary.to_excel(writer, sheet_name='Resumo de Alertas')
    
    output.seek(0)
    return output.getvalue()

def calculate_business_days(start_date: datetime, end_date: datetime) -> int:
    """
    Calculate business days between two dates (excluding weekends)
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Number of business days
    """
    if not start_date or not end_date:
        return 0
    
    try:
        return pd.bdate_range(start=start_date, end=end_date).size
    except:
        return 0

def validate_date_format(date_string: str) -> bool:
    """
    Validate if a string can be parsed as a date
    
    Args:
        date_string: String to validate
        
    Returns:
        True if valid date format, False otherwise
    """
    if not date_string or pd.isna(date_string):
        return False
    
    try:
        pd.to_datetime(date_string)
        return True
    except:
        return False

def clean_text(text: Any) -> str:
    """
    Clean text data by removing extra whitespace and handling None values
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text string
    """
    if pd.isna(text):
        return ""
    
    return str(text).strip()

def get_company_color(company_name: str) -> str:
    """
    Get consistent color coding for companies
    
    Args:
        company_name: Name of the company
        
    Returns:
        Hex color code
    """
    company_colors = {
        'Capital Consig': '#1f77b4',
        'Clickbank': '#ff7f0e',
        'Hoje': '#2ca02c',
        'CIASPREV': '#d62728',
        'Não Identificada': '#9467bd'
    }
    
    return company_colors.get(company_name, '#17becf')

def get_alert_color(alert_level: str) -> str:
    """
    Get color coding for alert levels
    
    Args:
        alert_level: Alert level string
        
    Returns:
        Hex color code
    """
    alert_colors = {
        'Em Cima do Prazo (≤1 dia)': '#d32f2f',
        'Perto de Ultrapassar o Prazo (2-3 dias)': '#f57c00',
        'Atenção (4 dias)': '#fbc02d',
        'Prazo Flexível (≥5 dias)': '#388e3c',
        'Vencida': '#7b1fa2'
    }
    
    return alert_colors.get(alert_level, '#616161')

def generate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate additional summary statistics for the processed data
    
    Args:
        df: Processed complaints dataframe
        
    Returns:
        Dictionary with summary statistics
    """
    if df.empty:
        return {}
    
    stats = {}
    
    # Response time statistics
    response_times = df[df['response_time_days'].notna()]['response_time_days']
    if not response_times.empty:
        stats['response_time_stats'] = {
            'min': response_times.min(),
            'max': response_times.max(),
            'median': response_times.median(),
            'std': response_times.std()
        }
    
    # Days to deadline statistics for pending complaints
    pending_days = df[df['days_to_deadline'].notna()]['days_to_deadline']
    if not pending_days.empty:
        stats['pending_deadline_stats'] = {
            'min': pending_days.min(),
            'max': pending_days.max(),
            'median': pending_days.median(),
            'negative_count': (pending_days < 0).sum()  # Overdue count
        }
    
    # Company distribution
    stats['company_distribution'] = df['company_name'].value_counts().to_dict()
    
    # Monthly trend (if enough data)
    df_with_dates = df[df['opening_date'].notna()].copy()
    if not df_with_dates.empty:
        df_with_dates['month_year'] = df_with_dates['opening_date'].apply(
            lambda x: x.strftime('%Y-%m') if pd.notna(x) else None
        )
        stats['monthly_trend'] = df_with_dates['month_year'].value_counts().sort_index().to_dict()
    
    return stats
