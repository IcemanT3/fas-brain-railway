"""
Admin Console Module
Provides system monitoring, environment validation, and operational insights
"""
import os
import psutil
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rlhaxgpojdbflaeamhty.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None


class AdminConsole:
    """
    Provides administrative functions and system monitoring
    """
    
    def __init__(self):
        if supabase is None:
            raise RuntimeError("Supabase client not initialized")
        self.supabase = supabase
        self.start_time = time.time()
    
    async def validate_environment(self) -> Dict:
        """
        Validate all required environment variables and services
        
        Returns:
            Dictionary with validation results
        """
        validations = {}
        
        # Check required environment variables
        required_vars = [
            'SUPABASE_URL',
            'SUPABASE_SERVICE_ROLE_KEY',
            'OPENAI_API_KEY'
        ]
        
        optional_vars = [
            'MICROSOFT_CLIENT_ID',
            'MICROSOFT_CLIENT_SECRET',
            'MICROSOFT_TENANT_ID'
        ]
        
        # Validate required vars
        for var in required_vars:
            value = os.getenv(var)
            validations[var] = {
                'present': value is not None and len(value) > 0,
                'required': True,
                'status': 'OK' if value else 'MISSING'
            }
        
        # Validate optional vars
        for var in optional_vars:
            value = os.getenv(var)
            validations[var] = {
                'present': value is not None and len(value) > 0,
                'required': False,
                'status': 'OK' if value else 'NOT_SET'
            }
        
        # Test database connection
        try:
            result = self.supabase.table('documents').select('id').limit(1).execute()
            validations['database_connection'] = {
                'present': True,
                'required': True,
                'status': 'OK'
            }
        except Exception as e:
            validations['database_connection'] = {
                'present': False,
                'required': True,
                'status': f'ERROR: {str(e)}'
            }
        
        # Calculate overall status
        all_required_ok = all(
            v['status'] == 'OK'
            for v in validations.values()
            if v['required']
        )
        
        return {
            'validations': validations,
            'overall_status': 'HEALTHY' if all_required_ok else 'DEGRADED',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_system_metrics(self) -> Dict:
        """
        Get system resource metrics
        
        Returns:
            Dictionary with system metrics
        """
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Uptime
        uptime_seconds = time.time() - self.start_time
        
        return {
            'cpu': {
                'usage_percent': cpu_percent,
                'count': cpu_count
            },
            'memory': {
                'total_mb': memory.total / (1024 * 1024),
                'used_mb': memory.used / (1024 * 1024),
                'available_mb': memory.available / (1024 * 1024),
                'percent': memory.percent
            },
            'disk': {
                'total_gb': disk.total / (1024 * 1024 * 1024),
                'used_gb': disk.used / (1024 * 1024 * 1024),
                'free_gb': disk.free / (1024 * 1024 * 1024),
                'percent': disk.percent
            },
            'uptime_seconds': uptime_seconds,
            'uptime_hours': uptime_seconds / 3600,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_ingestion_stats(self, hours: int = 24) -> Dict:
        """
        Get document ingestion statistics
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with ingestion stats
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get documents uploaded in time period
        result = self.supabase.table('documents').select(
            'id, created_at, file_size, document_type'
        ).gte(
            'created_at', cutoff_time.isoformat()
        ).execute()
        
        documents = result.data if result.data else []
        
        # Calculate stats
        total_documents = len(documents)
        total_size = sum(doc.get('file_size', 0) for doc in documents)
        
        # Group by document type
        by_type = {}
        for doc in documents:
            doc_type = doc.get('document_type', 'unknown')
            if doc_type not in by_type:
                by_type[doc_type] = {'count': 0, 'size': 0}
            by_type[doc_type]['count'] += 1
            by_type[doc_type]['size'] += doc.get('file_size', 0)
        
        # Group by hour
        by_hour = {}
        for doc in documents:
            created_at = datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00'))
            hour_key = created_at.strftime('%Y-%m-%d %H:00')
            if hour_key not in by_hour:
                by_hour[hour_key] = 0
            by_hour[hour_key] += 1
        
        return {
            'period_hours': hours,
            'total_documents': total_documents,
            'total_size_mb': total_size / (1024 * 1024),
            'average_size_mb': (total_size / total_documents / (1024 * 1024)) if total_documents > 0 else 0,
            'by_type': by_type,
            'by_hour': by_hour,
            'rate_per_hour': total_documents / hours if hours > 0 else 0
        }
    
    async def get_processing_queue_status(self) -> Dict:
        """
        Get status of document processing queue
        
        Returns:
            Dictionary with queue status
        """
        # Get documents by processing status
        pending = self.supabase.table('documents').select(
            'id', count='exact'
        ).eq('processing_status', 'pending').execute()
        
        processing = self.supabase.table('documents').select(
            'id', count='exact'
        ).eq('processing_status', 'processing').execute()
        
        completed = self.supabase.table('documents').select(
            'id', count='exact'
        ).eq('processing_status', 'completed').execute()
        
        failed = self.supabase.table('documents').select(
            'id', count='exact'
        ).eq('processing_status', 'failed').execute()
        
        return {
            'pending': pending.count if pending.count else 0,
            'processing': processing.count if processing.count else 0,
            'completed': completed.count if completed.count else 0,
            'failed': failed.count if failed.count else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_search_analytics(self, hours: int = 24) -> Dict:
        """
        Get search query analytics
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with search analytics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get queries from query_log
        result = self.supabase.table('query_log').select(
            'query_text, results_count, execution_time_ms, created_at'
        ).gte(
            'created_at', cutoff_time.isoformat()
        ).execute()
        
        queries = result.data if result.data else []
        
        total_queries = len(queries)
        
        if total_queries == 0:
            return {
                'period_hours': hours,
                'total_queries': 0,
                'average_execution_time_ms': 0,
                'average_results': 0,
                'queries_per_hour': 0
            }
        
        # Calculate stats
        total_execution_time = sum(q.get('execution_time_ms', 0) for q in queries)
        total_results = sum(q.get('results_count', 0) for q in queries)
        
        return {
            'period_hours': hours,
            'total_queries': total_queries,
            'average_execution_time_ms': total_execution_time / total_queries,
            'average_results': total_results / total_queries,
            'queries_per_hour': total_queries / hours,
            'slowest_queries': sorted(
                queries,
                key=lambda x: x.get('execution_time_ms', 0),
                reverse=True
            )[:5]
        }
    
    async def get_storage_stats(self) -> Dict:
        """
        Get storage statistics
        
        Returns:
            Dictionary with storage stats
        """
        # Get document stats
        docs_result = self.supabase.table('documents').select(
            'file_size', count='exact'
        ).execute()
        
        total_documents = docs_result.count if docs_result.count else 0
        total_size = sum(
            doc.get('file_size', 0) for doc in (docs_result.data or [])
        )
        
        # Get chunks stats
        chunks_result = self.supabase.table('chunks').select(
            'id', count='exact'
        ).execute()
        
        total_chunks = chunks_result.count if chunks_result.count else 0
        
        # Get cases stats
        cases_result = self.supabase.table('cases').select(
            'id', count='exact'
        ).execute()
        
        total_cases = cases_result.count if cases_result.count else 0
        
        return {
            'documents': {
                'count': total_documents,
                'total_size_mb': total_size / (1024 * 1024),
                'total_size_gb': total_size / (1024 * 1024 * 1024),
                'average_size_mb': (total_size / total_documents / (1024 * 1024)) if total_documents > 0 else 0
            },
            'chunks': {
                'count': total_chunks,
                'average_per_document': total_chunks / total_documents if total_documents > 0 else 0
            },
            'cases': {
                'count': total_cases
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_health_dashboard(self) -> Dict:
        """
        Get comprehensive health dashboard
        
        Returns:
            Dictionary with all health metrics
        """
        return {
            'environment': await self.validate_environment(),
            'system': await self.get_system_metrics(),
            'ingestion': await self.get_ingestion_stats(24),
            'processing_queue': await self.get_processing_queue_status(),
            'search': await self.get_search_analytics(24),
            'storage': await self.get_storage_stats(),
            'timestamp': datetime.utcnow().isoformat()
        }


# Global instance
if supabase:
    admin_console = AdminConsole()
else:
    admin_console = None
