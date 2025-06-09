import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Tuple, Any
import re

class ComplaintProcessor:
    """Process complaint data and calculate SLA metrics"""
    
    def __init__(self):
        self.processing_date = datetime.now()
    
    def process_file(self, df: pd.DataFrame, column_mapping: Dict[str, str], filename: str) -> Tuple[pd.DataFrame, List[str]]:
        """
        Process a single file's data according to business rules
        
        Args:
            df: Raw dataframe from file
            column_mapping: Mapping of logical fields to actual column names
            filename: Name of the source file
            
        Returns:
            Tuple of (processed_dataframe, list_of_errors)
        """
        errors = []
        processed_rows = []
        
        # Extract mapped columns
        try:
            id_col = column_mapping['id_case']
            opening_col = column_mapping['opening_date']
            deadline_col = column_mapping['deadline_date']
            response_col = column_mapping.get('response_date')
            company_col = column_mapping['company_name']
        except KeyError as e:
            errors.append(f"Coluna obrigatória não mapeada: {e}")
            return pd.DataFrame(), errors
        
        # Validate columns exist in dataframe
        required_cols = [id_col, opening_col, deadline_col, company_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            errors.append(f"Colunas não encontradas em {filename}: {missing_cols}")
            return pd.DataFrame(), errors
        
        # Process each row
        for i, (row_idx, row) in enumerate(df.iterrows()):
            try:
                row_num = i + 1
                processed_row = self._process_single_complaint(
                    row, column_mapping, filename, row_num
                )
                
                if processed_row:
                    processed_rows.append(processed_row)
                else:
                    errors.append(f"Linha {row_num} em {filename}: dados críticos faltando")
                    
            except Exception as e:
                row_num = i + 1
                errors.append(f"Erro na linha {row_num} em {filename}: {str(e)}")
        
        if processed_rows:
            result_df = pd.DataFrame(processed_rows)
            return result_df, errors
        else:
            return pd.DataFrame(), errors
    
    def _process_single_complaint(self, row: pd.Series, column_mapping: Dict[str, str], 
                                filename: str, row_num: int) -> Dict[str, Any] | None:
        """Process a single complaint row"""
        
        # Extract raw values
        case_id_raw = row.get(column_mapping['id_case'])
        opening_date_raw = row.get(column_mapping['opening_date'])
        deadline_date_raw = row.get(column_mapping['deadline_date'])
        response_date_raw = row.get(column_mapping.get('response_date')) if column_mapping.get('response_date') else None
        company_name_raw = row.get(column_mapping['company_name'])
        
        # Clean and validate case ID
        case_id = self._clean_case_id(case_id_raw)
        if not case_id:
            return None
        
        # Parse and validate dates
        opening_date = self._parse_date(opening_date_raw)
        deadline_date = self._parse_date(deadline_date_raw)
        
        if not opening_date or not deadline_date:
            return None
        
        # Parse response date (can be None/empty)
        response_date = self._parse_date(response_date_raw) if response_date_raw else None
        
        # Clean company name
        company_name = self._normalize_company_name(company_name_raw)
        
        # Calculate status and metrics
        complaint_status = "Respondida" if response_date else "Não Respondida"
        
        # Calculate response time
        response_time_days = None
        if response_date and opening_date:
            response_time_days = (response_date - opening_date).days
        
        # Determine deadline status for responded complaints
        deadline_status = None
        if complaint_status == "Respondida" and response_date and deadline_date:
            if response_date <= deadline_date:
                deadline_status = "Dentro do Prazo"
            else:
                deadline_status = "Fora do Prazo"
        
        # Calculate days to deadline and pending status for non-responded
        days_to_deadline = None
        status_pending = None
        alert_level = None
        
        if complaint_status == "Não Respondida":
            days_to_deadline = (deadline_date.date() - self.processing_date.date()).days
            
            if days_to_deadline < 0:
                status_pending = "Vencida e Não Respondida"
                alert_level = "Vencida"
            else:
                status_pending = "No Prazo, Não Respondida"
                alert_level = self._calculate_alert_level(days_to_deadline)
        
        return {
            'case_id': case_id,
            'company_name': company_name,
            'opening_date': opening_date,
            'deadline_date': deadline_date,
            'response_date': response_date,
            'complaint_status': complaint_status,
            'response_time_days': response_time_days,
            'deadline_status': deadline_status,
            'days_to_deadline': days_to_deadline,
            'status_pending': status_pending,
            'alert_level': alert_level,
            'source_file': filename,
            'source_row': row_num
        }
    
    def _clean_case_id(self, case_id_raw: Any) -> str | None:
        """Clean and validate case ID"""
        if pd.isna(case_id_raw):
            return None
        
        case_id = str(case_id_raw).strip()
        return case_id if case_id else None
    
    def _parse_date(self, date_raw: Any) -> datetime | None:
        """Parse date from various formats"""
        if pd.isna(date_raw):
            return None
        
        # If already a datetime
        if isinstance(date_raw, (datetime, pd.Timestamp)):
            return pd.to_datetime(date_raw)
        
        # If it's a date object
        if isinstance(date_raw, date):
            return datetime.combine(date_raw, datetime.min.time())
        
        # Try to parse string
        date_str = str(date_raw).strip()
        if not date_str:
            return None
        
        # Common date formats to try (Brazilian format first)
        date_formats = [
            '%d/%m/%Y %H:%M:%S',  # 26/05/2025 16:33:46
            '%d/%m/%Y %H:%M',     # 26/05/2025 16:33
            '%d/%m/%Y',           # 09/06/2025
            '%d-%m-%Y %H:%M:%S',  # 26-05-2025 16:33:46
            '%d-%m-%Y %H:%M',     # 26-05-2025 16:33
            '%d-%m-%Y',           # 09-06-2025
            '%d/%m/%y %H:%M:%S',  # 26/05/25 16:33:46
            '%d/%m/%y %H:%M',     # 26/05/25 16:33
            '%d/%m/%y',           # 09/06/25
            '%Y-%m-%d %H:%M:%S',  # ISO format
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%m/%d/%Y %H:%M:%S',  # US format
            '%m/%d/%Y %H:%M',
            '%m/%d/%Y',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%Y/%m/%d'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try pandas parsing as last resort
        try:
            return pd.to_datetime(date_str, dayfirst=True)
        except:
            return None
    
    def _normalize_company_name(self, company_raw: Any) -> str:
        """Clean company name while preserving original text"""
        if pd.isna(company_raw):
            return "Não Identificada"
        
        # Simply clean the company name without forcing specific mappings
        company_name = str(company_raw).strip()
        
        # Return empty string as "Não Identificada"
        if not company_name:
            return "Não Identificada"
        
        return company_name
    
    def _calculate_alert_level(self, days_to_deadline: int) -> str:
        """Calculate alert level based on days remaining"""
        if days_to_deadline <= 1:
            return "Em Cima do Prazo (≤1 dia)"
        elif days_to_deadline <= 3:
            return "Perto de Ultrapassar o Prazo (2-3 dias)"
        elif days_to_deadline == 4:
            return "Atenção (4 dias)"
        else:
            return "Prazo Flexível (≥5 dias)"
    
    def calculate_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate consolidated metrics from processed data"""
        if df.empty:
            return self._empty_metrics()
        
        total_complaints = len(df)
        
        # Response metrics
        responded = df[df['complaint_status'] == 'Respondida']
        total_responded = len(responded)
        responded_percentage = (total_responded / total_complaints * 100) if total_complaints > 0 else 0
        
        # Deadline compliance for responded complaints
        within_deadline = len(responded[responded['deadline_status'] == 'Dentro do Prazo'])
        within_deadline_percentage = (within_deadline / total_responded * 100) if total_responded > 0 else 0
        
        # Response time metrics
        if not responded.empty and 'response_time_days' in responded.columns:
            response_times = responded['response_time_days'].dropna()
            average_response_time = float(response_times.mean()) if len(response_times) > 0 else 0.0
        else:
            average_response_time = 0.0
        
        # Pending status breakdown
        not_responded = df[df['complaint_status'] == 'Não Respondida']
        total_not_responded = len(not_responded)
        
        in_deadline_not_responded = len(df[df['status_pending'] == 'No Prazo, Não Respondida'])
        overdue_not_responded = len(df[df['status_pending'] == 'Vencida e Não Respondida'])
        
        # Alert level breakdown
        alert_breakdown = df['alert_level'].value_counts().to_dict()
        
        # Company breakdown
        company_breakdown = df.groupby('company_name').agg({
            'case_id': 'count',
            'complaint_status': lambda x: (x == 'Respondida').sum(),
            'deadline_status': lambda x: (x == 'Dentro do Prazo').sum(),
            'response_time_days': 'mean'
        }).round(2)
        
        company_breakdown.columns = ['Total', 'Respondidas', 'Dentro do Prazo', 'Tempo Médio (dias)']
        
        return {
            'total_complaints': total_complaints,
            'total_responded': total_responded,
            'responded_percentage': responded_percentage,
            'total_not_responded': total_not_responded,
            'within_deadline': within_deadline,
            'within_deadline_percentage': within_deadline_percentage,
            'average_response_time': average_response_time,
            'in_deadline_not_responded': in_deadline_not_responded,
            'overdue_not_responded': overdue_not_responded,
            'alert_breakdown': alert_breakdown,
            'company_breakdown': company_breakdown,
            'processing_date': self.processing_date
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            'total_complaints': 0,
            'total_responded': 0,
            'responded_percentage': 0,
            'total_not_responded': 0,
            'within_deadline': 0,
            'within_deadline_percentage': 0,
            'average_response_time': 0,
            'in_deadline_not_responded': 0,
            'overdue_not_responded': 0,
            'alert_breakdown': {},
            'company_breakdown': pd.DataFrame(),
            'processing_date': self.processing_date
        }
