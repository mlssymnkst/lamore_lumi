
/* LUMI — componentes compartilhados, ponto de reposição,
   cenários de estoque, venda extra e datas do calendário.
   Consome /api/lumi/previsoes. */

(() => {
  "use strict";

  if (!document.getElementById("lumi-ruptura")) return;

  const el = id => document.getElementById(id);

  const fmt = valor =>
    new Intl.NumberFormat("pt-BR", {
      maximumFractionDigits: 1
    }).format(Number(valor) || 0);

  const esc = valor =>
    String(valor ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[c]));

  const rotulos = {
    critico: "Crítico",
    alto: "Alto",
    moderado: "Moderado",
    baixo: "Baixo"
  };

  let produtos = [];
  let horizonte = 28;
  let dataBase = null;

  // Converte dia relativo para data real do histórico.
  // Dia 0 corresponde à última data histórica.
  function dataPorDia(dia) {
    if (dia == null || !dataBase) return null;

    const [ano, mes, diaMes] = dataBase.split("-").map(Number);

    const data = new Date(
      Date.UTC(ano, mes - 1, diaMes + Number(dia))
    );

    return data.toISOString().slice(0, 10);
  }

  // Formata YYYY-MM-DD como DD/MM/YYYY ou DD/MM.
  function formatarData(iso, curta = false) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(iso || ""))) {
      return "—";
    }

    const [ano, mes, dia] = iso.split("-");

    return curta
      ? `${dia}/${mes}`
      : `${dia}/${mes}/${ano}`;
  }

  // Encontra quando o estoque atinge determinado limite.
  function primeiroDia(curva, limite) {
    const indice = curva.findIndex(
      quantidade => quantidade <= limite
    );

    return indice < 0 ? null : indice;
  }

  // Simula estoque sem reposição, com cenários e vendas extras.
  function simular(produto) {
    const fator =
      Number(el("lumi-cenario").value) || 1;

    const extra = Math.max(
      0,
      Math.floor(
        Number(el("lumi-venda-extra").value) || 0
      )
    );

    const inicial = Math.max(
      0,
      Math.round(
        Number(produto.estoque?.atual || 0) * fator
      ) - extra
    );

    const demandas = (produto.previsao_diaria || [])
      .map(d => Math.max(0, Number(d.unidades) || 0));

    const curva = [inicial];

    for (const demanda of demandas) {
      curva.push(
        Math.max(0, curva[curva.length - 1] - demanda)
      );
    }

    const minimo =
      Number(produto.estoque?.estoque_minimo) || 0;

    const ponto =
      Number(produto.ponto_reposicao) || 0;

    return {
      inicial,
      minimo,
      ponto,
      curva,
      diaAlerta: primeiroDia(curva, ponto),
      diaMinimo: primeiroDia(curva, minimo),
      diaRuptura: primeiroDia(curva, 0),
      extra
    };
  }

  // Desenha o gráfico em SVG.
  function desenhar() {
    const selecionado =
      produtos[Number(el("lumi-produto").value)];

    const destino = el("lumi-grafico");

    if (!selecionado) {
      destino.textContent = "Componente não encontrado.";
      return;
    }

    const s = simular(selecionado);

    const curva = s.curva;
    const ultimoDia = curva.length - 1;

    const maximo =
      Math.max(...curva, s.minimo, s.ponto, 1) * 1.12;

    const W = 1000;
    const H = 315;

    const l = 62;
    const r = 24;
    const t = 34;
    const b = 56;

    const largura = W - l - r;
    const altura = H - t - b;

    const x = i =>
      l + i / Math.max(ultimoDia, 1) * largura;

    const y = v =>
      t + altura - Math.max(v, 0) / maximo * altura;

    const coords = curva
      .map(
        (q, i) =>
          `${x(i).toFixed(2)},${y(q).toFixed(2)}`
      )
      .join(" ");

    const poligono =
      `${l},${y(0)} ${coords} ${x(ultimoDia)},${y(0)}`;

    // Linhas de referência horizontais.
    const grades = Array.from({ length: 5 }, (_, k) => {
      const valor = maximo * k / 4;
      const yy = y(valor);

      return `
        <line
          x1="${l}"
          y1="${yy}"
          x2="${W - r}"
          y2="${yy}"
          stroke="#f0e4e8"
        />
        <text
          x="${l - 8}"
          y="${yy + 4}"
          text-anchor="end"
          fill="#93858d"
          font-size="12"
        >${fmt(valor)}</text>
      `;
    }).join("");

    // Datas do eixo X.
    const datas =
      Array.isArray(selecionado.datas_grafico) &&
      selecionado.datas_grafico.length === curva.length
        ? selecionado.datas_grafico
        : curva.map((_, i) => dataPorDia(i));

    const dias = [
      ...new Set(
        [0, 7, 14, 21, 28, ultimoDia]
          .filter(n => n <= ultimoDia)
      )
    ];

    const ticks = dias.map(i => `
      <text
        x="${x(i)}"
        y="${H - 22}"
        text-anchor="middle"
        fill="#93858d"
        font-size="12"
      >${formatarData(datas[i], true)}</text>
    `).join("");

    // Linhas verticais pontilhadas até o eixo das datas
// Linhas pontilhadas com hover para mostrar data e estoque
const guias = curva.map((saldo, i) => `
  <g>
    <!-- Linha pontilhada rosa -->
    <line
      x1="${x(i)}"
      y1="${y(saldo)}"
      x2="${x(i)}"
      y2="${y(0)}"
      stroke="#c34d77"
      stroke-width="1.5"
      stroke-dasharray="4 4"
      opacity="0.65"
      pointer-events="none"
    />

    <!-- Área invisível para facilitar o hover -->
    <line
      x1="${x(i)}"
      y1="${y(saldo)}"
      x2="${x(i)}"
      y2="${y(0)}"
      stroke="transparent"
      stroke-width="14"
      pointer-events="stroke"
      style="cursor: crosshair;"
    >
      <title>
        Data: ${formatarData(datas[i])}
        Estoque projetado: ${fmt(saldo)} unidades
      </title>
    </line>
  </g>
`).join("");

// Pontos interativos com data e estoque
// Pontos rosas com data e estoque ao passar o mouse
const pontos = curva.map((saldo, i) => `
  <circle
    data-lumi-dia="${i}"
    cx="${x(i)}"
    cy="${y(saldo)}"
    r="4"
    fill="#c34d77"
    stroke="#c34d77"
    stroke-width="1.5"
    style="cursor: crosshair;"
  />
`).join("");

    // Linhas de estoque mínimo e ponto de reposição.
    const marcador = (valor, titulo, cor, tracejado) => `
      <line
        x1="${l}"
        x2="${W - r}"
        y1="${y(valor)}"
        y2="${y(valor)}"
        stroke="${cor}"
        stroke-width="2"
        stroke-dasharray="${tracejado}"
      />
      <text
        x="${W - r - 4}"
        y="${Math.max(14, y(valor) - 8)}"
        text-anchor="end"
        fill="${cor}"
        font-size="12"
      >${titulo}: ${fmt(valor)}</text>
    `;

    destino.innerHTML = `
      <svg
        viewBox="0 0 ${W} ${H}"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Estoque simulado de ${esc(
          selecionado.nome_produto
        )} em ${horizonte} dias"
      >
        <defs>
          <linearGradient
            id="lumi-grad-componente"
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop
              offset="0%"
              stop-color="#c34d77"
              stop-opacity=".22"
            />
            <stop
              offset="100%"
              stop-color="#c34d77"
              stop-opacity="0"
            />
          </linearGradient>
        </defs>

        ${grades}

          ${marcador(s.minimo, "mínimo", "#ae8838", "6 5")}

          ${marcador(s.ponto, "repor", "#477a9b", "10 5")}

          <polygon
            points="${poligono}"
            fill="url(#lumi-grad-componente)"
          />

          ${guias}

          <polyline
            points="${coords}"
            fill="none"
            stroke="#c34d77"
            stroke-width="3.5"
            stroke-linejoin="round"
            stroke-linecap="round"
            pointer-events="none"
          />

          ${pontos}

          ${ticks}

        <text
          x="${l + 4}"
          y="${H - 4}"
          fill="#a08c95"
          font-size="11"
        >
          Rosa: saldo · Azul: ponto de reposição ·
          Dourado: estoque mínimo
        </text>
      </svg>
    `;

    // Tooltip personalizado do LUMI
const svg = destino.querySelector("svg");

const tooltip = document.createElement("div");
tooltip.className = "lumi-tooltip";
tooltip.style.display = "none";

destino.appendChild(tooltip);

svg.addEventListener("pointermove", (evento) => {
  const alvo = evento.target.closest("[data-lumi-dia]");

  if (!alvo) {
    tooltip.style.display = "none";
    return;
  }

  const i = Number(alvo.dataset.lumiDia);
  const saldo = Number(curva[i]);

  let status = "Estoque acima do ponto de reposição";
  let classe = "normal";

  if (saldo <= 0) {
    status = "Possível ruptura de estoque";
    classe = "critico";
  } else if (saldo <= s.minimo) {
    status = "Abaixo do estoque mínimo";
    classe = "critico";
  } else if (saldo <= s.ponto) {
    status = "Ponto de reposição atingido";
    classe = "alerta";
  }

  tooltip.innerHTML = `
    <div class="lumi-tooltip-header">
      <div class="lumi-tooltip-data">
        📅 ${formatarData(datas[i])}
      </div>

      <div class="lumi-tooltip-label">
        ESTOQUE PROJETADO
      </div>

      <div class="lumi-tooltip-valor">
        ${fmt(saldo)}
        <small>unidades</small>
      </div>
    </div>

    <div class="lumi-tooltip-body">
      <div class="lumi-tooltip-status ${classe}">
        ${status}
      </div>

      <div class="lumi-tooltip-referencia">
        Ponto de reposição:
        <strong>${fmt(s.ponto)} un.</strong>
      </div>
    </div>
  `;

  tooltip.style.display = "block";

  const area = destino.getBoundingClientRect();
  const tamanho = tooltip.getBoundingClientRect();

  let esquerda = evento.clientX - area.left + 16;
  let topo = evento.clientY - area.top - tamanho.height - 12;

  if (esquerda + tamanho.width > area.width - 8) {
    esquerda = evento.clientX - area.left - tamanho.width - 16;
  }

  if (topo < 8) {
    topo = evento.clientY - area.top + 16;
  }

  tooltip.style.left = `${Math.max(8, esquerda)}px`;
  tooltip.style.top = `${Math.max(8, topo)}px`;
});

svg.addEventListener("pointerleave", () => {
  tooltip.style.display = "none";
});

    // Descrição do gráfico com DATAS.
    const alerta = s.diaAlerta === null
      ? "não atinge o ponto de reposição no período"
      : `atinge o ponto de reposição em ${
          formatarData(dataPorDia(s.diaAlerta))
        }`;

    const ruptura = s.diaRuptura === null
      ? "não apresenta ruptura no período"
      : `pode zerar em ${
          formatarData(dataPorDia(s.diaRuptura))
        }`;

    el("lumi-legenda").textContent =
      `Cenário: ${fmt(s.inicial)} un. após ` +
      `${fmt(s.extra)} un. de venda extra; ` +
      `${alerta} e ${ruptura}. ` +
      `Estoque mínimo: ${fmt(s.minimo)} un. ` +
      `(simulação baseada no histórico até ` +
      `${formatarData(dataBase)}).`;

    // Explica quais produtos e kits consomem o componente.
    const origens = selecionado.origens || {};

    const exemplos =
      (origens.produtos_que_utilizam || [])
        .slice(0, 5)
        .map(p => esc(p.nome))
        .join(" · ");

    el("lumi-origens").innerHTML = `
      <strong>
        Consumo compartilhado de ${
          esc(selecionado.nome_produto)
        }:
      </strong>

      ${fmt(origens.venda_individual_historica || 0)}
      un. atribuídas a vendas individuais e

      ${fmt(origens.consumo_em_kits_historico || 0)}
      un. atribuídas a kits no histórico.

      ${
        exemplos
          ? `<div>
               <strong>
                 Exemplos de produtos/combinações:
               </strong>
               ${exemplos}
             </div>`
          : ""
      }

      <div>
        O consumo de um componente é agregado entre
        vendas avulsas e kits. O estoque é ilustrativo;
        a venda extra digitada é apenas um teste e não
        atualiza o sistema.
      </div>
    `;
  }

  // Preenche indicadores, tabela e opções de componentes.
  function preencher(dados) {
    produtos = Array.isArray(dados.produtos)
      ? dados.produtos
      : [];

    horizonte = Number(dados.horizonte_dias) || 28;

    dataBase = dados.ultima_data_historico;

    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(String(dataBase || ""))
    ) {
      throw new Error(
        "Data-base inválida em ultima_data_historico."
      );
    }

    if (!produtos.length) {
      throw new Error(
        "Nenhum componente retornado no JSON."
      );
    }

    el("lumi-total").textContent =
      fmt(produtos.length);

    el("lumi-risco").textContent =
      fmt(
        produtos.filter(p =>
          ["critico", "alto"].includes(p.risco)
        ).length
      );

    el("lumi-reposicao").textContent =
      fmt(
        produtos.reduce(
          (soma, p) =>
            soma + (Number(p.reposicao_sugerida) || 0),
          0
        )
      );

    // Lista de produtos.
    const seletor = el("lumi-produto");

    seletor.replaceChildren();

    produtos.forEach((p, i) => {
      const opt = document.createElement("option");

      opt.value = String(i);
      opt.textContent = p.nome_produto;

      seletor.appendChild(opt);
    });

    // Seleciona Lenço inicialmente.
    const indiceLenco = produtos.findIndex(
      p => p.nome_produto.toLocaleLowerCase("pt-BR") === "lenço"
    );

    seletor.value = String(
      indiceLenco < 0 ? 0 : indiceLenco
    );

    // Atualiza o gráfico quando os controles são alterados.
    seletor.addEventListener("change", desenhar);

    el("lumi-cenario")
      .addEventListener("change", desenhar);

    el("lumi-venda-extra")
      .addEventListener("input", desenhar);

    // Tabela de prioridades com DATAS.
    el("lumi-tabela").innerHTML = produtos.map(p => `
      <tr>
        <td>${esc(p.nome_produto)}</td>

        <td>
          ${fmt(p.demanda_prevista_total)} un.
        </td>

        <td>
          ${fmt(p.estoque?.atual)} un.
        </td>

        <td>
          ${fmt(p.ponto_reposicao)} un.
        </td>

        <td>
          ${formatarData(
            p.data_alerta_reposicao ||
            dataPorDia(p.dia_alerta_reposicao)
          )}
        </td>

        <td>
          ${formatarData(
            p.data_ruptura ||
            dataPorDia(p.dia_ruptura)
          )}
        </td>

        <td>
          <span class="lumi-pill ${
            ["critico", "alto", "moderado", "baixo"]
              .includes(p.risco)
              ? p.risco
              : "baixo"
          }">
            ${esc(rotulos[p.risco] || p.risco)}
          </span>
        </td>

        <td>
          <strong>
            ${fmt(p.reposicao_sugerida)} un.
          </strong>
        </td>
      </tr>
    `).join("");

    // Informação sobre o período histórico.
    el("lumi-aviso").textContent =
      `Modelo ${dados.modelo} · ` +
      `Histórico até ${formatarData(dataBase)} · ` +
      `Previsão de ${formatarData(dataPorDia(1))} ` +
      `a ${formatarData(dataPorDia(horizonte))} · ` +
      `Componentes de kits (+) · ` +
      `Estoque simulado ` +
      `(não é previsão atual em tempo real).`;

    desenhar();
  }

  // Busca as previsões geradas pelo Python.
  fetch("/api/lumi/previsoes", {
    cache: "no-store"
  })
    .then(async resposta => {
      if (!resposta.ok) {
        throw new Error(`HTTP ${resposta.status}`);
      }

      return resposta.json();
    })
    .then(preencher)
    .catch(erro => {
      el("lumi-aviso").textContent =
        `Não foi possível carregar a previsão: ` +
        `${erro.message}. Execute ` +
        `python -m backend.lumi_forecast ` +
        `na raiz do projeto.`;

      el("lumi-grafico").textContent =
        "Verifique a API /api/lumi/previsoes " +
        "e atualize a página.";

      console.error("LUMI:", erro);
    });

})();
