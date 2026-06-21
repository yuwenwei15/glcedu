from functools import wraps

from flask import request, jsonify, current_app


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 仅认请求头，不从 URL query 取：令牌进 URL 会被 access log / 浏览器历史 / 代理记录
        token = request.headers.get('X-Admin-Token', '')
        if not token or token != current_app.config['ADMIN_TOKEN']:
            return jsonify({'success': False, 'message': '未授权访问'}), 401
        return f(*args, **kwargs)
    return decorated
