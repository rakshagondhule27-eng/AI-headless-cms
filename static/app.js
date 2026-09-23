async function api(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}), ...(options.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function esc(value){return String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function copyText(value){navigator.clipboard?.writeText(value).then(()=>alert('Copied: '+value)).catch(()=>alert(value));}
function imageSrc(x){return esc(x?.image_url || '/static/visuals/ai.svg');}

async function getMe(){try{const u=await api('/api/me');window.cmsRole=u.role;window.cmsUser=u;}catch(e){}}
async function loadSystemHealth(){const health=document.getElementById('systemHealth');if(!health)return;try{const d=await api('/api/health');const ok=d.status==='healthy';health.textContent=ok?'All core services ready':'One or more components need attention';health.className=ok?'health-ok':'health-warn';[['healthVersion','V'+(d.version||'10')],['healthDb',d.database||'—'],['healthMl',d.ml_model||'—']].forEach(([id,v])=>{const e=document.getElementById(id);if(e)e.textContent=v;});}catch(e){health.textContent='Health check unavailable';health.className='health-warn';}}

async function dashboard(){
  const d=await api('/api/dashboard');
  [['total',d.total],['published',d.published],['drafts',d.drafts],['ai',d.ai_generated],['views',d.views]].forEach(([id,v])=>{const el=document.getElementById(id);if(el)el.textContent=v??0});
  const wrap=document.getElementById('recentCards');
  if(!wrap)return;
  wrap.innerHTML=d.recent.map(x=>`<article class="mini-content"><img src="${imageSrc(x)}" onerror="this.src='/static/visuals/ai.svg'" alt=""><div class="mini-body"><small>${esc(x.category)}</small><h3>${esc(x.title)}</h3><p>${esc(x.status)} · Quality ${x.ai_score}/100</p></div></article>`).join('')||'<div class="empty-state"><b>No content yet</b></div>';
}

function visualButtons(){return document.querySelectorAll('#visualPicker button');}
function pickVisual(btn){visualButtons().forEach(b=>b.classList.remove('selected'));btn.classList.add('selected');document.getElementById('image_url').value=btn.dataset.img;}
function openEditor(){
  document.getElementById('modal').classList.remove('hidden');document.getElementById('eid').value='';
  ['title','summary','body','tags','image_url','meta_description','alt_text'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  const file=document.getElementById('mediaFile');if(file)file.value='';
  document.getElementById('uploadStatus').textContent='';
  visualButtons().forEach(b=>b.classList.remove('selected'));if(visualButtons()[0])pickVisual(visualButtons()[0]);
  document.getElementById('mt').textContent='Create Content';if(document.getElementById('language'))document.getElementById('language').value='English';if(document.getElementById('featured'))document.getElementById('featured').checked=false;
}
function closeEditor(){document.getElementById('modal').classList.add('hidden');}
function edit(x){
  openEditor();document.getElementById('eid').value=x.id;document.getElementById('title').value=x.title;document.getElementById('summary').value=x.summary||'';document.getElementById('body').value=x.body||'';document.getElementById('tags').value=(x.tags||[]).join(', ');document.getElementById('cat').value=x.category_id||'';document.getElementById('image_url').value=x.image_url||'';document.getElementById('language').value=x.language||'English';document.getElementById('meta_description').value=x.meta_description||'';document.getElementById('alt_text').value=x.alt_text||x.title;document.getElementById('featured').checked=!!x.featured;visualButtons().forEach(b=>b.classList.toggle('selected',b.dataset.img===x.image_url));document.getElementById('mt').textContent='Edit Content';
}
async function saveContent(){
  const id=document.getElementById('eid').value;
  const data={title:document.getElementById('title').value,summary:document.getElementById('summary').value,body:document.getElementById('body').value,category_id:+document.getElementById('cat').value,tags:document.getElementById('tags').value.split(','),image_url:document.getElementById('image_url').value,language:document.getElementById('language').value,meta_description:document.getElementById('meta_description').value,alt_text:document.getElementById('alt_text').value,featured:document.getElementById('featured').checked,status:'Draft'};
  try{await api(id?'/api/content/'+id:'/api/content',{method:id?'PUT':'POST',body:JSON.stringify(data)});closeEditor();await loadContent();toast('Content saved as Draft');}catch(e){toast(e.message,true);}
}
async function uploadMedia(){
  const file=document.getElementById('mediaFile')?.files?.[0];if(!file){toast('Choose an image first',true);return;}
  const fd=new FormData();fd.append('file',file);const status=document.getElementById('uploadStatus');status.textContent='Uploading…';
  try{const d=await api('/api/upload',{method:'POST',body:fd});document.getElementById('image_url').value=d.url;visualButtons().forEach(b=>b.classList.remove('selected'));status.textContent='✓ Uploaded';}catch(e){status.textContent='';toast(e.message,true);}
}
async function del(id){if(!confirm('Delete this content permanently?'))return;try{await api('/api/content/'+id,{method:'DELETE'});await loadContent();toast('Content deleted');}catch(e){toast(e.message,true);}}
async function aiFill(){try{const topic=document.getElementById('title').value.trim()||'Artificial Intelligence';const d=await api('/api/ai',{method:'POST',body:JSON.stringify({text:topic,mode:'content'})});document.getElementById('title').value=d.title||topic;document.getElementById('summary').value=d.summary||'';document.getElementById('body').value=d.body||'';document.getElementById('tags').value=(d.keywords||[]).join(', ');toast('AI draft generated');}catch(e){toast(e.message,true);}}

async function loadContent(){
  const el=document.getElementById('rows');if(!el)return;
  const q=(document.getElementById('search')?.value||'').toLowerCase();const status=document.getElementById('statusFilter')?.value||'';
  try{const xs=await api('/api/content');const filtered=xs.filter(x=>(!status||x.status===status)&&(x.title+' '+x.category+' '+x.status+' '+x.author+' '+x.tags.join(' ')).toLowerCase().includes(q));
    el.innerHTML=filtered.map(x=>{
      let actions=`<button onclick='edit(${JSON.stringify(x)})'>Edit</button><button onclick="viewArticle(${x.id})">View</button><button onclick="showHistory(${x.id})">History</button>`;
      if(x.status==='Draft'||x.status==='Rejected')actions+=`<button class="primary-action" onclick="workflowAction(${x.id},'submit')">Submit</button>`;
      if(x.status==='Pending Review'&&['Admin','Editor'].includes(window.cmsRole||''))actions+=`<button class="primary-action" onclick="workflowAction(${x.id},'approve')">Approve</button><button onclick="workflowAction(${x.id},'reject')">Reject</button>`;
      if(x.status==='Approved'&&['Admin','Editor'].includes(window.cmsRole||''))actions+=`<button class="primary-action" onclick="workflowAction(${x.id},'publish')">Publish</button>`;
      if(window.cmsRole==='Admin')actions+=`<button onclick="del(${x.id})">Delete</button>`;
      return `<article class="content-card"><div class="cover"><img src="${imageSrc(x)}" onerror="this.src='/static/visuals/ai.svg'" alt=""><span class="status-badge">${esc(x.status)}</span></div><div class="content-info"><small>${esc(x.category)}</small><h3>${esc(x.title)}</h3><p>${esc(x.summary||x.body||'No summary available.')}</p><div class="meta"><span>✦ Quality ${x.ai_score}/100</span><span>👤 ${esc(x.author)}</span></div><div class="actions">${actions}</div></div></article>`;
    }).join('')||'<div class="card" style="padding:22px"><p class="muted">No matching content. Try another filter or create new content.</p></div>';
  }catch(e){toast(e.message,true);}
}
function viewArticle(id){window.open('/article/'+id,'_blank');}
async function workflowAction(id,action){try{await api(`/api/content/${id}/${action}`,{method:'POST'});await loadContent();if(document.getElementById('pendingRows'))await loadPending();toast(action[0].toUpperCase()+action.slice(1)+' successful');}catch(e){toast(e.message,true);}}
async function loadPending(){
  const el=document.getElementById('pendingRows');if(!el)return;try{const xs=await api('/api/workflow/pending');el.innerHTML=xs.map(x=>`<tr><td><b>${esc(x.title)}</b><br><small>${esc(x.summary||'')}</small></td><td>${esc(x.author)}</td><td>${esc(x.category)}</td><td>${x.submitted_at?new Date(x.submitted_at).toLocaleString():'—'}</td><td><button onclick="workflowAction(${x.id},'approve')">Approve</button><button onclick="workflowAction(${x.id},'reject')">Reject</button></td></tr>`).join('')||'<tr><td colspan="5">No pending content.</td></tr>';}catch(e){toast(e.message,true);}}

async function loadAnalytics(){
  const r=await api('/api/analytics');[['atotal',r.total],['apub',r.published],['aviews',r.views],['aai',r.ai_assisted],['aquality',(r.average_quality||0)+'/100']].forEach(([id,v])=>{const e=document.getElementById(id);if(e)e.textContent=v});
  const top=document.getElementById('topContent');if(top){top.innerHTML=r.top_content.map((x,i)=>`<div class="rank-item"><div class="rank-num">${i+1}</div><div><b>${esc(x.title)}</b><small>${esc(x.category)}</small></div><strong>${x.views}</strong></div>`).join('')||'<p class="muted">No data yet.</p>';}
  function bars(arr){const max=Math.max(1,...arr.map(x=>x.count));return arr.map(x=>`<div class="bar-row"><span>${esc(x.name||x.status)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.round(x.count/max*100)}%"></div></div><b>${x.count}</b></div>`).join('')||'<p class="muted">No data.</p>';}
  const s=document.getElementById('statusList');if(s)s.innerHTML=bars(r.statuses);const c=document.getElementById('categoryList');if(c)c.innerHTML=bars(r.categories);const q=document.getElementById('qualityList');if(q)q.innerHTML=bars(r.quality);
  const rate=document.getElementById('publicationRate');const gauge=document.getElementById('publicationGauge');if(rate)rate.textContent=(r.publication_rate||0)+'%';if(gauge)gauge.style.setProperty('--rate',(r.publication_rate||0)*3.6+'deg');
  const donut=document.getElementById('statusDonut');if(donut){const total=r.statuses.reduce((a,x)=>a+x.count,0)||1;let angle=0;const colors=['#6855ef','#a56cff','#2ebd84','#f59e0b','#e65768'];const stops=r.statuses.map((x,i)=>{const start=angle;angle+=x.count/total*360;return `${colors[i%colors.length]} ${start}deg ${angle}deg`;}).join(',');donut.innerHTML=`<div class="donut" style="background:conic-gradient(${stops})"><div class="donut-label">${total}<br><small>items</small></div></div>`;}
}

async function predictML(){const el=document.getElementById('mlPrediction');const text=document.getElementById('mlText')?.value.trim();if(!text){toast('Enter some text first',true);return}el.innerHTML='<p>Classifying…</p>';try{const d=await api('/api/ml/predict?text='+encodeURIComponent(text));el.innerHTML=`<div class="prediction-main"><b>Predicted Category</b><strong>${esc(d.category)}</strong><span>Model confidence: ${d.confidence}%</span></div><div class="analysis-section"><b>Top predictions</b><p>${(d.top_predictions||[]).map(x=>`<span class="ai-tag">${esc(x.category)} · ${x.confidence}%</span>`).join(' ')}</p></div>`;}catch(e){el.innerHTML='';toast(e.message,true);}}
async function loadMLMetrics(){const el=document.getElementById('mlMetrics');if(!el)return;try{const d=await api('/api/ml/metrics');if(d.accuracy===undefined){el.textContent=d.status||'No metrics';return}el.innerHTML=`<div class="metric-list"><div><b>Model</b><span>${esc(d.model)}</span></div><div><b>Dataset</b><span>${d.dataset_size} samples</span></div><div><b>Train / Test</b><span>${d.train_size} / ${d.test_size}</span></div><div><b>Accuracy</b><span>${(d.accuracy*100).toFixed(1)}%</span></div><div><b>Precision</b><span>${(d.precision_weighted*100).toFixed(1)}%</span></div><div><b>Recall</b><span>${(d.recall_weighted*100).toFixed(1)}%</span></div><div><b>F1 Score</b><span>${(d.f1_weighted*100).toFixed(1)}%</span></div></div>`;
    const labels=d.labels||[];const cm=d.confusion_matrix||[];const matrix=document.getElementById('confusionMatrix');if(matrix&&labels.length){matrix.innerHTML='<table class="matrix"><tr><th>Actual / Predicted</th>'+labels.map(x=>`<th>${esc(x)}</th>`).join('')+'</tr>'+cm.map((row,i)=>`<tr><th>${esc(labels[i])}</th>${row.map(v=>`<td>${v}</td>`).join('')}</tr>`).join('')+'</table>';}
    const comp=await api('/api/ml/comparison').catch(()=>({}));const comparison=document.getElementById('modelComparison');if(comparison&&Object.keys(comp).length){comparison.innerHTML=Object.entries(comp).map(([name,m])=>`<div class="comparison-row"><b>${esc(name)}</b><div class="comparison-track"><div class="comparison-fill" style="width:${(m.accuracy*100).toFixed(1)}%"></div></div><span>${(m.accuracy*100).toFixed(1)}%</span></div>`).join('');}
  }catch(e){el.textContent=e.message;}}

function renderGeneration(d){let html='';if(d.title)html+=`<div class="ai-result-block"><strong>Suggested Title</strong><div>${esc(d.title)}</div></div>`;if(d.summary)html+=`<div class="ai-result-block"><strong>Summary</strong><div>${esc(d.summary)}</div></div>`;if(d.body)html+=`<div class="ai-result-block"><strong>Generated Content</strong><div class="ai-body">${esc(d.body).replace(/\n\n/g,'</p><p>').replace(/^/,'<p>').replace(/$/,'</p>')}</div></div>`;if(d.keywords?.length)html+=`<div class="ai-result-block"><strong>Keywords</strong><div>${d.keywords.map(k=>`<span class="ai-tag">${esc(k)}</span>`).join(' ')}</div></div>`;if(d.tags?.length)html+=`<div class="ai-result-block"><strong>Suggested Tags</strong><div>${d.tags.map(k=>`<span class="ai-tag">#${esc(k)}</span>`).join(' ')}</div></div>`;return html||'<p>No AI result available.</p>';}
async function generateAI(){const result=document.getElementById('result');const topic=document.getElementById('topic').value.trim();if(!topic){toast('Enter a topic first',true);return}result.innerHTML='<p>Generating local AI-assisted content…</p>';try{const d=await api('/api/ai',{method:'POST',body:JSON.stringify({text:topic,mode:document.getElementById('mode').value})});result.innerHTML=renderGeneration(d);}catch(e){result.innerHTML='';toast(e.message,true);}}
async function analyze(){const box=document.getElementById('analysis');const text=document.getElementById('antext').value.trim();if(!text){toast('Paste some text first',true);return}box.innerHTML='<p>Analyzing…</p>';try{const d=await api('/api/analyze',{method:'POST',body:JSON.stringify({text})});box.innerHTML=`<div class="analysis-grid"><div><b>Category</b><span>${esc(d.category)}</span></div><div><b>Confidence</b><span>${d.confidence}%</span></div><div><b>Quality</b><span>${d.quality}/100</span></div><div><b>Readability</b><span>${d.readability}</span></div></div><div class="analysis-section"><b>Summary</b><p>${esc(d.summary)}</p></div><div class="analysis-section"><b>Keywords</b><p>${(d.keywords||[]).map(k=>`<span class="ai-tag">${esc(k)}</span>`).join(' ')}</p></div>`;}catch(e){box.innerHTML='';toast(e.message,true);}}

async function loadAudit(){const el=document.getElementById('auditRows');if(!el)return;try{const xs=await api('/api/audit');el.innerHTML=xs.map(x=>`<tr><td>${new Date(x.created_at).toLocaleString()}</td><td>${esc(x.user)}</td><td><b>${esc(x.action)}</b></td><td>${esc(x.entity)} #${x.entity_id||''}</td><td>${esc(x.details)}</td></tr>`).join('')||'<tr><td colspan="5">No audit events yet.</td></tr>';}catch(e){toast(e.message,true);}}
async function showHistory(id){const modal=document.getElementById('historyModal');const rows=document.getElementById('historyRows');if(!modal||!rows)return;modal.classList.remove('hidden');rows.innerHTML='Loading…';try{const xs=await api('/api/content/'+id+'/versions');rows.innerHTML=xs.map(v=>`<div class="history-row"><b>Version ${v.version} · ${esc(v.title)}</b><small>${new Date(v.created_at).toLocaleString()}</small><p>${esc(v.summary||'No summary')}</p><button class="secondary" onclick="restoreVersion(${id},${v.version})">Restore this version</button></div>`).join('')||'<p class="muted">No versions available.</p>';}catch(e){rows.innerHTML='';toast(e.message,true);}}
function closeHistory(){document.getElementById('historyModal')?.classList.add('hidden');}
async function restoreVersion(id,version){if(!confirm('Restore this version? It will create a new version snapshot.'))return;try{await api(`/api/content/${id}/restore/${version}`,{method:'POST'});closeHistory();await loadContent();toast('Version restored');}catch(e){toast(e.message,true);}}
function toast(message,error=false){let box=document.getElementById('toast');if(!box){box=document.createElement('div');box.id='toast';box.className='toast';document.body.appendChild(box)}box.textContent=message;box.className='toast show'+(error?' error-toast':'');clearTimeout(window.__toast);window.__toast=setTimeout(()=>box.className='toast',3000);}

(async function init(){
  await getMe();
  loadSystemHealth();
  if(document.getElementById('total'))dashboard().catch(e=>toast(e.message,true));
  if(document.getElementById('rows'))loadContent();
  if(document.getElementById('pendingRows'))loadPending();
  if(document.getElementById('atotal'))loadAnalytics();
  if(document.getElementById('mlMetrics'))loadMLMetrics();
  if(document.getElementById('auditRows'))loadAudit();
})();

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await getMe();
    await loadSystemHealth();
    if (document.getElementById('recentCards')) await dashboard();
    if (document.getElementById('rows')) await loadContent();
    if (document.getElementById('pendingRows')) await loadPending();
    if (document.getElementById('topContent')) await loadAnalytics();
    if (document.getElementById('mlMetrics')) await loadMLMetrics();
  } catch (e) {
    console.error('AI CMS bootstrap error:', e);
    if (typeof toast === 'function') toast(e.message || 'Unable to load CMS data', true);
  }
});

/* V12 Advanced Intelligence */
async function loadIntelligence(){
  const el=document.getElementById('ixActions'); if(!el)return;
  try{
    const d=await api('/api/intelligence/insights');
    [['ixTotal',d.total],['ixPublished',d.published],['ixQuality',d.low_quality],['ixMetadata',d.metadata_gaps]].forEach(([id,v])=>{const x=document.getElementById(id);if(x)x.textContent=v??0});
    el.innerHTML=(d.actions||[]).map(a=>`<div class="insight-action"><span class="count">${a.count}</span><div><b>${esc(a.message)}</b><small>${a.count?'Review these items in Content Studio.':'No action currently required.'}</small></div></div>`).join('')||'<p class="muted">No editorial actions.</p>';
    await loadDuplicateChoices();
  }catch(e){toast(e.message,true)}
}
async function intelligenceSearch(){
  const q=document.getElementById('ixSearch')?.value.trim(),el=document.getElementById('ixSearchResults');if(!q){toast('Enter a search query',true);return}
  el.innerHTML='<p class="muted">Searching the published knowledge base…</p>';
  try{const d=await api('/api/intelligence/search?q='+encodeURIComponent(q));el.innerHTML=(d.results||[]).map(x=>`<div class="intel-result"><strong>${x.relevance}%</strong><b>${esc(x.title)}</b><small>${esc(x.category)} · ${esc(x.status)} · ${esc(x.summary||'')}</small><a href="/article/${x.id}" target="_blank">Open article →</a></div>`).join('')||'<p class="muted">No relevant content found.</p>';}catch(e){el.innerHTML='';toast(e.message,true)}
}
async function askCMS(){
  const q=document.getElementById('ixChat')?.value.trim(),el=document.getElementById('ixChatResult');if(!q){toast('Ask a question first',true);return}
  el.innerHTML='<p class="muted">Retrieving grounded sources…</p>';
  try{const d=await api('/api/intelligence/chat',{method:'POST',body:JSON.stringify({message:q})});el.innerHTML=`<div class="chat-answer">${esc(d.answer||'No answer')}</div><div class="source-list">${(d.sources||[]).map(s=>`<div class="source-row"><b>${esc(s.title)}</b> · ${esc(s.category)} · <a href="${s.url}" target="_blank">View source</a></div>`).join('')}</div>`;}catch(e){el.innerHTML='';toast(e.message,true)}
}
async function loadDuplicateChoices(){
  const select=document.getElementById('ixDuplicateContent');if(!select)return;
  try{const xs=await api('/api/content');select.innerHTML=xs.map(x=>`<option value="${x.id}">${esc(x.title)} · ${esc(x.status)}</option>`).join('')||'<option>No content</option>';}catch(e){toast(e.message,true)}
}
async function checkDuplicates(){
  const id=document.getElementById('ixDuplicateContent')?.value,el=document.getElementById('ixDuplicates');if(!id)return;
  el.innerHTML='<p class="muted">Comparing content…</p>';
  try{const d=await api('/api/intelligence/duplicates/'+id);el.innerHTML=(d.matches||[]).map(x=>`<div class="duplicate-row"><b>${esc(x.title)}</b><small>${esc(x.status)} · similarity ${x.similarity}%</small></div>`).join('')||'<p class="muted">No significant similar content detected.</p>';}catch(e){el.innerHTML='';toast(e.message,true)}
}

if(document.getElementById('ixActions')){document.addEventListener('DOMContentLoaded',()=>loadIntelligence());}

async function loadApiKeys(){const el=document.getElementById('apiKeysList');if(!el)return;try{const xs=await api('/api/admin/api-keys');el.innerHTML=xs.map(x=>`<div class="api-key-row"><div><b>${esc(x.name)}</b><small>${esc(x.prefix)}•••• · created ${new Date(x.created_at).toLocaleString()}</small></div><div><span class="status-badge">${x.active?'Active':'Disabled'}</span>${x.active?` <button class="secondary" onclick="revokeClientKey(${x.id})">Revoke</button>`:''}</div></div>`).join('')||'<p class="muted">No external client keys yet.</p>';}catch(e){el.textContent=e.message;}}
async function revokeClientKey(id){if(!confirm('Revoke this API key? External clients using it will stop working.'))return;try{await api('/api/admin/api-keys/'+id,{method:'DELETE'});await loadApiKeys();toast('API key revoked');}catch(e){toast(e.message,true)}}
async function createClientKey(){const name=prompt('Client name','Website / Mobile App');if(name===null)return;try{const d=await api('/api/admin/api-keys',{method:'POST',body:JSON.stringify({name})});const el=document.getElementById('newApiKey');el.classList.remove('hidden');el.innerHTML=`<b>Copy this key now — it will not be shown again.</b><code>${esc(d.api_key)}</code><button class="secondary" onclick="copyText('${esc(d.api_key)}')">Copy</button>`;await loadApiKeys();}catch(e){toast(e.message,true)}}
if(document.getElementById('apiKeysList'))document.addEventListener('DOMContentLoaded',()=>loadApiKeys());
