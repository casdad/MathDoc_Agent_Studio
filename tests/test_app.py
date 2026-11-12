from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from server import app, count_docx_equations, parse_markdown, html_preview, safe_ast, url_for_endpoint

cli = TestClient(app)
SOURCE = r'''# 模型设计

定义损失 $L=\alpha x^2+\beta$。

$$\mathcal{L}=\frac{1}{n}\sum_{i=1}^{n} (y_i-\hat y_i)^2$$

$$A=\begin{bmatrix}1&2\\3&4\end{bmatrix}$$

| 项 | 值 |
|---|---|
| a | $x_i$ |
'''


def test_preview_mathml_and_table():
    r=cli.post('/api/preview',json={'content':SOURCE})
    assert r.status_code==200, r.text
    data=r.json()
    assert len(data['formulas'])==4
    assert data['html'].count('<math')==4
    assert '<table>' in data['html']
    assert '<mfrac>' in data['html']


def test_native_omml_docx():
    r=cli.post('/api/export',json={'content':SOURCE,'title':'中文测试'})
    assert r.status_code==200, r.text
    assert r.headers['x-equation-count']=='4'
    assert count_docx_equations(r.content)==4
    with ZipFile(BytesIO(r.content)) as z:
        assert b'<m:oMath' in z.read('word/document.xml')


def test_sanitizer_prevents_xss_and_file_images():
    raw='''<script>alert(1)</script>\n\n![secret](/etc/passwd)\n\n[run](javascript:alert(1))\n\n$x^2$'''
    r=cli.post('/api/preview',json={'content':raw})
    assert r.status_code==200, r.text
    h=r.json()['html']
    assert '<script>' not in h
    assert 'javascript:' not in h
    assert '/etc/passwd' not in h
    assert '<math' in h


def test_url_contract():
    assert url_for_endpoint('https://api.openai.com/v1','chat/completions').endswith('/v1/chat/completions')
    assert url_for_endpoint('http://127.0.0.1:1234/v1','chat/completions').endswith('/v1/chat/completions')


def test_requires_input():
    assert cli.post('/api/export',json={'content':'','title':'x'}).status_code==400


def test_agent_openai_compatible(monkeypatch):
    import httpx
    async def mock_post(self, url, json, headers):
        req=httpx.Request('POST', url)
        return httpx.Response(200,json={'choices':[{'message':{'content':'# 处理完成\n\n$E=mc^2$'}}]},request=req)
    monkeypatch.setattr(httpx.AsyncClient, 'post', mock_post)
    r=cli.post('/api/agent',json={'content':'原文 $E=mc^2$','api_key':'test-only','model':'fake-model','base_url':'https://mock.example/v1'})
    assert r.status_code==200, r.text
    assert 'E=mc^2' in r.json()['content']


def test_config_roundtrip_and_masking(tmp_path, monkeypatch):
    import server
    monkeypatch.setattr(server, 'CONFIG_PATH', tmp_path / 'config.json')
    r=cli.post('/api/config',json={'base_url':'https://api.deepseek.com/v1','model':'deepseek-chat','provider':'deepseek','api_key':'sk-secret-123456'})
    assert r.status_code==200, r.text
    body=r.json()
    assert body['configured'] and body['api_key_set']
    assert 'sk-secret-123456' not in r.text
    assert (tmp_path / 'config.json').exists()
    got=cli.get('/api/config')
    assert got.status_code==200
    assert got.json()['base_url']=='https://api.deepseek.com/v1'
    assert 'sk-secret-123456' not in got.text
    assert cli.delete('/api/config').json()['deleted'] is True
    assert not (tmp_path / 'config.json').exists()


def test_config_rejects_bad_base_url(tmp_path, monkeypatch):
    import server
    monkeypatch.setattr(server, 'CONFIG_PATH', tmp_path / 'config.json')
    r=cli.post('/api/config',json={'base_url':'ftp://example.com','model':'x','api_key':'k'})
    assert r.status_code==400
    assert not (tmp_path / 'config.json').exists()


def test_agent_falls_back_to_saved_config(tmp_path, monkeypatch):
    import httpx, server
    monkeypatch.setattr(server, 'CONFIG_PATH', tmp_path / 'config.json')
    cli.post('/api/config',json={'base_url':'https://mock.example/v1','model':'saved-model','api_key':'saved-key'})
    seen={}
    async def mock_post(self, url, json, headers):
        seen['auth']=headers.get('Authorization');seen['model']=json['model']
        req=httpx.Request('POST', url)
        return httpx.Response(200,json={'choices':[{'message':{'content':'ok'}}]},request=req)
    monkeypatch.setattr(httpx.AsyncClient, 'post', mock_post)
    r=cli.post('/api/agent',json={'content':'原文'})
    assert r.status_code==200, r.text
    assert seen=={'auth':'Bearer saved-key','model':'saved-model'}
