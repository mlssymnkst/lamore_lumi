/* Camada de dados compartilhada. Espera GET /api/avaliacoes e PATCH /api/avaliacoes/<id>.
   Se a API não responder, usa DEMO (para você ver a tela funcionando). */
const API_AVAL = '/api/avaliacoes';
const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
const COR = { rosaClaro:'#F4C0D1', rosa:'#ED93B1', rosaForte:'#D4537E', vinho:'#72243E', texto:'#3D342C', begeEscuro:'#E2D2BF' };
const CFG_PLOTLY = { displayModeBar:false, responsive:true };
const $ = (id) => document.getElementById(id);
const escapar = (t) => { const d=document.createElement('div'); d.textContent=t==null?'':String(t); return d.innerHTML; };
const estrelas = (n) => '★'.repeat(n) + '<span class="off">' + '★'.repeat(5-n) + '</span>';
const fmtData = (iso) => iso.split('-').reverse().join('/');

// campos: id, cliente, categoria, uf, nota, comentario, data(AAAA-MM-DD),
// atendeu, respondeu, resolvido (true/false/null), motivo, resolucao
const DEMO = [
 {id:84712,cliente:'Cliente 1',categoria:'Embalagens',uf:'SP',nota:2,comentario:'Produto chegou danificado.',data:'2026-09-04',atendeu:true,respondeu:true,resolvido:false,motivo:'Cliente não aceitou a resolução',resolucao:'Desconto no pagamento'},
 {id:84689,cliente:'Cliente 2',categoria:'Decoração',uf:'RJ',nota:3,comentario:'Entrega atrasou 3 dias.',data:'2026-09-02',atendeu:true,respondeu:null,resolvido:null,motivo:null,resolucao:null},
 {id:84601,cliente:'Cliente 3',categoria:'Insumos',uf:'MG',nota:1,comentario:'Quantidade errada no pedido.',data:'2026-08-28',atendeu:false,respondeu:null,resolvido:null,motivo:null,resolucao:null},
 {id:84555,cliente:'Cliente 4',categoria:'Personalizados',uf:'SP',nota:5,comentario:'Adorei! Entrega rápida.',data:'2026-08-20',atendeu:null,respondeu:null,resolvido:null,motivo:null,resolucao:null},
 {id:84490,cliente:'Cliente 5',categoria:'Decoração',uf:'PR',nota:4,comentario:'Tudo certo, demorou um pouco.',data:'2026-07-15',atendeu:null,respondeu:null,resolvido:null,motivo:null,resolucao:null},
 {id:84410,cliente:'Cliente 6',categoria:'Embalagens',uf:'BA',nota:2,comentario:'Veio com defeito.',data:'2026-07-03',atendeu:true,respondeu:true,resolvido:true,motivo:null,resolucao:'Reenvio do pedido'},
 {id:84333,cliente:'Cliente 7',categoria:'Insumos',uf:'SP',nota:5,comentario:'Atendimento atencioso.',data:'2026-06-11',atendeu:null,respondeu:null,resolvido:null,motivo:null,resolucao:null},
 {id:84250,cliente:'Cliente 8',categoria:'Outros',uf:'RJ',nota:1,comentario:'Pedido não chegou.',data:'2026-05-22',atendeu:true,respondeu:true,resolvido:true,motivo:null,resolucao:'Devolução de pagamento'},
];
async function buscarAvaliacoes() {
  try { const r = await fetch(API_AVAL); if (!r.ok) throw 0; return { lista: await r.json(), demo:false }; }
  catch { return { lista: structuredClone(DEMO), demo:true }; }
}
async function salvarAvaliacao(id, campos) {
  try { const r = await fetch(`${API_AVAL}/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(campos) }); return r.ok; }
  catch { return false; }
}
const statusDe = (a) => a.resolvido === true ? 'Resolvido' : a.resolvido === false ? 'Não resolvido' : 'Em andamento';
const classeStatus = (s) => ({'Resolvido':'pago','Não resolvido':'atrasado','Em andamento':'pendente'}[s]);
function toast(msg) { const t=$('toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(toast.t); toast.t=setTimeout(()=>t.classList.remove('show'),2800); }
function preencher(select, valores, rotuloTodos='Todos') {
  const atual = select.value;
  select.innerHTML = [rotuloTodos, ...valores].map(v=>`<option value="${escapar(v)}">${escapar(v)}</option>`).join('');
  if ([rotuloTodos,...valores].map(String).includes(atual)) select.value = atual;
}
