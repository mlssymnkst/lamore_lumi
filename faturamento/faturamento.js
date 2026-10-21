/* ============================================================
   FATURAMENTO — busca os dados em /api/faturamento e desenha a tela
   ============================================================ */
const API_URL = '/api/faturamento';
const GEOJSON_URL = 'https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson';

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const NOMES_MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
                     'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const ESTADOS_BR = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
                    'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];
const CHAVES_SIGLA = ['sigla', 'SIGLA', 'UF', 'uf', 'abbrev', 'id'];
const TODOS = 'Todos';

// Paleta da tela (rosa + bege)
const COR = {
    bege: '#EFE6DA', begeEscuro: '#E2D2BF', rosaClaro: '#F4C0D1', rosa: '#ED93B1',
    rosaForte: '#D4537E', vinho: '#72243E', texto: '#3D342C',
};
const CFG_PLOTLY = { displayModeBar: false, responsive: true };

const $ = (id) => document.getElementById(id);
const el = {
    ano: $('filtroAno'), status: $('filtroStatus'), uf: $('filtroUf'),
    busca: $('searchInput'), buscaBtn: $('searchBtn'), aviso: $('aviso'),
    resultado: $('resultadoBusca'), cards: $('cards'),
    tituloGrafico: $('tituloGrafico'), graficoMensal: $('graficoMensal'),
    tabelaMensal: document.querySelector('#tabelaMensal tbody'),
    tabelaPedidos: document.querySelector('#tabelaPedidos tbody'),
    contador: $('contadorPedidos'), graficoMapa: $('graficoMapa'), avisoMapa: $('avisoMapa'),
    estadoConsulta: $('estadoConsulta'), metricaRotulo: $('metricaRotulo'), metricaValor: $('metricaValor'),
};

let ultimosDados = null;     // última resposta da API
let sequencia = 0;           // descarta respostas antigas se o usuário filtrar rápido
let geojsonPromise = null;   // o mapa é baixado uma única vez

/* ---------- formatação ---------- */
const fmtMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const moeda = (v) => fmtMoeda.format(Number(v) || 0).replace(/\u00a0/g, ' ');

function compacto(v) {
    v = Number(v) || 0;
    let t;
    if (v >= 1e6) t = (v / 1e6).toFixed(1) + 'M';
    else if (v >= 1e3) t = (v / 1e3).toFixed(1) + 'k';
    else t = v.toFixed(0);
    return t.replace('.', ',');
}

function escapar(texto) {
    const d = document.createElement('div');
    d.textContent = texto == null ? '' : String(texto);
    return d.innerHTML;
}

/* ---------- chamada à API ---------- */
async function carregar() {
    const id = ++sequencia;
    const params = new URLSearchParams();
    if (el.ano.value) params.set('ano', el.ano.value);
    params.set('status', el.status.value || TODOS);
    params.set('uf', el.uf.value || TODOS);
    params.set('q', el.busca.value.trim());

    try {
        const resp = await fetch(`${API_URL}?${params}`);
        if (!resp.ok) throw new Error(`a API respondeu ${resp.status}`);
        const dados = await resp.json();
        if (id !== sequencia) return;           // chegou uma resposta mais nova
        el.aviso.hidden = true;
        ultimosDados = dados;
        renderizar(dados);
    } catch (erro) {
        if (id !== sequencia) return;
        el.aviso.textContent = `Não foi possível carregar o faturamento (${erro.message}). ` +
                               'Confira se o servidor Flask está rodando.';
        el.aviso.hidden = false;
    }
}

function renderizar(d) {
    preencherFiltros(d);
    renderResultadoBusca(d);
    renderCards(d.cards);
    renderGraficoMensal(d);
    renderTabelaMensal(d);
    renderPedidos(d.pedidos);
    renderMapa(d.estados, id => id === sequencia, sequencia);
    renderConsulta(d.estados);
}

/* ---------- filtros ---------- */
function preencherSelect(select, valores, atual) {
    const lista = valores.map(String);
    const mudou = lista.length !== select.options.length ||
                  lista.some((v, i) => select.options[i].value !== v);
    if (mudou) {
        select.innerHTML = lista.map((v) => `<option value="${escapar(v)}">${escapar(v)}</option>`).join('');
    }
    select.value = lista.includes(String(atual)) ? String(atual) : lista[0];
}

function preencherFiltros(d) {
    preencherSelect(el.ano, d.opcoes.anos, el.ano.value || d.ano);
    el.ano.value = String(d.ano);
    preencherSelect(el.status, [TODOS, ...d.opcoes.status], el.status.value || TODOS);
    preencherSelect(el.uf, [TODOS, ...d.opcoes.ufs], el.uf.value || TODOS);
}

function renderResultadoBusca(d) {
    const termo = el.busca.value.trim();
    el.resultado.hidden = !termo;
    if (termo) {
        el.resultado.textContent =
            `Pesquisa por “${termo}”: ${d.cards.total_pedidos} pedido(s) em ${d.ano}.`;
    }
}

/* ---------- cards ---------- */
function renderCards(c) {
    const itens = [
        ['trending_up', String(c.total_pedidos), 'Número de pedidos', 'verde'],
        ['priority_high', String(c.atrasados), 'Em atraso', 'vermelho'],
        ['schedule', String(c.pendentes), 'Pendentes', 'amarelo'],
        ['payments', moeda(c.faturamento_total), 'Faturamento total', 'azul'],
        ['my_location', c.estado_maior, 'Estado com maior valor', 'rosa'],
    ];
    el.cards.innerHTML = itens.map(([icone, numero, rotulo, cor]) => `
        <div class="card">
            <div class="card-icone ${cor}"><span class="material-icons" aria-hidden="true">${icone}</span></div>
            <div class="card-numero">${escapar(numero)}</div>
            <div class="card-label">${escapar(rotulo)}</div>
        </div>`).join('');
}

/* ---------- gráfico mensal (ano inteiro) ---------- */
function renderGraficoMensal(d) {
    el.tituloGrafico.textContent = `Faturamento mensal de ${d.ano}`;
    const alvo = el.graficoMensal;

    if (d.cards.total_pedidos === 0) {
        Plotly.purge(alvo);
        alvo.innerHTML = '<div class="vazio">Não há pedidos para exibir com os filtros selecionados.</div>';
        return;
    }
    if (alvo.querySelector('.vazio')) alvo.innerHTML = '';

    const barras = {
        type: 'bar', x: MESES, y: d.mensal,
        marker: { color: COR.rosa, line: { color: COR.rosaForte, width: 1 } },
        text: d.mensal.map((v) => (v ? compacto(v) : '')),
        textposition: 'outside', cliponaxis: false,
        textfont: { color: COR.texto, size: 11 },
        customdata: d.mensal.map(moeda),
        hovertemplate: '<b>%{x}</b><br>Faturamento: %{customdata}<extra></extra>',
    };
    const layout = {
        height: 320, margin: { l: 15, r: 15, t: 25, b: 35 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: false, bargap: 0.35,
        font: { family: 'Quicksand, Arial, sans-serif', color: COR.texto },
        xaxis: {
            type: 'category', categoryorder: 'array', categoryarray: MESES,
            tickmode: 'array', tickvals: MESES, ticktext: MESES, showgrid: false,
            tickfont: { color: COR.texto, size: 13 }, automargin: true,
        },
        yaxis: { showgrid: true, gridcolor: COR.begeEscuro, zeroline: false, tickprefix: 'R$ ', separatethousands: true },
    };
    Plotly.react(alvo, [barras], layout, CFG_PLOTLY);
}

function renderTabelaMensal(d) {
    const totalPedidos = d.pedidos_mes.reduce((a, b) => a + b, 0);
    const totalValor = d.mensal.reduce((a, b) => a + b, 0);
    el.tabelaMensal.innerHTML = NOMES_MESES.map((nome, i) => `
        <tr><td>${nome}</td><td class="num">${d.pedidos_mes[i]}</td><td class="num">${moeda(d.mensal[i])}</td></tr>`
    ).join('') + `
        <tr class="total"><td>Total do ano</td><td class="num">${totalPedidos}</td><td class="num">${moeda(totalValor)}</td></tr>`;
}

/* ---------- tabela de pedidos ---------- */
function renderPedidos(pedidos) {
    el.contador.textContent = pedidos.length ? `(${pedidos.length})` : '';
    if (!pedidos.length) {
        el.tabelaPedidos.innerHTML =
            '<tr><td colspan="6"><div class="vazio">Nenhum pedido encontrado com os filtros selecionados.</div></td></tr>';
        return;
    }
    el.tabelaPedidos.innerHTML = pedidos.map((p) => `
        <tr>
            <td>${escapar(p.pedido)}</td>
            <td>${escapar(p.cliente)}</td>
            <td>${escapar(p.categoria)}</td>
            <td class="num">${moeda(p.valor)}</td>
            <td>${escapar(p.data)}</td>
            <td><span class="selo ${escapar(String(p.status).toLowerCase())}">${escapar(p.status)}</span></td>
        </tr>`).join('');
}

/* ---------- mapa ---------- */
function carregarGeojson() {
    if (!geojsonPromise) {
        geojsonPromise = fetch(GEOJSON_URL)
            .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
            .catch((e) => { geojsonPromise = null; throw e; });   // permite tentar de novo
    }
    return geojsonPromise;
}

function descobrirChaveSigla(geo) {
    const props = (geo.features[0] || {}).properties || {};
    return CHAVES_SIGLA.find((k) => ESTADOS_BR.includes(String(props[k] || '').toUpperCase())) || null;
}

function centroDoEstado(feature) {
    const lons = [], lats = [];
    (function coletar(c) {
        if (typeof c[0] === 'number') { lons.push(c[0]); lats.push(c[1]); }
        else c.forEach(coletar);
    })(feature.geometry.coordinates);
    return [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
}

function graficoEstadosEmBarras(estados) {
    const lista = Object.entries(estados).filter(([, v]) => v > 0).sort((a, b) => a[1] - b[1]);
    Plotly.react(el.graficoMapa, [{
        type: 'bar', orientation: 'h', x: lista.map((e) => e[1]), y: lista.map((e) => e[0]),
        marker: { color: COR.rosa }, customdata: lista.map((e) => moeda(e[1])),
        hovertemplate: '<b>%{y}</b><br>Faturamento: %{customdata}<extra></extra>',
    }], {
        height: 520, margin: { l: 40, r: 10, t: 10, b: 30 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'Quicksand, Arial, sans-serif', color: COR.texto },
        xaxis: { showgrid: true, gridcolor: COR.begeEscuro, tickprefix: 'R$ ' },
    }, CFG_PLOTLY);
}

async function renderMapa(estados, aindaValido, minhaSequencia) {
    const ufs = ESTADOS_BR;
    const valores = ufs.map((u) => estados[u] || 0);
    const maximo = Math.max(...valores, 1);
    el.avisoMapa.hidden = true;

    try {
        const geo = await carregarGeojson();
        if (!aindaValido(minhaSequencia)) return;
        const chave = descobrirChaveSigla(geo);
        if (!chave) throw new Error('o GeoJSON não traz a sigla dos estados');

        const coroplético = {
            type: 'choropleth', geojson: geo, featureidkey: `properties.${chave}`,
            locations: ufs, z: valores, zmin: 0, zmax: maximo,
            // 0 = bege escuro (o país aparece inteiro); depois do rosa claro ao vinho
            colorscale: [[0, COR.begeEscuro], [0.0001, COR.rosaClaro], [0.5, COR.rosa],
                         [0.8, COR.rosaForte], [1, COR.vinho]],
            marker: { line: { color: '#FFFFFF', width: 1 } },
            text: valores.map(moeda),
            hovertemplate: '<b>%{location}</b><br>Faturamento: %{text}<extra></extra>',
            colorbar: { title: { text: 'R$' }, thickness: 10, len: 0.7, tickprefix: 'R$ ',
                        tickfont: { color: COR.texto } },
        };

        // sigla + valor compacto escritos em cada estado
        const centros = {};
        geo.features.forEach((f) => {
            const sigla = String(f.properties[chave] || '').toUpperCase();
            if (ESTADOS_BR.includes(sigla)) centros[sigla] = centroDoEstado(f);
        });
        const siglas = Object.keys(centros);
        const rotulos = {
            type: 'scattergeo', mode: 'text', hoverinfo: 'skip',
            lon: siglas.map((s) => centros[s][0]), lat: siglas.map((s) => centros[s][1]),
            text: siglas.map((s) => `<b>${s}</b><br>${compacto(estados[s] || 0)}`),
            // texto branco sobre estados escuros, escuro sobre os claros
            textfont: { size: 10, family: 'Quicksand, Arial, sans-serif',
                        color: siglas.map((s) => ((estados[s] || 0) / maximo > 0.55 ? '#FFFFFF' : COR.texto)) },
        };

        const layout = {
            height: 560, margin: { l: 0, r: 0, t: 0, b: 0 }, showlegend: false,
            paper_bgcolor: 'rgba(0,0,0,0)',
            geo: {
                visible: false, projection: { type: 'mercator' },
                // zoom: enquadra o Brasil (lon -74 a -34, lat -34 a 5,5)
                lonaxis: { range: [-74, -34] }, lataxis: { range: [-34, 5.5] },
                bgcolor: 'rgba(0,0,0,0)',
            },
        };
        Plotly.react(el.graficoMapa, [coroplético, rotulos], layout, CFG_PLOTLY);
    } catch (erro) {
        if (!aindaValido(minhaSequencia)) return;
        el.avisoMapa.textContent = `Não foi possível carregar o mapa (${erro.message}); mostrando o ranking por estado.`;
        el.avisoMapa.hidden = false;
        graficoEstadosEmBarras(estados);
    }
}

function renderConsulta(estados) {
    if (!el.estadoConsulta.options.length) {
        el.estadoConsulta.innerHTML = ESTADOS_BR.map((u) => `<option value="${u}">${u}</option>`).join('');
        el.estadoConsulta.value = 'SP';
    }
    const uf = el.estadoConsulta.value;
    el.metricaRotulo.textContent = `Faturamento em ${uf}`;
    el.metricaValor.textContent = moeda(estados[uf] || 0);
}

/* ---------- eventos ---------- */
let temporizador = null;
el.busca.addEventListener('input', () => {              // filtra enquanto digita (como no chatbot)
    clearTimeout(temporizador);
    temporizador = setTimeout(carregar, 250);
});
el.busca.addEventListener('keydown', (e) => { if (e.key === 'Enter') { clearTimeout(temporizador); carregar(); } });
el.buscaBtn.addEventListener('click', () => { clearTimeout(temporizador); carregar(); });
[el.ano, el.status, el.uf].forEach((s) => s.addEventListener('change', carregar));
el.estadoConsulta.addEventListener('change', () => { if (ultimosDados) renderConsulta(ultimosDados.estados); });

carregar();