const RESOLUCOES=['Mandar produto faltante','Desconto no pagamento','Devolução de pagamento','Contato com transportadora','Reenvio do pedido','Outro'];
const MOTIVOS=['Cliente não aceitou a resolução','Cliente não respondeu'];
const STATUS=['Em andamento','Não resolvido','Resolvido'];
let LISTA=[]; const f={status:$('fStatus'),nota:$('fNota'),uf:$('fUf'),ord:$('fOrd'),q:$('searchInput')};
const dias=(iso)=>Math.floor((Date.now()-new Date(iso))/864e5);

function chipsSimNao(id,campo,v){const b=(val,txt)=>`<button class="chip ${v===val?(val?'sim':'nao'):''}" data-id="${id}" data-campo="${campo}" data-val="${val}">${txt}</button>`;return `<div class="chips" style="margin:0">${b(true,'Sim')}${b(false,'Não')}</div>`;}
function chipsEscolha(id,campo,opcoes,atual,cls=''){return `<div class="chips">${opcoes.map(o=>`<button class="chip ${atual===o?'sel '+cls:''}" data-id="${id}" data-campo="${campo}" data-val="${escapar(o)}">${escapar(o)}</button>`).join('')}</div>`;}

function card(a){const st=statusDe(a),d=dias(a.data);
  return `<article class="aval"><div class="aval-topo"><b>Pedido #${a.id}</b><span class="stars">${estrelas(a.nota)}</span>${a.resolvido==null&&d>=5?`<span class="aberto">${d}d em aberto ⚠</span>`:''}<span class="selo ${classeStatus(st)}">${st}</span></div>
  <div class="meta">Recebida em ${fmtData(a.data)} · ${escapar(a.cliente)} · ${escapar(a.categoria)} · ${a.uf}</div><div class="coment">“${escapar(a.comentario)}”</div>
  <div class="pergunta">Operador atendeu a avaliação?${chipsSimNao(a.id,'atendeu',a.atendeu)}</div>
  <div class="pergunta">Cliente respondeu à devolutiva? <span style="font-weight:400;color:var(--gray-lamore)">(aviso de 7 dias)</span>${chipsSimNao(a.id,'respondeu',a.respondeu)}</div>
  <div class="pergunta">Teve resolução?${chipsSimNao(a.id,'resolvido',a.resolvido)}</div>
  ${a.resolvido===false?`<div class="sub-pergunta">Por que não foi resolvido?${chipsEscolha(a.id,'motivo',MOTIVOS,a.motivo)}</div>`:''}
  <div class="sub-pergunta">Qual a resolução?${chipsEscolha(a.id,'resolucao',RESOLUCOES,a.resolucao,'verde')}</div></article>`;}

function render(){
  const q=f.q.value.trim().toLowerCase();
  let l=LISTA.filter(a=>(f.status.value==='Todos'||statusDe(a)===f.status.value)&&(f.uf.value==='Todos'||a.uf===f.uf.value)&&
    (f.nota.value==='all'||(f.nota.value==='neg'?a.nota<=3:a.nota===+f.nota.value))&&
    (!q||[a.id,a.cliente,a.comentario].some(v=>String(v).toLowerCase().includes(q))));
  l.sort((a,b)=>f.ord.value==='ant'?a.data.localeCompare(b.data):f.ord.value==='nota'?a.nota-b.nota:b.data.localeCompare(a.data));
  $('resumo').textContent=`${l.length} avaliação(ões) · ${l.filter(a=>a.resolvido==null).length} em andamento`;
  $('lista').innerHTML=l.length?l.map(card).join(''):'<div class="box vazio">Nenhuma avaliação encontrada com esses filtros.</div>';
}
$('lista').addEventListener('click',async e=>{
  const b=e.target.closest('.chip'); if(!b) return;
  const a=LISTA.find(x=>x.id==b.dataset.id), campo=b.dataset.campo, raw=b.dataset.val;
  const val=raw==='true'?true:raw==='false'?false:raw;
  const novo=a[campo]===val?null:val;                 // clicar de novo desmarca
  const antes={...a}; a[campo]=novo;
  if(campo==='resolvido'&&novo!==false) a.motivo=null;
  render();
  const ok=await salvarAvaliacao(a.id,{atendeu:a.atendeu,respondeu:a.respondeu,resolvido:a.resolvido,motivo:a.motivo,resolucao:a.resolucao});
  toast(ok?'Salvo ✓':'Alterado só nesta tela (API indisponível)');
});
[f.status,f.nota,f.uf,f.ord].forEach(s=>s.addEventListener('change',render));
let t; f.q.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(render,200)});
(async()=>{
  $('lista').innerHTML='<div class="skeleton" style="min-height:260px"></div>'.repeat(2);
  const {lista,demo}=await buscarAvaliacoes(); LISTA=lista;
  if(demo) $('demo').innerHTML='<span class="demo-tag">dados de demonstração</span>';
  preencher(f.status,STATUS); preencher(f.uf,[...new Set(LISTA.map(a=>a.uf))].sort()); render();
})();
