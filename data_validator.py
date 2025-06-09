import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Any
import os

class DataValidator:
    """Validate uploaded files and data quality"""
    
    def __init__(self):
        self.supported_extensions = ['.xlsx', '.xls', '.csv', '.ods']
        self.max_file_size = 50 * 1024 * 1024  # 50MB
    
    def validate_files(self, uploaded_files: List[Any]) -> Tuple[List[Dict], List[str]]:
        """
        Validate uploaded files for basic requirements
        
        Args:
            uploaded_files: List of uploaded file objects
            
        Returns:
            Tuple of (valid_files_info, list_of_errors)
        """
        valid_files = []
        errors = []
        
        if not uploaded_files:
            errors.append("Nenhum arquivo foi selecionado")
            return valid_files, errors
        
        for file in uploaded_files:
            file_info = self._validate_single_file(file)
            
            if file_info['valid']:
                valid_files.append(file_info)
            else:
                errors.extend(file_info['errors'])
        
        return valid_files, errors
    
    def _validate_single_file(self, file) -> Dict[str, Any]:
        """Validate a single uploaded file"""
        file_info = {
            'file': file,
            'name': file.name,
            'valid': False,
            'errors': [],
            'size': 0,
            'extension': ''
        }
        
        try:
            # Check file extension
            file_extension = os.path.splitext(file.name)[1].lower()
            file_info['extension'] = file_extension
            
            if file_extension not in self.supported_extensions:
                file_info['errors'].append(
                    f"Formato de arquivo não suportado: {file.name}. "
                    f"Formatos aceitos: {', '.join(self.supported_extensions)}"
                )
                return file_info
            
            # Check file size
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            file_info['size'] = file_size
            
            if file_size > self.max_file_size:
                file_info['errors'].append(
                    f"Arquivo muito grande: {file.name} "
                    f"({file_size / (1024*1024):.1f}MB). Máximo: {self.max_file_size / (1024*1024):.0f}MB"
                )
                return file_info
            
            # Try to read file structure
            try:
                if file_extension == '.csv':
                    # Test CSV reading
                    pd.read_csv(file, nrows=1)
                else:
                    # Test Excel reading
                    pd.read_excel(file, nrows=1)
                
                file.seek(0)  # Reset file pointer
                file_info['valid'] = True
                
            except Exception as e:
                file_info['errors'].append(
                    f"Erro ao ler arquivo {file.name}: {str(e)}"
                )
        
        except Exception as e:
            file_info['errors'].append(
                f"Erro de validação para {file.name}: {str(e)}"
            )
        
        return file_info
    
    def validate_column_mapping(self, df: pd.DataFrame, column_mapping: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate that mapped columns exist in the dataframe
        
        Args:
            df: Dataframe to validate
            column_mapping: Dictionary mapping logical names to column names
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required columns
        required_mappings = ['id_case', 'opening_date', 'deadline_date', 'company_name']
        
        for logical_name in required_mappings:
            if logical_name not in column_mapping:
                errors.append(f"Mapeamento obrigatório ausente: {logical_name}")
                continue
            
            column_name = column_mapping[logical_name]
            if column_name not in df.columns:
                errors.append(f"Coluna não encontrada: '{column_name}' (mapeada como {logical_name})")
        
        # Optional response date column
        if column_mapping.get('response_date') and column_mapping['response_date'] not in df.columns:
            errors.append(f"Coluna não encontrada: '{column_mapping['response_date']}' (mapeada como response_date)")
        
        return len(errors) == 0, errors
    
    def validate_data_quality(self, df: pd.DataFrame, column_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze data quality issues in the dataframe
        
        Args:
            df: Dataframe to analyze
            column_mapping: Column mapping configuration
            
        Returns:
            Dictionary with quality metrics and issues
        """
        quality_report = {
            'total_rows': len(df),
            'issues': [],
            'column_stats': {},
            'date_parsing_issues': [],
            'missing_data_summary': {}
        }
        
        # Analyze each mapped column
        for logical_name, column_name in column_mapping.items():
            if column_name and column_name in df.columns:
                col_data = df[column_name]
                
                # Basic statistics
                stats = {
                    'total_values': len(col_data),
                    'null_count': col_data.isnull().sum(),
                    'empty_strings': (col_data == '').sum() if col_data.dtype == 'object' else 0,
                    'unique_values': col_data.nunique()
                }
                
                stats['valid_percentage'] = ((stats['total_values'] - stats['null_count'] - stats['empty_strings']) 
                                           / stats['total_values'] * 100) if stats['total_values'] > 0 else 0
                
                quality_report['column_stats'][logical_name] = stats
                
                # Check for critical missing data
                if logical_name in ['id_case', 'opening_date', 'deadline_date', 'company_name']:
                    missing_count = stats['null_count'] + stats['empty_strings']
                    if missing_count > 0:
                        quality_report['issues'].append(
                            f"Coluna crítica '{column_name}' ({logical_name}) tem {missing_count} valores faltantes"
                        )
                
                # Date column validation
                if logical_name in ['opening_date', 'deadline_date', 'response_date']:
                    date_issues = self._analyze_date_column(col_data, column_name)
                    if date_issues:
                        quality_report['date_parsing_issues'].extend(date_issues)
        
        # Summary of rows with missing critical data
        critical_columns = [column_mapping.get(name) for name in ['id_case', 'opening_date', 'deadline_date', 'company_name'] 
                           if column_mapping.get(name)]
        
        if critical_columns:
            missing_critical = df[critical_columns].isnull().any(axis=1).sum()
            quality_report['missing_data_summary']['rows_with_missing_critical_data'] = missing_critical
            quality_report['missing_data_summary']['processable_rows'] = len(df) - missing_critical
        
        return quality_report
    
    def _analyze_date_column(self, col_data: pd.Series, column_name: str) -> List[str]:
        """Analyze date column for parsing issues"""
        issues = []
        
        # Sample non-null values for date format detection
        non_null_data = col_data.dropna()
        if non_null_data.empty:
            return issues
        
        # Try to parse a sample of dates
        sample_size = min(10, len(non_null_data))
        sample_data = non_null_data.head(sample_size)
        
        parsing_failures = 0
        for value in sample_data:
            try:
                pd.to_datetime(value)
            except:
                parsing_failures += 1
        
        if parsing_failures > 0:
            issues.append(
                f"Coluna '{column_name}': {parsing_failures}/{sample_size} valores de amostra "
                f"não puderam ser interpretados como datas"
            )
        
        return issues
    
    def get_file_preview(self, file, header_row: int = 1, preview_rows: int = 5) -> Tuple[pd.DataFrame, List[str]]:
        """
        Get a preview of the file data for column mapping
        
        Args:
            file: Uploaded file object
            header_row: Row number where headers are located (1-based)
            preview_rows: Number of data rows to preview
            
        Returns:
            Tuple of (preview_dataframe, list_of_errors)
        """
        errors = []
        
        try:
            file.seek(0)
            
            if file.name.endswith('.csv'):
                df = pd.read_csv(file, header=header_row-1, nrows=preview_rows)
            else:
                df = pd.read_excel(file, header=header_row-1, nrows=preview_rows)
            
            file.seek(0)  # Reset file pointer
            return df, errors
            
        except Exception as e:
            errors.append(f"Erro ao gerar preview de {file.name}: {str(e)}")
            return pd.DataFrame(), errors
