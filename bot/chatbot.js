
'use strict';

/* ── ESTADO GLOBAL ── */

const state = {
  conversations:  [],   // lista de conversas
  activeConvId:   null, // id da conversa selecionada
  convMessages:   {},   // { [convId]: [] } — mensagens por conversa
  convQuoteItems: {},   // { [convId]: [] } — itens de orçamento por conversa
  menuOpen:       false,
  convCounter:    0,    // contador de conversas criadas
  quoteCounter:   0,    // contador de itens criados
  deletedConvs:   {},   // — lixeira temporária

/* Fluxo de orçamento */
  modoConsultaCliente: false,
  modoOrcamento: false,
  modoConsultaOrcamento: false,
  botSessionId: null,
  etapaOrcamento: null,
  dadosOrcamento: {}
};

/* Atalhos para acessar dados da conversa ativa */
function activeMessages()   { return state.convMessages[state.activeConvId]   || []; }
function activeQuoteItems() { return state.convQuoteItems[state.activeConvId] || []; }

const BASE_URL = "http://127.0.0.1:5000";

/* ════════════════════════════════════════════════
   UTILITÁRIOS
════════════════════════════════════════════════ */

/** Hora atual formatada HH:MM */
function now() {
  return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

/** Data amigável relativa */
function dateStr(timestamp) {
  const diff = Date.now() - timestamp;
  if (diff < 60_000)      return 'Agora';
  if (diff < 3_600_000)   return Math.floor(diff / 60_000) + 'min atrás';
  return new Date(timestamp).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

/* ──────────────────────────────────────────
API Insumos
async que irão retornar os valores do banco 
───────────────────────────────────────────── */

// Insumos

async function buscarPorCategoria(categoria){
  const response = await fetch(`http://127.0.0.1:5000/insumos?categoria=${categoria}`);
  const data = await response.json();

  if(!data.length) {
    return "Nenhum insumo encontrado."
  }
  
  let resposta = " Itens encontrados:\n\n";

  data.forEach(i => {
    resposta += 
    ` ${i.modelo || i.categoria} \n` +
    ` - Preço: R$ ${i.preco_venda || i.preco_unitario}\n` +
    ` - Estoque: ${i.estoque_disponivel} ${i.unidade_medida || ""} \n\n`
  });

  return resposta;
}

/* ─────────────────────────────────────────────
API ORÇAMENTO
──────────────────────────────────────────────── */


// Inicia uma nova sessão de orçamento dentro do backend

async function iniciarSessaoBot() {
  const res = await fetch (`${BASE_URL}/bot/iniciar`, {method: "POST"});
  const data = await res.json();
  state.botSessionId = data.session_id;

  return data;    // {session_id, mensagem, opções}
}

/*Envia resposta pro usuário e retorna a próxima */
async function enviarMensagemBot(texto) {
  const res = await fetch
  (`${BASE_URL}/bot/mensagem`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.botSessionId, mensagem: texto }),
  });
  return await res.json();
  // retorna: { mensagem, opcoes, acao?, item?, itens_painel?, orcamento_id?, valor_total?, frete? }
}

//══════════════════════════════════════════════
// EMAILL AUTOMÁTICO
// ══════════════════════════════════════════════

function enviarEmailCliente(emailCliente) {
  const assunto = encodeURIComponent("Orçamento L'amore");

  const corpo = encodeURIComponent(
    "Olá!\n\nSegue o orçamento solicitado.\n\nAtenciosamente,\nL'amore"
  );

  window.location.href =
    `mailto:${emailCliente}?subject=${assunto}&body=${corpo}`;
}


/** Processa a resposta do backend e age sobre a UI */
async function tratarRespostaBot(resposta) {
  if (resposta.erro) {
    addBotMessage("Erro:" + resposta.erro);
    return;
  }

  if (resposta.mensagem) {
    addBotMessage(resposta.mensagem);
  }

  if (resposta.opcoes && resposta.opcoes.length) {
    renderOpcoes(resposta.opcoes);
  }

  if (resposta.acao === "item_adicionado" && resposta.item) {
    const item = resposta.item;

    addQuoteItem(
      item.titulo,
      item.papel,
      item.envelope,
      item.quantidade,
      item.fita,
      item.custo
    );
  }

//Orçamento gerado 
//Atualiza o painel com os itens e exibe o total
 if (resposta.acao === "orcamento_gerado") {

  if (resposta.itens_painel) {
    if (state.activeConvId)
      state.convQuoteItems[state.activeConvId] = [];

    resposta.itens_painel.forEach(item => {
      addQuoteItem(
        item.titulo,
        item.papel,
        item.embalagem,
        item.quantidade,
        item.fita,
        item.custo
      );
    });
  }

  //addTotalAoPanel(resposta.valor_total, resposta.frete); ESSA LINHA NO MOMENTO NÃO FUNCIONA 

  if (resposta.pdf_url) {
    addBotMessage(
      `📄 PDF gerado!\n\n<a href="${BASE_URL}${resposta.pdf_url}" target="_blank">Clique aqui para baixar</a>`
    );
  }

  state.modoOrcamento = false;
  state.botSessionId = null;
}
}
// Render Mensagens
function renderOpcoes(opcoes) {
  const existing = document.getElementById('opcoes-bot');
  if (existing) existing.remove();
 
  const wrap = document.createElement('div');
  wrap.id        = 'opcoes-bot';
  wrap.className = 'opcoes-bot-wrap';
 
  opcoes.forEach(op => {
    const btn = document.createElement('button');
    btn.className   = 'opcao-btn';
    btn.textContent = op;
    btn.onclick = () => {
      wrap.remove();
      document.getElementById('chatInput').value = op;
      sendMessage();
    };
    wrap.appendChild(btn);
  });
 
  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

//Mostrar Orçamento
function mostrarAcoesOrcamento(orcamentoId) {
  const existing = document.getElementById("acoes-orcamento");
  if (existing) existing.remove();

  const container = document.getElementById("messages");

  const wrap = document.createElement("div");
  wrap.id = "acoes-orcamento";
  wrap.className = "opcoes-bot-wrap";

  const btnPdf = document.createElement("button");
  btnPdf.type = "button";
  btnPdf.className = "opcao-btn";
  btnPdf.textContent = "📄 Baixar PDF";

  btnPdf.onclick = (event) => {
  event.preventDefault();
  event.stopPropagation();

  window.open(
    `${BASE_URL}/bot/pdf/${orcamentoId}`,
    "_blank"
  );
};

  wrap.appendChild(btnPdf);
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
}
/* ════════════════════════════════════════════════
   MENU LATERAL (SIDEBAR)
════════════════════════════════════════════════ */

function toggleMenu() {
  state.menuOpen = !state.menuOpen;
  document.getElementById('menuSidebar').classList.toggle('open',    state.menuOpen);
  document.getElementById('overlay').classList.toggle('visible',     state.menuOpen);
  document.getElementById('menuToggleBtn').classList.toggle('active', state.menuOpen);
}

/* ════════════════════════════════════════════════
   CONVERSAS
════════════════════════════════════════════════ */

/** Cria uma nova conversa e a define como ativa */
function newConversation() {
  state.convCounter++;
  const convId = state.convCounter; // Referência fixa para este escopo

  const conv = {
    id: convId,
    name: 'Conversa ' + convId,
    createdAt: Date.now(),
    msgCount: 0,
    active: true,
  };

  state.modoOrcamento = false;
  state.botSessionId = null;

  state.conversations.unshift(conv);
  state.activeConvId = convId;
  state.convMessages[convId] = [];
  state.convQuoteItems[convId] = [];

  // Primeiro renderiza a estrutura vazia
  renderConvList();
  renderQuotePanel();
  updateFooter();
  updateFinishBtn(true);

  // Agora adiciona a mensagem (que chamará o renderMessages internamente)
  addBotMessage(
    'Olá! 👋 Sou o Assistente Virtual da Lamore!\n\n' +
    'Estou aqui para ajudar você a gerenciar nossos produtos!\n\n' +
    '📋 Comandos disponíveis:\n' +
    '• "pedido novo" – criar novo pedido\n' +
    '• "buscar [nome]" – procurar produtos\n' +
    '• "produtos" — listar produtos disponíveis\n' +
    '• "resumo" — ver itens do orçamento\n' +
    '• "ajuda" – ver todos os comandos\n\n' +

    'O que você precisa hoje?\n\n'
  );
}

/** Seleciona uma conversa existente e carrega seus dados */
function selectConv(id) {
  state.activeConvId = id;
  renderConvList();
  renderMessages();
  renderQuotePanel();
  updateFooter();
  const conv = state.conversations.find(c => c.id === id);
  if (conv) updateFinishBtn(conv.active);
}

/** Exclui uma conversa com opção de reverter via toast */
function deleteConv(id, event) {
  event.stopPropagation();

  const idx = state.conversations.findIndex(c => c.id === id);
  if (idx === -1) return;

  const conv = state.conversations[idx];

  state.deletedConvs[id] = {
    conv,
    index:      idx,
    messages:   state.convMessages[id]   || [],
    quoteItems: state.convQuoteItems[id] || [],
  };

  state.conversations.splice(idx, 1);
  delete state.convMessages[id];
  delete state.convQuoteItems[id];

  if (state.activeConvId === id) {
    const next = state.conversations[0];
    state.activeConvId = next ? next.id : null;
  }

  renderConvList();
  renderMessages();
  renderQuotePanel();
  updateFooter();
  showDeleteToast(id, conv.name);
}

/** Reverte a exclusão de uma conversa */
function undoDelete(id) {
  const saved = state.deletedConvs[id];
  if (!saved) return;

  const insertAt = Math.min(saved.index, state.conversations.length);
  state.conversations.splice(insertAt, 0, saved.conv);
  state.convMessages[id]   = saved.messages;
  state.convQuoteItems[id] = saved.quoteItems;

  delete state.deletedConvs[id];

  state.activeConvId = id;
  renderConvList();
  renderMessages();
  renderQuotePanel();
  updateFooter();
  hideDeleteToast();
}

function showDeleteToast(id, name) {
  hideDeleteToast();

  const toast = document.createElement('div');
  toast.id        = 'deleteToast';
  toast.className = 'delete-toast';
  toast.innerHTML = `
    <span>Conversa "<strong>${name}</strong>" excluída.</span>
    <button class="toast-undo-btn" onclick="undoDelete(${id})">Desfazer</button>
    <div class="toast-progress" id="toastProgress"></div>
  `;
  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const bar = document.getElementById('toastProgress');
      if (bar) bar.style.width = '0%';
    });
  });

  state._toastTimer = setTimeout(() => {
    hideDeleteToast();
    delete state.deletedConvs[id];
  }, 5000);
}

function hideDeleteToast() {
  clearTimeout(state._toastTimer);
  const old = document.getElementById('deleteToast');
  if (old) old.remove();
}

/** Renomeia uma conversa */
function renameConv(id, newName) {
  const conv = state.conversations.find(c => c.id === id);
  if (conv && newName.trim()) conv.name = newName.trim();
  renderConvList();
}

/** Alterna o status ativo/encerrado da conversa selecionada */
function toggleActive() {
  const conv = state.conversations.find(c => c.id === state.activeConvId);
  if (conv) {
    conv.active = !conv.active;
    updateFooter();
    updateFinishBtn(conv.active);
  }
}

/** Atualiza o visual do botão "Finalizar conversa" na área do chat */
function updateFinishBtn(isActive) {
  const btn   = document.getElementById('finishConvBtn');
  const label = document.getElementById('finishConvLabel');
  if (!btn || !label) return;

  if (isActive) {
    btn.className   = 'finish-conv-btn';
    label.textContent = 'Finalizar conversa';
    btn.querySelector('svg').innerHTML = '<polyline points="20 6 9 17 4 12"/>';
  } else {
    btn.className   = 'finish-conv-btn reopen';
    label.textContent = 'Reabrir conversa';
    btn.querySelector('svg').innerHTML = '<path d="M3 12a9 9 0 109 9"/><polyline points="3 7 3 12 8 12"/>';
  }
}

/* Abrir o menu usuário, deslogar TERMINAR */

/* Filtro de pesquisa  */
function filterConversations() {
  const input = document.getElementById('searchInput');
  if (!input || !state.activeConvId) return;

  const termo = input.value.toLowerCase();

  const itensFiltrados = activeQuoteItems().filter(item =>
    item.title.toLowerCase().includes(termo) ||
    item.papel.toLowerCase().includes(termo) ||
    item.envelope.toLowerCase().includes(termo)
  );

  renderQuotePanelFiltrado(itensFiltrados);
}

/* filtrar qualquer coisa da pesquisa */
function renderQuotePanelFiltrado(items) {
  const panel = document.getElementById('quoteItems');

  if (!items.length) {
    panel.innerHTML = `
      <div style="text-align:center; color:var(--gray-400); font-size:12px; margin-top:24px;">
        Nenhum item encontrado.
      </div>`;
    return;
  }

  panel.innerHTML = '';

  items.forEach(item => {

    const card = document.createElement('div');
    card.className = 'quote-card';

    card.innerHTML = `
      <div class="quote-card-header">
        <span class="quote-tag">Convites</span>
      </div>

      <div class="quote-card-body">
        <div class="quote-title">${item.title}</div>
        <div class="quote-detail">Papel: ${item.papel}</div>
        <div class="quote-detail">Envelope: ${item.envelope}</div>
        <div class="quote-detail">Quantidade: ${item.qty}</div>
        <div class="quote-detail">Custo: R$ ${item.custo}</div>
      </div>
    `;

    panel.appendChild(card);
  });
}
function filterConversations() {
  const input = document.getElementById('searchInput');

  if (!input || !state.activeConvId) return;

  const termo = input.value.toLowerCase().trim();

  if (termo === '') {
    renderQuotePanel();
    return;
  }

  const itensFiltrados = activeQuoteItems().filter(item =>
    item.title.toLowerCase().includes(termo) ||
    item.papel.toLowerCase().includes(termo) ||
    item.envelope.toLowerCase().includes(termo)
  );

  renderQuotePanelFiltrado(itensFiltrados);
}



/* ════════════════════════════════════════════════
   RENDERIZAÇÃO — LISTA DE CONVERSAS
════════════════════════════════════════════════ */

function renderConvList() {
  const list = document.getElementById('convList');
  list.innerHTML = '';

  if (!state.conversations.length) {
    list.innerHTML = '<div style="font-size:12px;color:var(--gray-400);text-align:center;padding:12px 0">Nenhuma conversa ainda</div>';
    return;
  }

  state.conversations.forEach(conv => {
    const card = document.createElement('div');
    card.className = 'conv-card' + (conv.id === state.activeConvId ? ' active-conv' : '');
    card.onclick = () => selectConv(conv.id);

    card.innerHTML = `
      <div class="conv-card-top">
        <input
          class="conv-name-input"
          value="${conv.name}"
          onclick="event.stopPropagation()"
          onblur="renameConv(${conv.id}, this.value)"
          onkeydown="if(event.key==='Enter') this.blur()">
        <button
          class="conv-delete-btn"
          title="Excluir conversa"
          onclick="deleteConv(${conv.id}, event)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
          </svg>
        </button>
      </div>

      <div class="conv-meta">
        <span class="conv-badge">${conv.msgCount} Msg ${conv.msgCount !== 1 ? 's' : ''}</span>
        <span class="conv-date">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          ${dateStr(conv.createdAt)}
        </span>
      </div>
    `;

    list.appendChild(card);
  });
}

/** Atualiza rodapé: total de conversas + status ativa */
function updateFooter() {
  document.getElementById('totalConvs').textContent = state.conversations.length;

  const conv = state.conversations.find(c => c.id === state.activeConvId);
  const btn  = document.getElementById('activeToggle');

  if (!conv) {
    btn.textContent = '—';
    btn.className   = 'status-toggle';
    return;
  }

  btn.textContent = conv.active ? 'Sim' : 'Não';
  btn.className   = 'status-toggle ' + (conv.active ? 'sim' : 'nao');
}


/* ════════════════════════════════════════════════
   MENSAGENS
════════════════════════════════════════════════ */

/** Adiciona mensagem do bot */
function addBotMessage(text) {
  const conv = state.conversations.find(c => c.id === state.activeConvId);
  if (!conv) return;
  conv.msgCount++;
  if (!state.convMessages[conv.id]) state.convMessages[conv.id] = [];
  state.convMessages[conv.id].push({ type: 'bot', text, time: now() });
  renderMessages();
  renderConvList();
}

/** Adiciona mensagem do usuário */
function addUserMessage(text) {
  const conv = state.conversations.find(c => c.id === state.activeConvId);
  if (!conv) return;
  conv.msgCount++;
  if (!state.convMessages[conv.id]) state.convMessages[conv.id] = [];
  state.convMessages[conv.id].push({ type: 'user', text, time: now() });
  renderMessages();
  renderConvList();
}

/** Renderiza todas as mensagens no DOM */
function renderMessages() {
  const container = document.getElementById('messages');
  container.innerHTML = '';

  const msgs = activeMessages();

  if (!msgs.length && !state.activeConvId) {
    container.innerHTML = '<div style="text-align:center;color:var(--gray-400);font-size:13px;margin-top:40px">Selecione ou crie uma conversa.</div>';
    return;
  }

  msgs.forEach(msg => {
    const row = document.createElement('div');
    row.className = 'msg-row ' + msg.type;

    const safe = msg.text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    if (msg.type === 'bot') {
    row.innerHTML = `
    <img src="../images/french-bulldog.png" alt="L'amore Bot" class="msg-avatar" onerror="this.style.display='none'">
    <div>
      <div class="msg-bubble bot">${safe}<div class="msg-time">${msg.time}</div></div>
    </div>`;

} else {
  row.innerHTML = `
    <div class="msg-bubble user">${safe}<div class="msg-time">${msg.time}</div></div>`;
}

    container.appendChild(row);
  });

  container.scrollTop = container.scrollHeight;
}


/** Preenche o campo de texto com um atalho rápido */
function insertShortcut(cmd) {
  const input = document.getElementById('chatInput');
  input.value = cmd;
  input.focus();
}

/* ══════════════════════════════════════════════
   BOTÕES DE OPÇÃO (novos — gerados pelo fluxo do backend)
══════════════════════════════════════════════ */
function renderOpcoes(opcoes) {
  // Remove opções anteriores se existirem
  const existing = document.getElementById('opcoes-bot');
  if (existing) existing.remove();
 
  const wrap = document.createElement('div');
  wrap.id        = 'opcoes-bot';
  wrap.className = 'opcoes-bot-wrap';
 
  opcoes.forEach(op => {
    const btn = document.createElement('button');
    btn.className   = 'opcao-btn';
    btn.textContent = op;
    btn.onclick = () => {
      wrap.remove();

      // Insere o texto no input e envia
      const input = document.getElementById('chatInput');
      input.value = op;
      sendMessage();
    };
    wrap.appendChild(btn);
  });
 
  // Injeta após o último balão de bot
  const container = document.getElementById('messages');
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
}
 

/* ════════════════════════════════════════════════
   LÓGICA DE RESPOSTAS DO BOT
════════════════════════════════════════════════ */
const BOT_RESPONSES = {
  'consultar orçamento': async () => {
  state.modoConsultaOrcamento = true;
  return 'Informe o telefone do cliente para consultar os orçamentos:';
},

  'consultar cliente': async () => {
  state.modoConsultaCliente = true;
  return 'Informe o telefone do cliente para consulta:';
},

  'ajuda': () =>
    'Comandos disponíveis:\n' +
    '• "pedido novo" – criar pedido\n' +
    '• "buscar [nome]" – procurar produtos\n' +
    '• "resumo" – ver itens do orçamento\n' +
    '• "produtos" – listar produtos',

  'resumo': () =>
    activeQuoteItems().length
      ? `Seu orçamento tem ${activeQuoteItems().length} item(ns). Confira no painel ao lado.`
      : 'Seu orçamento está vazio. Use "pedido novo" para adicionar itens.',

  'produtos': async () => {
  const res = await fetch(`${BASE_URL}/api/insumos`);
  const produtos = await res.json();

  if (!produtos.length) {
    return 'Nenhum produto cadastrado.';
  }

  let texto = '📦 Produtos disponíveis:\n\n';

  produtos.forEach(p => {
    texto +=
      `• ${p.nome}\n` +
      `  Estoque: ${p.qtd}\n` +
      `  Valor: R$ ${p.valor}\n\n`;
  });

  return texto;
},

  'pedido novo': async () => {
    const resposta = await iniciarSessaoBot();

    state.modoOrcamento = true;

    await tratarRespostaBot(resposta);

    return null;
  },

  'default': (input) => {
    if (input.startsWith('buscar ')) {
      const term = input.replace('buscar ', '');

      addQuoteItem(
        'Produto: ' + term,
        'Papel A4',
        'Envelope Personalizado',
        50,
        'Nenhuma',
        0
      );

      return `Busquei por "${term}". Um item foi adicionado ao orçamento para sua revisão.`;
    }

    return 'Não reconheci o comando. Digite "ajuda" para ver os comandos disponíveis.';
  }
};

  /* ******************************************************************************* */
 /* *************************** Inputs do Usuario ********************************* */
  /* ******************************************************************************* */
async function getBotReply(input) {
  const text = input.toLowerCase().trim();

  if (text.startsWith("insumos") || text.startsWith("insumo")) {
    const categoria = text
      .replace("insumos", "")
      .replace("insumo", "")
      .trim();

    return await buscarPorCategoria(categoria);
  }

  if (BOT_RESPONSES[text]) {
    return await BOT_RESPONSES[text]();
  }

  return BOT_RESPONSES["default"](text);
}


  /* ******************************************************************************* */
  /* ******************************************************************************* */
  /* ******************************************************************************* */


/** Envia a mensagem do usuário e aciona a resposta do bot */
async function sendMessage(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }

  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }

  const input = document.getElementById("chatInput");
  const text = input.value.trim();

  if (!text) return;

  if (!state.activeConvId) newConversation();

  input.value = "";
  addUserMessage(text);

  const opcoesDom = document.getElementById("opcoes-bot");
  if (opcoesDom) opcoesDom.remove();

  if (state.modoConsultaOrcamento) {
    state.modoConsultaOrcamento = false;

    const telefone = text.trim();
    const resCliente = await fetch(`${BASE_URL}/clientes/telefone/${telefone}`);

    if (!resCliente.ok) {
      addBotMessage("Cliente não encontrado.");
      return;
    }

    const cliente = await resCliente.json();

    const resOrcamentos = await fetch(`${BASE_URL}/orcamentos`);
    const orcamentos = await resOrcamentos.json();

    const encontrados = orcamentos.filter(o => o.clienteId === cliente._id);

    if (!encontrados.length) {
      addBotMessage(`Nenhum orçamento encontrado para ${cliente.nome}.`);
      return;
    }

    const texto = encontrados.slice(-3).map(o => {
      return `📄 Orçamento: ${o._id}
Cliente: ${o.clienteNome || cliente.nome}
Valor: R$ ${o.valor_total || o.valor_final}
Status: ${o.status || 'registrado'}`;
    }).join('\n\n');

    addBotMessage(texto);
    return;
  }

  if (state.modoConsultaCliente) {
    state.modoConsultaCliente = false;

    const telefone = text.trim();
    const resCliente = await fetch(`${BASE_URL}/clientes/telefone/${telefone}`);

    if (!resCliente.ok) {
      addBotMessage("Cliente não encontrado.");
      return;
    }

    const cliente = await resCliente.json();

    const texto =
      `👤 Cliente encontrado:\n` +
      `Nome: ${cliente.nome}\n` +
      `Telefone: ${cliente.telefone}\n` +
      `E-mail: ${cliente.email || 'Não informado'}\n` +
      `Endereço: ${cliente.endereco || 'Não informado'}\n` +
      `Tipo: ${cliente.tipoCliente || 'comum'}`;

    addBotMessage(texto);
    return;
  }

  if (state.modoOrcamento && state.botSessionId) {
    try {
      const resposta = await enviarMensagemBot(text);
      await tratarRespostaBot(resposta);
    } catch (e) {
      console.error(e);
      addBotMessage("Erro de comunicação com o servidor. Tente novamente.");
    }

    return;
  }

  const resposta = await getBotReply(text);

  if (resposta !== null) {
    addBotMessage(resposta);
  }
}
/** Envia a mensagem do usuário e aciona a resposta do bot */

/* ════════════════════════════════════════════════
   PAINEL DE ORÇAMENTO
════════════════════════════════════════════════ */

/** Adiciona novo item de orçamento na conversa ativa */
function addQuoteItem(title, papel, envelope, qty, fita, custo) {
  if (!state.activeConvId) return;
  state.quoteCounter++;
  if (!state.convQuoteItems[state.activeConvId]) state.convQuoteItems[state.activeConvId] = [];
  state.convQuoteItems[state.activeConvId].unshift({
    id: state.quoteCounter,
    title, 
    papel,
    envelope,
    qty,
    fita,
    custo,
    status: 'pendente',
  });
  renderQuotePanel();
}

/** Confirma um item no orçamento */
function confirmItem(id) {
  const item = activeQuoteItems().find(i => i.id === id);
  if (item) { item.status = 'concluido'; renderQuotePanel(); }
}

/** Exclui (marca como excluído) um item do orçamento */
function removeItem(id) {
  const item = activeQuoteItems().find(i => i.id === id);
  if (item) { item.status = 'excluido'; renderQuotePanel(); }
}

/** Renderiza todos os cards do orçamento da conversa ativa */
function renderQuotePanel() {
  const panel = document.getElementById('quoteItems');
  const items = activeQuoteItems();

  if (!items.length) {
    panel.innerHTML = `
      <div style="text-align:center; color:var(--gray-400); font-size:12px; margin-top:24px; line-height:1.8;">
        Nenhum item ainda.<br>Use o chat para adicionar produtos ao orçamento.
      </div>`;
    return;
  }

  panel.innerHTML = '';

  items.forEach(item => {
    const LABELS   = { concluido: 'Concluído', excluido: 'Excluído', pendente: 'Pendente' };
    const BADGES   = { concluido: 'badge-ok',  excluido: 'badge-excluido', pendente: 'badge-pendente' };
    const statusOk = item.status !== 'excluido';
    const icon     = statusOk ? '✓' : '✗';
    const iconCls  = statusOk ? 'ok-icon' : 'no-icon';

    let actions = '';
    if (item.status === 'pendente') {
      actions = `
        <button class="quote-action-btn confirm" onclick="confirmItem(${item.id})">Confirmar</button>
        <button class="quote-action-btn remove"  onclick="removeItem(${item.id})">Excluir</button>`;
    } else if (item.status === 'excluido') {
      actions = `<button class="quote-action-btn" onclick="confirmItem(${item.id})">Restaurar</button>`;
    } else {
      actions = `<button class="quote-action-btn remove" onclick="removeItem(${item.id})">Remover</button>`;
    }

    const card = document.createElement('div');
    card.className = 'quote-card';
    card.innerHTML = `
      <div class="quote-card-header">
        <span class="quote-tag">Convites</span>
        <span class="quote-status-badge ${BADGES[item.status]}">${LABELS[item.status]}</span>
      </div>
      <div class="quote-card-body">
        <div class="quote-title">${item.title}</div>
        <div class="quote-detail"><span class="${iconCls}">${icon}</span> ${item.papel}</div>
        <div class="quote-detail"><span class="${iconCls}">${icon}</span> Envelope: ${item.envelope}</div>
        <div class="quote-detail"><span class="${iconCls}">${icon}</span> Custo: R$ ${item.custo}</div> 
        <div class="quote-detail"><span class="${iconCls}">${icon}</span> Quantidade: ${item.qty}</div>
        <div class="status-label ${item.status}">
          ${item.status === 'pendente' ? 'Aguardando...' : LABELS[item.status]}
        </div>
      </div>
      <div class="quote-card-actions">${actions}</div>
      <div class="quote-code">Código ${item.code}-00${item.id}</div>
    `;

    panel.appendChild(card);
  });
}


/* ════════════════════════════════════════════════
   INICIALIZAÇÃO
════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  newConversation();
});
