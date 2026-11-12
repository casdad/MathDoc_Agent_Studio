'use strict';
const $ = id => document.getElementById(id);
const state = {apiKey:'',baseUrl:'https://api.openai.com/v1',model:'gpt-4.1-mini',provider:'openai',savedKeyHint:'',configPath:'config.json',html:'',equations:[],warnings:[],busy:false,renderToken:0};
const notes = {
 omml:'OMML 是 DOCX 内部的原生数学格式。浏览器「复制富文本」会包含 MathML，能保留大部分文字样式，但不保证 Word 识别成原生公式；要确保可编辑请点击「导出 DOCX」。',
 mathtype:'MathType 是公式编辑器，不是与 OMML 并列的单一开放文件格式。本模式可将公式复制为 LaTeX，适合粘贴到 MathType 的 TeX 输入区；不会生成 MathType 专有 OLE 对象。',
 mathml:'MathML 是公式交换格式。本模式「复制所选公式」输出 MathML 源码，适用于支持 MathML 的编辑器；Word 对浏览器 MathML 剪贴板的支持依版本而异。'
};
let toastTimer=0, debounceTimer=0;
function toast(text, bad=false){const x=$('toast');x.textContent=text;x.classList.toggle('error',bad);x.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>x.classList.remove('show'),3600);}
function setStatus(text,bad=false){$('status-message').innerHTML='';const d=document.createElement('span');d.className='status-dot';d.style.background=bad?'#c85059':'#31a56b';$('status-message').append(d, document.createTextNode(text));}
async function api(path,payload,format='json'){
 const res=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 if(!res.ok){let err='请求失败（HTTP '+res.status+'）';try{let j=await res.json();err=j.detail||err;}catch(e){}throw new Error(err);}
 if(format==='blob')return await res.blob();return await res.json();
}
function syncStats(){ $('source-stat').textContent=$('source').value.length.toLocaleString()+' 字符';$('processed-stat').textContent=$('processed').value.length.toLocaleString()+' 字符'; }
function setBusy(x){state.busy=x;$('agent-btn').disabled=x;$('direct-btn').disabled=x;$('export-btn').disabled=x;$('agent-btn').textContent=x?'◌ 正在处理…':'✦ Agent 智能处理';}
function direct(){ $('processed').value=$('source').value;syncStats();render();setStatus('已直接排版（未使用 AI）'); }
function applySample(){const s=`# 研究方法与数学定义

## 1. 问题定义

设训练样本为 $\\mathcal{D}=\\{(x_i,y_i)\\}_{i=1}^{n}$，希望最小化经验风险：

$$
\\mathcal{L}_{\\mathrm{total}}=\\frac{1}{n}\\sum_{i=1}^{n}\\ell(f_{\\theta}(x_i),y_i)+\\lambda\\lVert\\theta\\rVert_2^2
$$

这里 $\\lambda>0$ 是正则化系数，$\\theta$ 表示模型参数。

## 2. 矩阵与分段函数

$$
A=\\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}
$$

$$
f(x)=\\begin{cases} x^2, & x\\geq 0 \\\\ -x, & x<0 \\end{cases}
$$

## 3. 对比结果

| 方法 | MAE ↓ | Pearson ↑ |
|:---|---:|---:|
| Baseline | 0.615 | 0.621 |
| Proposed | **0.602** | **0.639** |

**注：** 表中的数字仅为软件测试示例，不是实际实验结果。`;
 $('source').value=s;$('processed').value=s;syncStats();render();toast('已载入包含公式和表格的演示文档');}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function render(){const token=++state.renderToken,content=$('processed').value;syncStats();if(!content.trim()){state.html='';state.equations=[];$('preview').innerHTML='<div class="preview-placeholder"><span class="placeholder-icon">ƒ(x)</span><h2>你的文档将在这里呈现</h2><p>左侧输入内容后，点击直接排版或 Agent 智能处理。</p></div>';$('preview-state').textContent='无内容';updateEquations();return;}
 $('preview-state').textContent='解析中…';try{const data=await api('preview',{content});if(token!==state.renderToken)return;state.html=data.html;state.equations=data.formulas;state.warnings=data.warnings;$('preview').innerHTML=data.html;$('preview-state').textContent='已渲染';updateEquations();if(data.warnings.length)setStatus('转换完成，存在 '+data.warnings.length+' 条诊断提醒',true);}catch(e){if(token!==state.renderToken)return;$('preview').textContent='预览失败：'+e.message;$('preview-state').textContent='失败';setStatus(e.message,true);toast(e.message,true);}}
function updateEquations(){const s=$('formula-item');s.innerHTML='';if(!state.equations.length){s.add(new Option('尚无公式',''));}else{state.equations.forEach((f,i)=>s.add(new Option('#'+(i+1)+'  '+f.tex.slice(0,56),i)));}$('math-count').textContent=state.equations.length+' 条公式';$('warning-count').textContent=state.warnings.length;$('warnings-box').textContent=state.warnings.length?state.warnings.join('\n\n'):'没有来自解析器的警告。注意：公式数量一致不等于语义已验证。';}
async function runAgent(){if(!checkInput())return;if(!state.model||!state.baseUrl){openSettings();toast('请先配置模型服务',true);return;}setBusy(true);setStatus('Agent 正在整理 Markdown 与公式…');$('agent-message').textContent='正在调用 '+state.model;try{const r=await api('agent',{content:$('source').value,api_key:state.apiKey,base_url:state.baseUrl,model:state.model,mode:$('agent-mode').value,custom_instruction:$('custom-instruction').value});$('processed').value=r.content;$('agent-message').textContent='已处理 · '+r.model;setStatus('Agent 处理完成');await render();toast('Agent 已完成处理，右侧已更新');}catch(e){setStatus(e.message,true);$('agent-message').textContent='处理失败（原始文本未改变）';toast(e.message,true);}finally{setBusy(false);}}
function checkInput(){if(!$('source').value.trim()){toast('请先输入原始内容',true);return false;}return true;}
function previewHtmlForClipboard(){const container=document.createElement('div');container.innerHTML=state.html;const inline={h1:'font-size:20pt;font-weight:bold;margin:15pt 0 8pt;',h2:'font-size:15pt;font-weight:bold;margin:13pt 0 7pt;',h3:'font-size:12pt;font-weight:bold;',p:'font-size:11pt;line-height:1.6;margin:7pt 0;',table:'border-collapse:collapse;width:100%;font-size:10.5pt;',td:'border:1px solid #b8bfce;padding:6px 9px;',th:'border:1px solid #8894a4;padding:6px 9px;background:#f3f5f8;font-weight:bold;',strong:'font-weight:700;',em:'font-style:italic;',blockquote:'border-left:3px solid #8eabd3;padding-left:9pt;color:#596a82;'};
 for(const el of container.querySelectorAll('*')){const tag=el.tagName.toLowerCase();if(inline[tag])el.setAttribute('style',inline[tag]);}container.setAttribute('style','font-family:SimSun,宋体,Times New Roman,serif;font-size:11pt;color:#202635;');return container.outerHTML;}
async function clipboard(text,html){try{if(html&&navigator.clipboard&&navigator.clipboard.write){const item=new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})});await navigator.clipboard.write([item]);return true;}if(navigator.clipboard&&navigator.clipboard.writeText){await navigator.clipboard.writeText(text);return !html;}const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();const ok=document.execCommand('copy');t.remove();return ok&&!html;}catch(err){try{await navigator.clipboard.writeText(text);}catch(e){}return false;}}
function mathMarkupForCopy(html,kind){if(kind==='omml'||kind==='mathml')return html;
 const div=document.createElement('div');div.innerHTML=html;
 const math=div.querySelectorAll('math');math.forEach((el,i)=>{const f=state.equations[i];if(!f)return;const span=document.createElement('span');span.textContent=(f.kind==='DisplayMath'?'$$':'\\(')+f.tex+(f.kind==='DisplayMath'?'$$':'\\)');span.style.fontFamily='Consolas,monospace';el.replaceWith(span);});return div.outerHTML;}
async function copyRich(){if(!state.html){toast('右侧没有可复制的排版内容',true);return;}const mode=$('formula-format').value;const html=mathMarkupForCopy(previewHtmlForClipboard(),mode);const ok=await clipboard($('processed').value,html);toast(ok?'已复制富文本，可在 Word 粘贴并检查公式':'已复制文本（富文本剪贴板不可用，请使用导出 DOCX）',!ok);}
async function copyFormula(){const idx=Number($('formula-item').value);if(!state.equations.length||!state.equations[idx]){toast('没有可复制的公式',true);return;}const f=state.equations[idx],mode=$('formula-format').value;let copyText='';if(mode==='mathml'){const math=$('preview').querySelectorAll('math')[idx];copyText=math?math.outerHTML:'<math><mtext>'+escapeHtml(f.tex)+'</mtext></math>';}else{copyText=mode==='omml'?(f.kind==='DisplayMath'?'$$'+f.tex+'$$':'\\('+f.tex+'\\)'):f.tex;}
 try{await navigator.clipboard.writeText(copyText);toast('已复制第 '+(idx+1)+' 条公式的 '+(mode==='mathml'?'MathML':'LaTeX')+' 表示');}catch(e){toast('剪贴板不可用，请使用本机 localhost 地址打开页面',true);}}
async function exportDocx(){const content=$('processed').value;if(!content.trim()){toast('没有可以导出的内容',true);return;}setBusy(true);setStatus('正在生成 Word 与检查原生公式…');try{const title=((content.match(/^#\s+(.+)$/m)||[])[1]||'MathDoc_学术文档').replace(/[\\/:*?"<>|]/g,'_').slice(0,50);const blob=await api('export',{content,title},'blob');const href=URL.createObjectURL(blob);const a=document.createElement('a');a.href=href;a.download=title+'.docx';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),10000);setStatus('DOCX 已生成，OMML 数量已校验；请用 Word 打开检查渲染');toast('已生成 Word 文档（包含可编辑 OMML 公式）');}catch(e){setStatus(e.message,true);toast(e.message,true);}finally{setBusy(false);}}
function updateKeyStatus(){const el=$('key-status');if(!el)return;el.textContent=state.savedKeyHint?'已保存到 '+state.configPath+'：'+state.savedKeyHint+'（输入框留空则沿用）':'尚未保存配置；保存后写入 '+state.configPath;el.classList.toggle('saved',!!state.savedKeyHint);}
async function loadConfig(){try{const r=await fetch('/api/config');if(!r.ok)return;const c=await r.json();state.savedKeyHint=c.api_key_set?(c.api_key_hint||''):'';state.configPath=c.path||'config.json';if(c.base_url)state.baseUrl=c.base_url;if(c.model)state.model=c.model;if(c.provider)state.provider=c.provider;state.apiKey='';$('model-name').textContent=(c.configured&&state.model)?state.model.slice(0,26):'未配置';updateKeyStatus();}catch(e){}}
async function openSettings(){await loadConfig();$('api-base').value=state.baseUrl;$('api-model').value=state.model;$('provider').value=state.provider;$('api-key').value='';$('api-key').placeholder=state.savedKeyHint?'已保存 '+state.savedKeyHint+'，留空沿用':'sk-...';updateKeyStatus();$('settings-modal').classList.remove('hidden');}
function closeSettings(){$('settings-modal').classList.add('hidden');}
async function saveSettings(){const baseUrl=$('api-base').value.trim(),model=$('api-model').value.trim(),provider=$('provider').value,apiKey=$('api-key').value.trim();if(!baseUrl||!model){toast('API 地址与模型 ID 不能为空',true);return;}const payload={base_url:baseUrl,model,provider};if(apiKey)payload.api_key=apiKey;const btn=$('settings-save');btn.disabled=true;try{const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok){let err='保存失败（HTTP '+r.status+'）';try{const j=await r.json();err=j.detail||err;}catch(e){}throw new Error(err);}const c=await r.json();state.baseUrl=baseUrl;state.model=model;state.provider=provider;state.apiKey='';state.savedKeyHint=c.api_key_set?(c.api_key_hint||''):'';$('api-key').value='';$('model-name').textContent=model.slice(0,26);updateKeyStatus();closeSettings();toast('配置已保存到 '+state.configPath);}catch(e){toast(e.message,true);}finally{btn.disabled=false;}}
async function clearConfig(){if(!window.confirm('删除本地配置文件 '+state.configPath+'？删除后需要重新填写 API Key。'))return;try{const r=await fetch('/api/config',{method:'DELETE'});if(!r.ok)throw new Error('删除失败（HTTP '+r.status+'）');state.savedKeyHint='';state.apiKey='';state.baseUrl='https://api.openai.com/v1';state.model='gpt-4.1-mini';state.provider='openai';$('api-key').value='';$('api-base').value=state.baseUrl;$('api-model').value=state.model;$('provider').value=state.provider;$('model-name').textContent='未配置';updateKeyStatus();toast('已删除保存的配置');}catch(e){toast(e.message,true);}}
const presets={openai:{url:'https://api.openai.com/v1',model:'gpt-4.1-mini'},deepseek:{url:'https://api.deepseek.com/v1',model:'deepseek-chat'},local:{url:'http://127.0.0.1:1234/v1',model:'local-model'}};
async function fetchModels(){const base=$('api-base').value.trim();if(!base)return;const btn=$('list-models');btn.disabled=true;try{const r=await api('models',{base_url:base,api_key:$('api-key').value});const sel=$('available-models');sel.innerHTML='<option value="">— 选择 API 返回的模型 —</option>';r.models.forEach(m=>sel.add(new Option(m,m)));sel.classList.remove('hidden');toast('已读取 '+r.models.length+' 个模型');}catch(e){toast(e.message,true);}finally{btn.disabled=false;}}
function updateNote(){$('format-note').lastElementChild.textContent=notes[$('formula-format').value];}
async function init(){try{const res=await fetch('/api/health');const v=await res.json();$('backend-pill').innerHTML='<span class="status-dot"></span> '+(v.pandoc?'本地引擎在线':'需要安装 Pandoc');setStatus(v.pandoc?'本地 Pandoc 转换引擎就绪':'未找到 Pandoc，请安装后重新启动',!v.pandoc);}catch(e){$('backend-pill').textContent='后端未连接';setStatus('本机后端未连接',true);}loadConfig();updateNote();syncStats();}
$('source').addEventListener('input',syncStats);
$('processed').addEventListener('input',()=>{syncStats();clearTimeout(debounceTimer);debounceTimer=setTimeout(render,420);});
$('direct-btn').addEventListener('click',direct);$('agent-btn').addEventListener('click',runAgent);$('sample-btn').addEventListener('click',applySample);
$('clear-btn').addEventListener('click',()=>{$('source').value='';$('processed').value='';syncStats();render();setStatus('已清空');});
$('copy-rich-btn').addEventListener('click',copyRich);$('copy-formula-btn').addEventListener('click',copyFormula);$('export-btn').addEventListener('click',exportDocx);
$('copy-md-btn').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('processed').value);toast('已复制 Markdown 源码');}catch(e){toast('浏览器拒绝访问剪贴板',true);}});
$('formula-format').addEventListener('change',updateNote);$('show-warnings').addEventListener('click',()=>$('warnings-box').classList.toggle('hidden'));
$('settings-open').addEventListener('click',openSettings);$('settings-close').addEventListener('click',closeSettings);$('settings-backdrop').addEventListener('click',closeSettings);$('settings-cancel').addEventListener('click',closeSettings);$('settings-save').addEventListener('click',saveSettings);$('settings-clear').addEventListener('click',clearConfig);
$('provider').addEventListener('change',()=>{const p=presets[$('provider').value];if(p){$('api-base').value=p.url;$('api-model').value=p.model;}});
$('toggle-key').addEventListener('click',()=>{$('api-key').type=$('api-key').type==='password'?'text':'password';$('toggle-key').textContent=$('api-key').type==='password'?'显示':'隐藏';});
$('list-models').addEventListener('click',fetchModels);$('available-models').addEventListener('change',()=>{if($('available-models').value)$('api-model').value=$('available-models').value;});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSettings();if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();direct();}});init();
