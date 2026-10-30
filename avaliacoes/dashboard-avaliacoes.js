let TODAS = [];
const f = { ano:$('fAno'), uf:$('fUf'), cat:$('fCat'), q:$('searchInput') };

function filtradas() {
  const q = f.q.value.trim().toLowerCase();
  return TODAS.filter(a => a.data.startsWith(f.ano.value) && (f.uf.value==='Todos'||a.uf===f.uf.value) &&
    (f.cat.value==='Todos'||a.categoria===f.cat.value) &&
    (!q || [a.id,a.cliente,a.comentario,a.categoria].some(v=>String(v).toLowerCase().includes(q))));
}
function renderCards(l) {
  const n=l.length, media=n?l.reduce((s,a)=>s+a.nota,0)/n:0, neg=l.filter(a=>a.nota<=3);
  const itens=[['star',n?media.toFixed(1).replace('.',','):'—','Nota média','rosa'],
    ['reviews',n,'Avaliações recebidas','azul'],
    ['sentiment_satisfied',n?Math.round(l.filter(a=>a.nota>=4).length/n*100)+'%':'—','Satisfação (4–5 ★)','verde'],
    ['warning',neg.length,'Avaliações negativas (≤3 ★)','vermelho'],
    ['schedule',neg.filter(a=>a.resolvido==null).length,'Reclamações em aberto','amarelo']];
  $('cards').innerHTML=itens.map(([i,v,r,c])=>`<div class="card"><div class="card-icone ${c}"><span class="material-icons">${i}</span></div><div class="card-numero">${escapar(v)}</div><div class="card-label">${r}</div></div>`).join('');
}
const vazio = (el,msg) => { Plotly.purge(el); el.innerHTML=`<div class="vazio">${msg}</div>`; };
function renderGraficos(l) {
  const base={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Quicksand, Arial',color:COR.texto},showlegend:false};
  if(!l.length){['gMensal','gNotas','gMotivos'].forEach(i=>vazio($(i),'Sem avaliações para os filtros selecionados.'));return;}
  ['gMensal','gNotas','gMotivos'].forEach(i=>{ if($(i).querySelector('.vazio')) $(i).innerHTML=''; });
  const cont=MESES.map((_,m)=>l.filter(a=>+a.data.slice(5,7)===m+1)), qtd=cont.map(x=>x.length),
        med=cont.map(x=>x.length?+(x.reduce((s,a)=>s+a.nota,0)/x.length).toFixed(2):null);
  Plotly.react('gMensal',[
    {type:'bar',x:MESES,y:qtd,marker:{color:COR.rosa},name:'Avaliações',hovertemplate:'<b>%{x}</b><br>%{y} avaliações<extra></extra>'},
    {type:'scatter',mode:'lines+markers',x:MESES,y:med,yaxis:'y2',connectgaps:true,line:{color:COR.vinho,width:3},marker:{size:8},name:'Nota média',hovertemplate:'Nota média: %{y}<extra></extra>'}],
    {...base,height:320,showlegend:true,legend:{orientation:'h',y:1.12},margin:{l:30,r:35,t:30,b:35},bargap:.35,
     yaxis:{gridcolor:COR.begeEscuro,zeroline:false,rangemode:'tozero'},yaxis2:{overlaying:'y',side:'right',range:[0,5],showgrid:false}},CFG_PLOTLY);
  const notas=[5,4,3,2,1];
  Plotly.react('gNotas',[{type:'bar',orientation:'h',y:notas.map(n=>n+' ★'),x:notas.map(n=>l.filter(a=>a.nota===n).length),
    marker:{color:notas.map(n=>n>=4?'#46ad70':n===3?'#E8C94A':COR.rosaForte)},hovertemplate:'%{y}: %{x}<extra></extra>'}],
    {...base,height:300,margin:{l:40,r:10,t:10,b:30},xaxis:{gridcolor:COR.begeEscuro},yaxis:{autorange:'reversed'}},CFG_PLOTLY);
  const mot={}; l.forEach(a=>{ if(a.motivo) mot[a.motivo]=(mot[a.motivo]||0)+1; });
  const e=Object.entries(mot).sort((a,b)=>a[1]-b[1]);
  if(!e.length) return vazio($('gMotivos'),'Nenhuma reclamação sem resolução. 🎉');
  Plotly.react('gMotivos',[{type:'bar',orientation:'h',x:e.map(x=>x[1]),y:e.map(x=>x[0]),marker:{color:COR.rosaForte}}],
    {...base,height:300,margin:{l:190,r:10,t:10,b:30},xaxis:{gridcolor:COR.begeEscuro,dtick:1}},CFG_PLOTLY);
}
function renderTabela(l) {
  const s=[...l].sort((a,b)=>b.data.localeCompare(a.data));
  $('contador').textContent=s.length?`(${s.length})`:'';
  $('tbody').innerHTML=s.length?s.map(a=>{const st=statusDe(a);return `<tr><td>${a.id}</td><td>${escapar(a.cliente)}</td><td>${escapar(a.categoria)}</td><td><span class="stars">${estrelas(a.nota)}</span></td><td title="${escapar(a.comentario)}">${escapar(a.comentario.length>40?a.comentario.slice(0,37)+'…':a.comentario)}</td><td>${fmtData(a.data)}</td><td>${a.nota<=3?`<span class="selo ${classeStatus(st)}">${st}</span>`:'—'}</td></tr>`}).join('')
    :'<tr><td colspan="7"><div class="vazio">Nenhuma avaliação encontrada.</div></td></tr>';
}
function render(){const l=filtradas();renderCards(l);renderGraficos(l);renderMapa(l);renderTabela(l);}
async function iniciar(){
  $('cards').innerHTML='<div class="skeleton"></div>'.repeat(5);
  const {lista,demo}=await buscarAvaliacoes(); TODAS=lista;
  if(demo) $('demo').innerHTML='<span class="demo-tag">dados de demonstração</span>';
  const anos=[...new Set(TODAS.map(a=>a.data.slice(0,4)))].sort().reverse();
  f.ano.innerHTML=anos.map(a=>`<option>${a}</option>`).join('');
  preencher(f.uf,[...new Set(TODAS.map(a=>a.uf))].sort());
  preencher(f.cat,[...new Set(TODAS.map(a=>a.categoria))].sort());
  render();
}
[f.ano,f.uf,f.cat].forEach(s=>s.addEventListener('change',render));
let t; f.q.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(render,200)});

/* ---------- mapa por estado ---------- */
const GEOJSON_URL='https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson';
const UFS=['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];
const CHAVES=['sigla','SIGLA','UF','uf','abbrev','id'];
let geoPromise=null, seqMapa=0;
function carregarGeo(){ if(!geoPromise) geoPromise=fetch(GEOJSON_URL).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}).catch(e=>{geoPromise=null;throw e}); return geoPromise; }
function centro(feat){const lo=[],la=[];(function c(a){if(typeof a[0]==='number'){lo.push(a[0]);la.push(a[1])}else a.forEach(c)})(feat.geometry.coordinates);return[(Math.min(...lo)+Math.max(...lo))/2,(Math.min(...la)+Math.max(...la))/2];}
function barrasEstados(v,txt){
  const e=UFS.filter(u=>v[u]!=null&&v[u]>0).sort((a,b)=>v[a]-v[b]);
  if(!e.length) return vazio($('gMapa'),'Sem avaliações para os filtros selecionados.');
  Plotly.react('gMapa',[{type:'bar',orientation:'h',x:e.map(u=>v[u]),y:e,marker:{color:COR.rosa},customdata:e.map(u=>txt[u]),hovertemplate:'<b>%{y}</b><br>%{customdata}<extra></extra>'}],
   {height:520,margin:{l:40,r:10,t:10,b:30},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Quicksand, Arial',color:COR.texto},xaxis:{gridcolor:COR.begeEscuro}},CFG_PLOTLY);
}
async function renderMapa(l){
  const id=++seqMapa, modo=$('mapaMetrica').value, av=$('avisoMapa'); av.hidden=true;
  const v={},txt={};
  UFS.forEach(u=>{const a=l.filter(x=>x.uf===u); if(modo==='qtd'){v[u]=a.length;txt[u]=a.length+' avaliações'} else if(a.length){v[u]=+(a.reduce((s,x)=>s+x.nota,0)/a.length).toFixed(2);txt[u]='Nota média '+String(v[u]).replace('.',',')+' ('+a.length+' aval.)'} else {v[u]=null;txt[u]='Sem avaliações'}});
  const fmt=x=>x==null?'':modo==='qtd'?String(x):x.toFixed(1).replace('.',',');
  const alvo=$('gMapa'); if(alvo.querySelector('.vazio')) alvo.innerHTML='';
  try{
    const geo=await carregarGeo(); if(id!==seqMapa) return;
    const chave=CHAVES.find(k=>UFS.includes(String((geo.features[0].properties||{})[k]||'').toUpperCase()));
    if(!chave) throw new Error('o GeoJSON não traz a sigla dos estados');
    const vals=UFS.map(u=>v[u]), max=Math.max(...vals.filter(x=>x!=null),1);
    const zmin=modo==='media'?1:0, zmax=modo==='media'?5:max;
    const base={type:'choropleth',geojson:geo,featureidkey:'properties.'+chave,locations:UFS,z:UFS.map(()=>0),colorscale:[[0,COR.begeEscuro],[1,COR.begeEscuro]],showscale:false,hoverinfo:'skip',marker:{line:{color:'#fff',width:1}}};
    const dados={type:'choropleth',geojson:geo,featureidkey:'properties.'+chave,locations:UFS,z:vals,zmin,zmax,
      colorscale:modo==='qtd'?[[0,COR.begeEscuro],[0.0001,COR.rosaClaro],[0.5,COR.rosa],[0.8,COR.rosaForte],[1,COR.vinho]]:[[0,COR.rosaClaro],[0.5,COR.rosa],[1,COR.vinho]],
      marker:{line:{color:'#fff',width:1}},text:UFS.map(u=>txt[u]),hovertemplate:'<b>%{location}</b><br>%{text}<extra></extra>',
      colorbar:{thickness:10,len:.7,tickfont:{color:COR.texto}}};
    const cs={}; geo.features.forEach(f=>{const s=String(f.properties[chave]||'').toUpperCase(); if(UFS.includes(s)) cs[s]=centro(f)});
    const sg=Object.keys(cs);
    const rot={type:'scattergeo',mode:'text',hoverinfo:'skip',lon:sg.map(s=>cs[s][0]),lat:sg.map(s=>cs[s][1]),
      text:sg.map(s=>`<b>${s}</b>`+(v[s]!=null?`<br>${fmt(v[s])}`:'')),
      textfont:{size:10,family:'Quicksand, Arial',color:sg.map(s=>v[s]!=null&&(v[s]-zmin)/(zmax-zmin)>0.55?'#fff':COR.texto)}};
    Plotly.react(alvo,[base,dados,rot],{height:560,margin:{l:0,r:0,t:0,b:0},showlegend:false,paper_bgcolor:'rgba(0,0,0,0)',
      geo:{visible:false,projection:{type:'mercator'},lonaxis:{range:[-74,-34]},lataxis:{range:[-34,5.5]},bgcolor:'rgba(0,0,0,0)'}},CFG_PLOTLY);
  }catch(e){
    if(id!==seqMapa) return;
    av.textContent=`Não foi possível carregar o mapa (${e.message}); mostrando o ranking por estado.`; av.hidden=false;
    barrasEstados(v,txt);
  }
}
$('mapaMetrica').addEventListener('change',()=>renderMapa(filtradas()));
iniciar();
