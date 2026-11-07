const RESOLUCOES=['Mandar produto faltante','Desconto no pagamento','Devolução de pagamento','Contato com transportadora','Reenvio do pedido','Outro'];
const MOTIVOS=['Cliente não aceitou a resolução','Cliente não respondeu'];
const STATUS=['Em andamento','Não resolvido','Resolvido','Avaliação positiva','Histórica'];
let LISTA=[]; const f={status:$('fStatus'),nota:$('fNota'),uf:$('fUf'),ord:$('fOrd'),q:$('searchInput')};
const dias=(iso)=>Math.floor((Date.now()-new Date(iso))/864e5);

function chipsSimNao(id,campo,v){const b=(val,txt)=>`<button class="chip ${v===val?(val?'sim':'nao'):''}" data-id="${id}" data-campo="${campo}" data-val="${val}">${txt}</button>`;return `<div class="chips" style="margin:0">${b(true,'Sim')}${b(false,'Não')}</div>`;}
function chipsEscolha(id,campo,opcoes,atual,cls=''){return `<div class="chips">${opcoes.map(o=>`<button class="chip ${atual===o?'sel '+cls:''}" data-id="${id}" data-campo="${campo}" data-val="${escapar(o)}">${escapar(o)}</button>`).join('')}</div>`;}

function card(a){const st=statusDe(a),d=dias(a.data),id=escapar(a.avaliacaoId),acompanhar=a.nota<5&&a.origem!=='historico';
  const problemas=a.problemas?.length?`<div class="coment">Problemas: ${a.problemas.map(escapar).join(' · ')}</div>`:'';
  const quantidade=a.quantidade_correta?`<div class="coment">Quantidade correta: ${a.quantidade_correta==='sim'?'Sim':'Não'}</div>`:'';
  const recomendacao=a.recomendacao?`<div class="coment">Recomendação: “${escapar(a.recomendacao)}”</div>`:'';
  const fotos=a.fotos?.length?`<div class="coment">${a.fotos.map(f=>`<a href="/api/avaliacoes/fotos/${encodeURIComponent(f.id)}" target="_blank" rel="noopener">${escapar(f.nome)}</a>`).join(' · ')}</div>`:'';
  return `<article class="aval"><div class="aval-topo"><b>Pedido #${escapar(a.id)}</b><span class="stars">${estrelas(a.nota)}</span>${acompanhar&&a.resolvido==null&&d>=5?`<span class="aberto">${d}d em aberto ⚠</span>`:''}${a.origem==='demo'?'<span class="selo pendente">Demonstração</span>':''}${a.origem==='historico'?'<span class="selo pendente">Histórico</span>':''}<span class="selo ${classeStatus(st)}">${st}</span></div>
  <div class="meta">Recebida em ${fmtData(a.data)} · ${escapar(a.cliente)} · ${escapar(a.categoria)} · ${escapar(a.uf)}</div><div class="coment">“${escapar(a.comentario)}”</div>
  ${problemas}${quantidade}${recomendacao}${fotos}
  ${acompanhar?`<div class="pergunta">Operador atendeu a avaliação?${chipsSimNao(id,'atendeu',a.atendeu)}</div>
  <div class="pergunta">Cliente respondeu à devolutiva? <span style="font-weight:400;color:var(--gray-lamore)">(aviso de 7 dias)</span>${chipsSimNao(id,'respondeu',a.respondeu)}</div>
  <div class="pergunta">Teve resolução?${chipsSimNao(id,'resolvido',a.resolvido)}</div>
  ${a.resolvido===false?`<div class="sub-pergunta">Por que não foi resolvido?${chipsEscolha(id,'motivo',MOTIVOS,a.motivo)}</div>`:''}
  <div class="sub-pergunta">Qual a resolução?${chipsEscolha(id,'resolucao',RESOLUCOES,a.resolucao,'verde')}</div>`:''}</article>`;}

function render(){
  const q=f.q.value.trim().toLowerCase();
  let l=LISTA.filter(a=>(f.status.value==='Todos'||statusDe(a)===f.status.value)&&(f.uf.value==='Todos'||a.uf===f.uf.value)&&
    (f.nota.value==='all'||(f.nota.value==='neg'?a.nota<=3:a.nota===+f.nota.value))&&
    (!q||[a.id,a.cliente,a.comentario].some(v=>String(v).toLowerCase().includes(q))));
  l.sort((a,b)=>f.ord.value==='ant'?a.data.localeCompare(b.data):f.ord.value==='nota'?a.nota-b.nota:b.data.localeCompare(a.data));
  $('resumo').textContent=`${l.length} avaliação(ões) · ${l.filter(a=>a.origem!=='historico'&&a.nota<5&&a.resolvido==null).length} reclamação(ões) em andamento`;
  $('lista').innerHTML=l.length?l.map(card).join(''):'<div class="box vazio">Nenhuma avaliação encontrada com esses filtros.</div>';
}
$('lista').addEventListener('click',async e=>{
  const b=e.target.closest('.chip'); if(!b) return;
  const a=LISTA.find(x=>x.avaliacaoId==b.dataset.id), campo=b.dataset.campo, raw=b.dataset.val;
  if(!a) return;
  const val=raw==='true'?true:raw==='false'?false:raw;
  const novo=a[campo]===val?null:val;                 // clicar de novo desmarca
  const antes={...a}; a[campo]=novo;
  if(campo==='resolvido'&&novo!==false) a.motivo=null;
  render();
  if(a.origem==='demo') {
    toast('Alteração aplicada somente nesta demonstração.');
    return;
  }
  try {
    const ok=await salvarAvaliacao(a.avaliacaoId,{atendeu:a.atendeu,respondeu:a.respondeu,resolvido:a.resolvido,motivo:a.motivo,resolucao:a.resolucao});
    if(!ok) throw new Error();
    toast('Salvo ✓');
  } catch {
    Object.assign(a,antes);
    render();
    toast('Não foi possível salvar. Tente novamente.');
  }
});
[f.status,f.nota,f.uf,f.ord].forEach(s=>s.addEventListener('change',render));
let t; f.q.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(render,200)});
(async()=>{
  $('lista').innerHTML='<div class="skeleton" style="min-height:260px"></div>'.repeat(2);
  try {
    LISTA=await buscarAvaliacoes();
  } catch (error) {
    $('lista').innerHTML=`<div class="box vazio">${escapar(error.message)}</div>`;
    $('resumo').textContent='Não foi possível carregar as avaliações.';
    return;
  }
  preencher(f.status,STATUS); preencher(f.uf,[...new Set(LISTA.map(a=>a.uf).filter(Boolean))].sort()); render();
})();
