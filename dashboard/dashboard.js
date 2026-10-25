const MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];
const COLORS = ["#a82d48", "#dc8588", "#e99ca4", "#bf394d", "#e98071", "#e5a04e", "#df73b0", "#9c778b"];
const UF_POR_CODAREA = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
};

function number(value) {
    return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function formatCurrency(value, compact = false) {
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        notation: compact ? "compact" : "standard",
        maximumFractionDigits: compact ? 1 : 0,
    }).format(number(value));
}

function showEmpty(svg, message = "Sem dados disponíveis") {
    svg.innerHTML = `<text class="empty-label" x="50%" y="52%" text-anchor="middle">${message}</text>`;
}

function escapeXml(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&apos;",
    })[character]);
}

function renderMonthly(data) {
    const svg = document.querySelector("#chart-monthly");
    const closed = data.fechados || [];
    const negotiation = data.negociacao || [];
    const values = [...closed, ...negotiation].map(number);
    if (!values.some(Boolean)) {
        showEmpty(svg);
        return;
    }

    const width = 950;
    const height = 260;
    const margin = { top: 48, right: 43, bottom: 36, left: 50 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const x = index => margin.left + (index / (MONTHS.length - 1)) * plotWidth;
    const y = (value, max) => margin.top + plotHeight - (number(value) / max) * plotHeight;

    const grid = Array.from({ length: 5 }, (_, index) => {
        const lineY = margin.top + (index / 4) * plotHeight;
        const leftValue = (4 - index) * 2.5;
        const rightValue = (4 - index) * 5 + 5;
        const leftLabel = index % 2 === 0
            ? `<text class="chart-label" x="${margin.left - 10}" y="${lineY + 4}" text-anchor="end">${leftValue}</text>`
            : "";
        return `<line class="grid-line" x1="${margin.left}" y1="${lineY}" x2="${width - margin.right}" y2="${lineY}"/>
            ${leftLabel}
            <text class="chart-label" x="${width - margin.right + 10}" y="${lineY + 4}">${rightValue}</text>`;
    }).join("");
    const monthLabels = MONTHS.map((month, index) =>
        `<text class="chart-label" x="${x(index)}" y="${height - 12}" text-anchor="middle">${month}</text>`
    ).join("");
    const series = [
        { values: negotiation, color: COLORS[0], label: "Orçamentos Em Negociação", max: 12 },
        { values: closed, color: COLORS[1], label: "Orçamentos Fechados", max: 25 },
    ];
    const lines = series.map(item => {
        const points = MONTHS.map((_, index) => `${x(index)},${y(item.values[index], item.max)}`).join(" ");
        const dots = MONTHS.map((month, index) => {
            const pointY = y(item.values[index], item.max);
            return `<rect x="${x(index) - 3.5}" y="${pointY - 3.5}" width="7" height="7"
                    transform="rotate(45 ${x(index)} ${pointY})" fill="${item.color}">
                <title>${month}: ${item.values[index] || 0} ${item.label.toLowerCase()}</title>
            </rect>`;
        }).join("");
        return `<polyline points="${points}" fill="none" stroke="${item.color}" stroke-width="3"
                    stroke-linecap="round" stroke-linejoin="round"/>${dots}`;
    }).join("");
    const legend = series.map((item, index) => {
        const xPosition = index === 0 ? 8 : 211;
        return `<rect x="${xPosition}" y="5" width="8" height="8"
                    transform="rotate(45 ${xPosition + 4} 9)" fill="${item.color}"/>
            <text class="chart-label" x="${xPosition + 14}" y="14">${item.label}</text>`;
    }).join("");
    svg.innerHTML = `
        ${grid}
        <line class="axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"/>
        <line class="axis" x1="${width - margin.right}" y1="${margin.top}" x2="${width - margin.right}" y2="${height - margin.bottom}"/>
        ${legend}${monthLabels}${lines}`;
}

function renderProducts(products) {
    const svg = document.querySelector("#chart-products");
    if (!products.length) {
        showEmpty(svg);
        return;
    }
    const top = products.slice(0, 8);
    const max = Math.max(1, ...top.map(item => number(item.quantidade)));
    const barWidth = 270;
    const rowHeight = 27;
    const contentHeight = Math.max(205, top.length * rowHeight + 34);
    svg.setAttribute("viewBox", `0 0 430 ${contentHeight}`);
    svg.style.height = `${contentHeight / 205 * 100}%`;
    const rows = top.map((item, index) => {
        const y = 8 + index * rowHeight;
        const fullLabel = String(item.nome || "Produto");
        const label = fullLabel.length > 17 ? `${fullLabel.slice(0, 16)}…` : fullLabel;
        const width = (number(item.quantidade) / max) * barWidth;
        return `<text class="chart-label" x="4" y="${y + 13}">${label}</text>
            <rect x="145" y="${y}" width="${barWidth}" height="18" fill="#ffffff"/>
            <rect x="145" y="${y}" width="${width}" height="18" fill="#d65d70">
                <title>${fullLabel}: ${item.quantidade}</title>
            </rect>`;
    }).join("");
    const axisY = 8 + top.length * rowHeight + 4;
    svg.innerHTML = `${rows}
        <line class="axis" x1="145" y1="${axisY}" x2="415" y2="${axisY}"/>
        <text class="chart-label" x="145" y="${axisY + 17}">0</text>
        <text class="chart-label" x="280" y="${axisY + 17}" text-anchor="middle">${Math.round(max / 2)}</text>
        <text class="chart-label" x="415" y="${axisY + 17}" text-anchor="end">${max}</text>`;
}

function renderCategories(categories) {
    const svg = document.querySelector("#chart-categories");
    if (!categories.length) {
        showEmpty(svg);
        return;
    }
    const items = categories.slice(0, 6);
    const total = items.reduce((sum, item) => sum + number(item.quantidade), 0);
    if (!total) {
        showEmpty(svg);
        return;
    }

    let angle = -Math.PI / 2;
    const centerX = 135;
    const centerY = 113;
    const radius = 68;
    const segments = items.map((item, index) => {
        const value = number(item.quantidade);
        const next = angle + (value / total) * Math.PI * 2;
        const start = [centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius];
        const end = [centerX + Math.cos(next) * radius, centerY + Math.sin(next) * radius];
        const large = next - angle > Math.PI ? 1 : 0;
        const path = `M ${centerX} ${centerY} L ${start[0]} ${start[1]} A ${radius} ${radius} 0 ${large} 1 ${end[0]} ${end[1]} Z`;
        const middle = (angle + next) / 2;
        const percentage = new Intl.NumberFormat("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value / total * 100);
        const segment = {
            item,
            index,
            path,
            large,
            middle,
            percentage,
            side: Math.cos(middle) >= 0 ? "right" : "left",
            labelY: centerY + Math.sin(middle) * (radius + 24),
        };
        angle = next;
        return segment;
    });
    const labelPositions = { left: [], right: [] };
    segments.forEach(segment => labelPositions[segment.side].push(segment));
    Object.values(labelPositions).forEach(positioned => {
        positioned.sort((a, b) => a.labelY - b.labelY);
        positioned.forEach((segment, index) => {
            segment.labelY = Math.max(15, segment.labelY);
            if (index > 0) {
                segment.labelY = Math.max(segment.labelY, positioned[index - 1].labelY + 17);
            }
        });
        if (positioned.length && positioned[positioned.length - 1].labelY > 198) {
            const shift = positioned[positioned.length - 1].labelY - 198;
            positioned.forEach(segment => { segment.labelY -= shift; });
        }
    });
    const slices = segments.map(segment => {
        const edgeX = centerX + Math.cos(segment.middle) * radius;
        const edgeY = centerY + Math.sin(segment.middle) * radius;
        const lineX = segment.side === "right" ? 207 : 63;
        const labelX = segment.side === "right" ? 210 : 60;
        const anchor = segment.side === "right" ? "start" : "end";
        const value = number(segment.item.quantidade);
        return `<path d="${segment.path}" fill="${COLORS[segment.index + 2]}" stroke="#fff" stroke-width="2">
                <title>${segment.item.nome}: ${value}</title>
            </path>
            <polyline points="${edgeX},${edgeY} ${lineX},${segment.labelY - 3} ${labelX},${segment.labelY - 3}"
                fill="none" stroke="#c9c5c7" stroke-width="1"/>
            <text class="chart-label percentage-label" x="${labelX}" y="${segment.labelY}" text-anchor="${anchor}">${segment.percentage}%</text>`;
    }).join("");
    const legend = items.map((item, index) => {
        const y = 54 + index * 25;
        const label = String(item.nome || "Categoria").slice(0, 15);
        return `<circle cx="258" cy="${y - 3}" r="5" fill="${COLORS[index + 2]}"/>
            <text class="chart-label" x="269" y="${y}">${label}</text>`;
    }).join("");
    svg.innerHTML = `${slices}${legend}`;
}

function renderRegions(regions, geojson) {
    const svg = document.querySelector("#chart-regions");
    const width = 270;
    const height = 210;
    const padding = 8;
    const longitudeScale = Math.cos(14 * Math.PI / 180);
    const features = geojson.features || [];
    const rings = feature => {
        const geometry = feature.geometry;
        if (geometry.type === "Polygon") {
            return geometry.coordinates;
        }
        if (geometry.type === "MultiPolygon") {
            return geometry.coordinates.flat();
        }
        return [];
    };
    const allCoordinates = features.flatMap(feature => rings(feature).flat());
    if (!allCoordinates.length) {
        showEmpty(svg, "Geometria do mapa indisponível");
        return;
    }

    const projected = allCoordinates.map(([longitude, latitude]) => [
        longitude * longitudeScale,
        latitude,
    ]);
    const minX = Math.min(...projected.map(point => point[0]));
    const maxX = Math.max(...projected.map(point => point[0]));
    const minY = Math.min(...projected.map(point => point[1]));
    const maxY = Math.max(...projected.map(point => point[1]));
    const scale = Math.min(
        (width - padding * 2) / (maxX - minX),
        (height - padding * 2) / (maxY - minY),
    );
    const offsetX = (width - (maxX - minX) * scale) / 2;
    const offsetY = (height - (maxY - minY) * scale) / 2;
    const x = longitude => offsetX + (longitude * longitudeScale - minX) * scale;
    const y = latitude => offsetY + (maxY - latitude) * scale;
    const byState = new Map(regions.map(region => [
        String(region.nome || "").toUpperCase(),
        region,
    ]));
    const maxOrders = Math.max(0, ...regions.map(region => number(region.orcamentos)));
    const mix = (start, end, amount) => Math.round(start + (end - start) * amount);
    const colorFor = orders => {
        if (!maxOrders || !orders) {
            return "#f5e9ed";
        }
        const amount = Math.sqrt(orders / maxOrders);
        return `rgb(${mix(249, 181, amount)}, ${mix(237, 50, amount)}, ${mix(240, 82, amount)})`;
    };
    const paths = features.map(feature => {
        const state = UF_POR_CODAREA[String(feature.properties?.codarea || "")];
        const region = state ? byState.get(state) : null;
        const orders = number(region?.orcamentos);
        const value = number(region?.valor);
        const pathData = rings(feature).map(ring => ring.map((point, index) =>
            `${index ? "L" : "M"}${x(point[0]).toFixed(2)},${y(point[1]).toFixed(2)}`
        ).join(" ") + " Z").join(" ");
        const description = state
            ? `${state}: ${orders} orçamento${orders === 1 ? "" : "s"}; ${formatCurrency(value)}`
            : "Estado sem identificação";
        return `<path d="${pathData}" fill="${colorFor(orders)}" stroke="#ffffff"
                stroke-width="0.8" stroke-linejoin="round" aria-label="${escapeXml(description)}">
            <title>${escapeXml(description)}</title>
        </path>`;
    }).join("");
    svg.innerHTML = paths;
}

function setIndicators(indicators) {
    document.querySelector("#kpi-closed").textContent =
        indicators.orcamentos_fechados ?? "—";
    document.querySelector("#kpi-waste").textContent =
        indicators.media_desperdicio == null
            ? "—"
            : `${new Intl.NumberFormat("pt-BR", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(indicators.media_desperdicio)}%`;
    document.querySelector("#kpi-negotiation").textContent =
        indicators.pedidos_negociacao ?? "—";
    const value = number(indicators.valor_negociacao);
    document.querySelector("#kpi-value").textContent = value >= 1000
        ? `${new Intl.NumberFormat("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value / 1000)} Mil`
        : new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

async function loadDashboard() {
    const status = document.querySelector("#status");
    try {
        const response = await fetch("/api/dashboard", {
            headers: { Accept: "application/json" },
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.erro || "Falha ao carregar os indicadores.");
        }
        setIndicators(data.indicadores);
        renderMonthly(data.mensal);
        renderProducts(data.produtos);
        renderCategories(data.categorias);

        try {
            const mapResponse = await fetch("/dashboard/assets/brazil-states.geojson", {
                headers: { Accept: "application/geo+json, application/json" },
            });
            const geojson = await mapResponse.json();
            if (!mapResponse.ok) {
                throw new Error("Não foi possível carregar a geometria do mapa.");
            }
            if (!Array.isArray(geojson.features)) {
                throw new Error("A geometria do mapa está em um formato inválido.");
            }
            renderRegions(data.regioes, geojson);
        } catch (error) {
            showEmpty(document.querySelector("#chart-regions"), "Mapa indisponível");
            status.textContent = error.message || "Não foi possível carregar o mapa.";
        }
    } catch (error) {
        status.textContent = error.message || "Não foi possível carregar os dados.";
        [".visual-line svg", ".visual-products svg", ".visual-categories svg"]
            .forEach(selector => showEmpty(document.querySelector(selector), "Dados indisponíveis"));
        showEmpty(document.querySelector("#chart-regions"), "Dados indisponíveis");
    }
}

loadDashboard();
