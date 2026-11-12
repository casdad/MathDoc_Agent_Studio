"""MathDoc Agent Studio — local Markdown/LaTeX → Word pipeline.

API credentials are persisted to config.json only when the user saves them.
Agent requests go only to the configured OpenAI-compatible endpoint. Exports
are deterministic and do not call an LLM.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import bleach
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
PANDOC = shutil.which('pandoc')
READER = 'markdown-raw_html-raw_tex+tex_math_dollars+tex_math_single_backslash+pipe_tables+grid_tables+fenced_code_blocks'
MAX_CHARS = 180_000
MATH_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
CONFIG_PATH = ROOT / 'config.json'
CONFIG_FIELDS = ('provider', 'base_url', 'model', 'api_key')

app = FastAPI(title='MathDoc Agent Studio', version='1.0.0')


def load_config() -> dict:
    """Read config.json, tolerating a missing or hand-edited broken file."""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: raw[k].strip() for k in CONFIG_FIELDS
            if isinstance(raw.get(k), str) and raw[k].strip()}


def save_config(values: dict) -> None:
    """Merge known fields into config.json with an atomic replace."""
    data = load_config()
    data.update({k: v for k, v in values.items() if k in CONFIG_FIELDS})
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, CONFIG_PATH)
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass


def mask_key(key: str) -> str:
    return f'{key[:4]}…{key[-4:]}' if len(key) > 8 else ('****' if key else '')


def config_summary() -> dict:
    """Config details safe to return to the browser: the key is never echoed."""
    cfg = load_config()
    key = cfg.get('api_key', '')
    return {
        'configured': bool(key or cfg.get('base_url')),
        'provider': cfg.get('provider', ''),
        'base_url': cfg.get('base_url', ''),
        'model': cfg.get('model', ''),
        'api_key_set': bool(key),
        'api_key_hint': mask_key(key),
        'path': CONFIG_PATH.name,
    }


class Source(BaseModel):
    content: str = Field(min_length=0, max_length=MAX_CHARS)


class ExportRequest(Source):
    title: str = Field(default='MathDoc 论文', max_length=120)


class AgentRequest(Source):
    base_url: str = Field(default='', max_length=500)
    model: str = Field(default='', max_length=160)
    api_key: str = Field(default='', max_length=800)
    mode: str = Field(default='preserve')
    custom_instruction: str = Field(default='', max_length=2000)


class ModelsRequest(BaseModel):
    base_url: str = ''
    api_key: str = ''


class ConfigRequest(BaseModel):
    base_url: str = Field(default='', max_length=500)
    model: str = Field(default='', max_length=160)
    provider: str = Field(default='openai', max_length=40)
    api_key: str | None = Field(default=None, max_length=800)


def require_pandoc():
    if not PANDOC:
        raise HTTPException(status_code=503, detail='未检测到 Pandoc，请安装后重新启动。')


def pandoc(arguments: list[str], stdin: str, timeout: int = 35) -> tuple[str, str]:
    require_pandoc()
    cmd = [PANDOC, *arguments]
    try:
        proc = subprocess.run(cmd, input=stdin, text=True, encoding='utf-8',
                              errors='replace', capture_output=True, timeout=timeout,
                              cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail='Pandoc 转换超时。')
    if proc.returncode != 0:
        raise HTTPException(status_code=422, detail=f'Pandoc 转换失败：{proc.stderr[-700:]}')
    return proc.stdout, proc.stderr


def safe_ast(node):
    """Remove images/raw nodes; prohibit local file fetches and unsafe links."""
    if isinstance(node, list):
        return [safe_ast(item) for item in node]
    if not isinstance(node, dict):
        return node
    tag = node.get('t')
    if tag == 'Image':
        return {'t': 'Str', 'c': '[图片已省略：为安全起见不读取本地/远程图片]'}
    if tag in {'RawInline', 'RawBlock'}:
        return {'t': 'Str', 'c': '[已省略原始嵌入内容]'} if tag == 'RawInline' else {'t': 'Para', 'c': [{'t': 'Str', 'c': '[已省略原始嵌入内容]'}]}
    if tag == 'Link':
        c = node.get('c', [])
        if len(c) == 3:
            href = c[2][0]
            target = urlsplit(href)
            if target.scheme and target.scheme not in {'https', 'http', 'mailto'}:
                return {'t': 'Span', 'c': [['', [], []], safe_ast(c[1])]}
            if not target.scheme and not href.startswith(('#', '/', './')):
                return {'t': 'Span', 'c': [['', [], []], safe_ast(c[1])]}
    return {k: safe_ast(v) for k, v in node.items()}


def formulas_in_ast(obj) -> list[dict]:
    result = []
    def walk(n):
        if isinstance(n, list):
            for x in n: walk(x)
        elif isinstance(n, dict):
            if n.get('t') == 'Math':
                c = n.get('c', [])
                if len(c) == 2:
                    result.append({'number': len(result)+1, 'kind': c[0].get('t', 'InlineMath'), 'tex': c[1]})
            else:
                for v in n.values(): walk(v)
    walk(obj.get('blocks', []))
    return result


def parse_markdown(content: str):
    ast_text, parsing_warnings = pandoc(['-f', READER, '-t', 'json'], content)
    ast = safe_ast(json.loads(ast_text))
    math = formulas_in_ast(ast)
    return json.dumps(ast, ensure_ascii=False), math, parsing_warnings


TAGS = {
    'p','div','span','a','strong','em','b','i','s','u','blockquote','br','hr','pre','code','ol','ul','li',
    'h1','h2','h3','h4','h5','h6','table','thead','tbody','tfoot','tr','td','th','caption','sup','sub',
    'math','semantics','mrow','mi','mn','mo','msup','msub','msubsup','mfrac','msqrt','mroot','mover',
    'munder','munderover','mtable','mtr','mtd','mtext','mspace','mfenced','menclose','annotation',
    'mmultiscripts','mprescripts','none','mpadded','mphantom','maligngroup','mlabeledtr','mstyle',
    'ms','maction','mglyph'
}
ATTRS = {
    '*': ['class', 'id', 'title'],
    'a': ['href','title'],
    'math': ['display','xmlns','alttext'],
    'annotation': ['encoding'],
    'mspace':['width','height','depth'],
    'mo':['stretchy','fence','separator','lspace','rspace','form'],
    'mstyle':['displaystyle','scriptlevel','mathcolor','mathsize'],
    'mtd':['columnspan','rowspan','columnalign','rowalign'],
    'mtable':['columnalign','rowalign','columnspacing','rowspacing','frame'],
    'mi':['mathvariant'],
    'mtext':['mathvariant'],
}


def html_preview(ast_json: str):
    raw, warn = pandoc(['-f', 'json', '-t', 'html5', '--mathml'], ast_json)
    safe = bleach.clean(raw, tags=TAGS, attributes=ATTRS, protocols=['https','http','mailto'], strip=True)
    return safe, warn


def count_docx_equations(payload: bytes) -> int:
    from io import BytesIO
    with ZipFile(BytesIO(payload)) as z:
        doc = ET.fromstring(z.read('word/document.xml'))
    return len(doc.findall(f'.//{{{MATH_NS}}}oMath'))


def docx_bytes(ast_json: str):
    template = ROOT / 'templates' / 'reference.docx'
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / 'result.docx'
        cmd = [PANDOC, '-f', 'json', '-t', 'docx', '--wrap=none', '-o', str(dst)]
        if template.exists():
            cmd.extend(['--reference-doc', str(template)])
        _, warnings = pandoc(cmd[1:], ast_json, timeout=60)
        return dst.read_bytes(), warnings


def url_for_endpoint(base_url: str, endpoint: str) -> str:
    base_url = base_url.strip().rstrip('/')
    parsed = urlsplit(base_url)
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail='API Base URL 必须是有效的 http(s) 地址，且不能包含用户名或密码。')
    if parsed.query or parsed.fragment:
        raise HTTPException(status_code=400, detail='API Base URL 不能包含查询参数或片段。')
    if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise HTTPException(status_code=400, detail='远程 API 必须使用 HTTPS；HTTP 仅允许本机模型服务。')
    if base_url.endswith('/chat/completions'):
        base_url = base_url[:-len('/chat/completions')]
    if base_url.endswith('/models'):
        base_url = base_url[:-len('/models')]
    return f'{base_url}/{endpoint.lstrip("/")}'


@app.get('/api/health')
def health():
    return {'ok': True, 'pandoc': bool(PANDOC), 'version': '1.0.0'}


@app.get('/api/config')
def get_config():
    return config_summary()


@app.post('/api/config')
def put_config(request: ConfigRequest):
    base_url = request.base_url.strip()
    model = request.model.strip()
    if not base_url or not model:
        raise HTTPException(status_code=400, detail='API 地址与模型 ID 不能为空。')
    url_for_endpoint(base_url, 'chat/completions')  # validate before saving
    values = {'base_url': base_url, 'model': model,
              'provider': request.provider.strip() or 'openai'}
    if request.api_key is not None:
        values['api_key'] = request.api_key.strip()
    save_config(values)
    return config_summary()


@app.delete('/api/config')
def delete_config():
    try:
        CONFIG_PATH.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f'删除配置文件失败：{exc}')
    return {**config_summary(), 'deleted': True}


@app.post('/api/preview')
def preview(request: Source):
    if not request.content.strip():
        return {'html': '<p class="placeholder">处理后的内容会在这里显示。</p>', 'formulas': [], 'warnings': []}
    ast_json, formulas, warnings1 = parse_markdown(request.content)
    html, warnings2 = html_preview(ast_json)
    errs = [x.strip() for x in (warnings1, warnings2) if x.strip()]
    count_html = len(re.findall(r'<math(?:\s|>)', html))
    if count_html != len(formulas):
        errs.append(f'公式检查：源文档 {len(formulas)} 条，预览呈现 {count_html} 条。')
    return {'html': html, 'formulas': formulas, 'warnings': errs}


@app.post('/api/export')
def export(request: ExportRequest):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail='没有可以导出的内容。')
    require_pandoc()
    ast_json, formulas, _ = parse_markdown(request.content)
    doc, conversion_warnings = docx_bytes(ast_json)
    num = count_docx_equations(doc)
    if num != len(formulas):
        raise HTTPException(status_code=422, detail=f'OMML 检查失败：输入公式 {len(formulas)} 条，输出原生公式 {num} 条。未提供不完整文件。')
    # Pandoc may warn about unsupported TeX despite emitting an OMML placeholder.
    # A visible warning header ensures the caller does not mistake this for full semantic proof.
    from urllib.parse import quote
    filename = re.sub(r'[\\/:*?"<>|\r\n]', '_', request.title).strip() or 'MathDoc'
    headers = {'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}.docx",
               'X-Equation-Count': str(num), 'X-Conversion-Warning': '1' if conversion_warnings else '0'}
    return Response(content=doc, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', headers=headers)


SYSTEM_PRESERVE = '''你是科研文档排版智能体。请将用户输入规整为结构清晰、可被 Pandoc 解析的 Markdown，输出 ONLY Markdown。
绝不能更改公式的数学含义、变量、系数、数据、引用或结论。保留全部有效内容与段落顺序；纠正明显的 Markdown 格式问题。
行内公式使用 $...$，独立公式使用 $$...$$。不要用 ```latex 包裹数学公式。禁止臆造论证或修改推导。对无法确定的公式原样保留。'''
SYSTEM_POLISH = '''你是科研论文排版与文字润色智能体。请把用户输入整理为可被 Pandoc 解析的清晰 Markdown，输出 ONLY Markdown。
可以改善中文语言表达与段落结构，但不得改变事实、数据、数学公式语义及引用。不得虚构研究结果和新结论。
行内公式使用 $...$，独立公式使用 $$...$$，保持公式原文和上下标含义。不要使用 ```latex 代码块表示公式。'''


@app.post('/api/agent')
async def agent(request: AgentRequest):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail='请输入需要处理的内容。')
    cfg = load_config()
    base_url = request.base_url.strip() or cfg.get('base_url', '')
    model = request.model.strip() or cfg.get('model', '')
    api_key = request.api_key.strip() or cfg.get('api_key', '')
    if not base_url or not model:
        raise HTTPException(status_code=400, detail='请先配置 API 地址和模型 ID。')
    url = url_for_endpoint(base_url, 'chat/completions')
    prompt = SYSTEM_POLISH if request.mode == 'polish' else SYSTEM_PRESERVE
    if request.custom_instruction.strip():
        prompt += '\n补充排版要求：' + request.custom_instruction.strip()
    body = {'model': model, 'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': request.content}
    ], 'stream': False}
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=12.0), follow_redirects=False, trust_env=False) as client:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        # No exception body or full URL is reflected to avoid accidental token leakage.
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        raise HTTPException(status_code=502, detail=(f'模型服务返回 HTTP {status}，请核对模型、Key、额度或兼容协议。' if status else '连接模型服务失败，请检查 API 地址和网络。'))
    try:
        value = data['choices'][0]['message']['content']
        if isinstance(value, list):
            value = ''.join(part.get('text','') for part in value if part.get('type') == 'text')
        if not isinstance(value,str) or not value.strip():
            raise ValueError('empty')
    except (TypeError,KeyError,IndexError,ValueError):
        raise HTTPException(status_code=502, detail='模型响应不符合 OpenAI Chat Completions 格式，或模型未返回文本。')
    value = value.strip()
    if value.startswith('```markdown') and value.endswith('```'):
        value = re.sub(r'^```markdown\s*|\s*```$', '', value, flags=re.I).strip()
    return {'content': value, 'model': model}


@app.post('/api/models')
async def models(request: ModelsRequest):
    cfg = load_config()
    base_url = request.base_url.strip() or cfg.get('base_url', '')
    api_key = request.api_key.strip() or cfg.get('api_key', '')
    if not base_url:
        raise HTTPException(status_code=400, detail='请先填写 API Base URL。')
    url = url_for_endpoint(base_url, 'models')
    h = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as c:
            r = await c.get(url,headers=h)
            r.raise_for_status()
            data = r.json()
        values = [o['id'] for o in data.get('data',[]) if isinstance(o,dict) and isinstance(o.get('id'),str)]
        return {'models': sorted(values)[:300]}
    except Exception:
        raise HTTPException(status_code=502,detail='该服务暂不支持模型列表查询；可直接手动填写模型 ID。')


@app.get('/')
def index():
    # Local UI is edited in place; never let the browser keep a stale shell.
    return FileResponse(ROOT / 'static' / 'index.html',
                        headers={'Cache-Control': 'no-store'})

app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
