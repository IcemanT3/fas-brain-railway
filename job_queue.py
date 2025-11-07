"""
job_queue.py - Async Job Queue for Document Processing
Implements in-process job queue with background worker thread
"""

import threading
import queue
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
import traceback


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


@dataclass
class Job:
    """Represents a background processing job"""
    id: str
    type: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    progress_message: str = ""
    error: Optional[str] = None
    result: Optional[Dict] = None
    params: Dict = field(default_factory=dict)


class JobQueue:
    """
    In-process job queue with background worker thread.
    Implements backpressure and rate limiting.
    """
    
    def __init__(self, max_queue_size: int = 100, max_concurrent: int = 3):
        self.max_queue_size = max_queue_size
        self.max_concurrent = max_concurrent
        
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._jobs: Dict[str, Job] = {}
        self._jobs_lock = threading.Lock()
        self._running_count = 0
        self._running_lock = threading.Lock()
        
        self._workers = []
        self._shutdown = False
        self._handlers: Dict[str, Callable] = {}
        
    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler function for a job type"""
        self._handlers[job_type] = handler
        
    def start_workers(self, num_workers: int = 3):
        """Start background worker threads"""
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"JobWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
            
    def enqueue(self, job_type: str, params: Dict) -> str:
        """
        Enqueue a new job for processing.
        
        Returns:
            job_id: Unique identifier for the job
            
        Raises:
            queue.Full: If queue is at capacity (backpressure)
        """
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            type=job_type,
            status=JobStatus.QUEUED,
            created_at=datetime.utcnow(),
            params=params
        )
        
        with self._jobs_lock:
            self._jobs[job_id] = job
            
        try:
            # Non-blocking put with timeout
            self._queue.put(job_id, block=False)
        except queue.Full:
            with self._jobs_lock:
                del self._jobs[job_id]
            raise queue.Full("Job queue is full - try again later")
            
        return job_id
        
    def get_status(self, job_id: str) -> Optional[Job]:
        """Get current status of a job"""
        with self._jobs_lock:
            return self._jobs.get(job_id)
            
    def get_queue_depth(self) -> int:
        """Get number of jobs waiting in queue"""
        return self._queue.qsize()
        
    def get_running_count(self) -> int:
        """Get number of currently running jobs"""
        with self._running_lock:
            return self._running_count
            
    def _worker_loop(self):
        """Background worker thread loop"""
        while not self._shutdown:
            try:
                # Wait for job with timeout to allow shutdown
                job_id = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            # Check concurrent limit
            with self._running_lock:
                while self._running_count >= self.max_concurrent:
                    time.sleep(0.5)
                self._running_count += 1
                
            try:
                self._process_job(job_id)
            finally:
                with self._running_lock:
                    self._running_count -= 1
                self._queue.task_done()
                
    def _process_job(self, job_id: str):
        """Process a single job"""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
                
        # Update status to RUNNING
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        try:
            # Get handler for job type
            handler = self._handlers.get(job.type)
            if not handler:
                raise Exception(f"No handler registered for job type: {job.type}")
                
            # Execute handler with progress callback
            def update_progress(progress: float, message: str = ""):
                job.progress = progress
                job.progress_message = message
                
            result = handler(job.params, update_progress)
            
            # Mark as done
            job.status = JobStatus.DONE
            job.completed_at = datetime.utcnow()
            job.progress = 1.0
            job.result = result
            
        except Exception as e:
            # Mark as error
            job.status = JobStatus.ERROR
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            job.progress_message = traceback.format_exc()
            
    def shutdown(self):
        """Shutdown the job queue and wait for workers"""
        self._shutdown = True
        for worker in self._workers:
            worker.join(timeout=5.0)


# Global job queue instance
job_queue = JobQueue(max_queue_size=100, max_concurrent=3)
