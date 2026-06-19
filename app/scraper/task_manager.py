import threading
import uuid
from datetime import datetime


class TaskManager:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()

    def submit(self, fn, *args, **kwargs):
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = {
                'status': 'running',
                'started_at': datetime.now().isoformat(),
                'finished_at': None,
                'result': None,
                'error': None,
            }

        def wrapper():
            try:
                result = fn(*args, **kwargs)
                with self._lock:
                    self._tasks[task_id]['status'] = 'success'
                    self._tasks[task_id]['result'] = result
            except Exception as e:
                with self._lock:
                    self._tasks[task_id]['status'] = 'failed'
                    self._tasks[task_id]['error'] = str(e)
            finally:
                with self._lock:
                    self._tasks[task_id]['finished_at'] = datetime.now().isoformat()

        t = threading.Thread(target=wrapper, daemon=True)
        t.start()
        return task_id

    def get(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def cleanup(self, max_age_seconds=3600):
        now = datetime.now()
        with self._lock:
            expired = [
                tid for tid, t in self._tasks.items()
                if t['finished_at'] and
                (now - datetime.fromisoformat(t['finished_at'])).total_seconds() > max_age_seconds
            ]
            for tid in expired:
                del self._tasks[tid]


task_manager = TaskManager()
