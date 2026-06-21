"""轻量级进程内限流：用于给「会花钱/重操作」的接口（如 AI 摘要生成）兜底，
防止被脚本循环刷爆烧 token。

实现为按 key 的滑动窗口计数。注意：状态在进程内存里，多 worker 部署时
每个进程各自计数（与 task_manager 同样的取舍），仅作滥用兜底，非精确配额。
若部署在反向代理后，request.remote_addr 是代理 IP，需配 ProxyFix / 用
X-Forwarded-For 才能按真实客户端区分。
"""
import time
import threading
from functools import wraps

from flask import request, jsonify


class RateLimiter:
    def __init__(self):
        self._hits = {}  # key -> [timestamp, ...]
        self._lock = threading.Lock()

    def allow(self, key, limit, window):
        """window 秒内最多 limit 次。命中返回 True，超限返回 False。"""
        now = time.time()
        with self._lock:
            bucket = [t for t in self._hits.get(key, []) if now - t < window]
            if len(bucket) >= limit:
                self._hits[key] = bucket
                return False
            bucket.append(now)
            self._hits[key] = bucket
            return True


_limiter = RateLimiter()


def allow(name, limit, window):
    """直接判定：当前请求 IP 在 window 秒内对 name 的调用是否仍在 limit 内。

    用于只想限流「部分代码路径」（如缓存未命中才生成）而非整个接口的场景。
    """
    client = request.remote_addr or 'anon'
    return _limiter.allow(f'{name}:{client}', limit, window)


def rate_limit(limit, window):
    """每个客户端 IP 在 window 秒内最多调用 limit 次，超出返回 429。"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            client = request.remote_addr or 'anon'
            key = f'{f.__name__}:{client}'
            if not _limiter.allow(key, limit, window):
                return jsonify({
                    'success': False,
                    'message': '请求过于频繁，请稍后再试',
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator
