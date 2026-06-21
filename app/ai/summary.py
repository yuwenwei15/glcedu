"""AI 新闻总结服务：调用 OpenAI 兼容接口生成新闻摘要。

结果缓存到 Article.ai_summary，避免重复消耗 token。
"""
import re
from datetime import datetime

from flask import current_app

from app import db
from app.models import Article


def _build_client():
    from openai import OpenAI

    return OpenAI(
        api_key=current_app.config['AI_API_KEY'],
        base_url=current_app.config['AI_BASE_URL'],
        timeout=current_app.config['AI_TIMEOUT'],
    )


def _strip_html(text):
    """去掉 HTML 标签与多余空白，给模型喂纯文本。"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _truncate(text, limit=4000):
    """控制送入模型的正文长度，避免超长。"""
    if not text:
        return ''
    return text[:limit]


def _build_prompt(article):
    body = _truncate(_strip_html(article.content or article.summary or ''), 4000)
    title = article.title or ''
    return (
        '你是一名校园新闻编辑助理。请阅读下面这篇校园新闻，输出一段 150 字以内的中文总结。'
        '要求：客观、信息密度高、不要使用「本文」「该新闻」之类的空话，'
        '不要分点，直接给出可读的整段摘要。\n\n'
        f'标题：{title}\n\n正文：\n{body}'
    )


def generate_summary(article):
    """为指定文章生成 AI 总结并写回数据库。返回总结文本。

    失败时抛出异常，由调用方决定如何反馈给前端。
    """
    if not current_app.config.get('AI_API_KEY'):
        raise RuntimeError('未配置 AI_API_KEY，无法生成总结')

    client = _build_client()
    prompt = _build_prompt(article)

    resp = client.chat.completions.create(
        model=current_app.config['AI_MODEL'],
        temperature=current_app.config['AI_TEMPERATURE'],
        max_tokens=current_app.config['AI_MAX_TOKENS'],
        messages=[{'role': 'user', 'content': prompt}],
    )
    msg = resp.choices[0].message
    summary = (msg.content or '').strip()
    if not summary:
        reasoning = getattr(msg, 'reasoning', None) or ''
        summary = reasoning.strip().split('\n')[-1].strip()
    if not summary:
        raise RuntimeError('AI 返回了空内容（可能 max_tokens 不足，模型思考被截断）')

    article.ai_summary = summary
    article.ai_summary_at = datetime.now()
    db.session.commit()
    return summary


def get_or_generate(article):
    """有缓存则直接返回，无则生成。返回 (summary, is_cached)。"""
    if article.ai_summary:
        return article.ai_summary, True
    return generate_summary(article), False
