// Estado global para controlar o menu
const state = {
    menuOpen: false
};

function toggleMenu() {
    state.menuOpen = !state.menuOpen;
    const menu = document.getElementById('menuSidebar');
    const overlay = document.getElementById('overlay');
    const btn = document.getElementById('menuToggleBtn');

    if (menu) menu.classList.toggle('open', state.menuOpen);
    if (overlay) overlay.classList.toggle('visible', state.menuOpen);
    if (btn) btn.classList.toggle('active', state.menuOpen);
}
 //produtos da conexão mongodb
let produtos = [];
let produtosFiltrados = [];

async function carregarProdutos() {

    try {

        const resposta = await fetch('/api/insumos');

        const dados = await resposta.json();
        if (!resposta.ok) {
            throw new Error(dados.erro || 'Não foi possível carregar os produtos.');
        }
        produtos = dados;

        produtosFiltrados = [...produtos];

        mostrarProdutos();

    } catch (erro) {

        const container = document.getElementById("productList");
        container.textContent = erro.message || "Não foi possível carregar os produtos.";

    }
}

let paginaAtual = 1;
const itensPorPagina = 10;
 

function mostrarProdutos() {

    const container = document.getElementById("productList");

    container.innerHTML = "";

    const inicio = (paginaAtual - 1) * itensPorPagina;

    const fim = inicio + itensPorPagina;

    const produtosPagina = produtosFiltrados.slice(inicio, fim);

    produtosPagina.forEach(produto => {

        const podeExcluir =
            (typeof USER_ROLE !== "undefined" && USER_ROLE === "admin");

        container.innerHTML += `
        <div class="row">
            <span>${produto.id_visual}</span> 

            <span>${produto.nome}</span>

            <span>${produto.qtd}</span>

            <span>R$ ${Number(produto.valor).toFixed(2)}</span>

            ${
                podeExcluir
                ? `<button class="btn-delete"
                    onclick="excluirProduto('${produto.id}')">
                    
                    <span class="material-symbols-outlined">
        delete
    </span>
                   </button>`
                : ''
            }

        </div>`;
    });
}
// excluir
async function excluirProduto(id) {

    if (USER_ROLE !== "admin") {
        alert("Você não tem permissão!");
        return;
    }

    const confirmar = confirm("Deseja excluir este produto?");

    if (!confirmar) return;

    try {

        const resposta = await fetch(`/api/excluir_insumo/${id}`, {
            method: 'DELETE'
        });

        const resultado = await resposta.json();

        alert(resultado.mensagem);

        carregarProdutos();

    } catch (erro) {

        console.log("Erro ao excluir:", erro);

    }
}

function irParaPagina(numero) {
    paginaAtual = numero;
    atualizarBotoes();
    mostrarProdutos();
}

function proximaPagina() {
    const totalPaginas = Math.ceil(produtosFiltrados.length / itensPorPagina);
    if (paginaAtual < totalPaginas) {
        paginaAtual++;
        atualizarBotoes();
        mostrarProdutos();
    }
}

function paginaAnterior() {
    if (paginaAtual > 1) {
        paginaAtual--;
        atualizarBotoes();
        mostrarProdutos();
    }
}

function atualizarBotoes() {
    const botoes = document.querySelectorAll(".page-number");
    botoes.forEach((btn, index) => {
        if (index === paginaAtual - 1) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });
}

function pesquisarProduto() {
    const texto = document.getElementById("searchInput").value.toLowerCase();
    
    produtosFiltrados = produtos.filter(produto =>
        produto.nome.toLowerCase().includes(texto)
    );

    paginaAtual = 1; // Reseta para a primeira página na busca
    atualizarBotoes();
    mostrarProdutos();
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    carregarProdutos();

    console.log("ROLE NO LOAD:", USER_ROLE);

    if (USER_ROLE !== "admin") {
        const btn = document.getElementById("btnEditar");
        if (btn) btn.style.display = "none";
    }
});




// Transforma a tabela em campos editáveis
function habilitarEdicaoGeral() {

    console.log("ROLE:", USER_ROLE); // DEBUG

    if (typeof USER_ROLE === "undefined" || USER_ROLE !== "admin") {
        alert("Você não tem permissão para editar!");
        return;
    }

    const rows = document.querySelectorAll("#productList .row");
    
    rows.forEach((row) => {
        const spans = row.querySelectorAll("span");

        const nomeAtual = spans[1].innerText;
        const qtdAtual = spans[2].innerText;
        const valorAtual = spans[3].innerText.replace("R$ ", "");

        spans[1].innerHTML = `<input class="edit-input" type="text" value="${nomeAtual}">`;
        spans[2].innerHTML = `<input class="edit-input" type="number" value="${qtdAtual}">`;
        spans[3].innerHTML = `<input class="edit-input" type="number" step="0.01" value="${valorAtual}">`;
    });

    //  GARANTE QUE O BOTÃO SEMPRE APAREÇA
    let btn = document.getElementById("btnSalvarGeral");

    if (!btn) {
        btn = document.createElement("button");
        btn.id = "btnSalvarGeral";
        btn.innerText = "SALVAR ALTERAÇÕES";
        btn.className = "save-all-btn";
        btn.onclick = salvarTodasAlteracoes;
        document.querySelector(".products-box").appendChild(btn);
    }

    btn.style.display = "block"; // 🔥 força aparecer
}
//  Salva os dados dos inputs de volta para o array 'produtos'
async function salvarTodasAlteracoes() {

    const rows = document.querySelectorAll("#productList .row");

    const produtosEditados = [];

    rows.forEach(row => {

        const spans = row.querySelectorAll("span");
        const inputs = row.querySelectorAll("input");

        const idVisual = spans[0].innerText;

        const produto = produtos.find(
            p => String(p.id_visual) === String(idVisual)
        );

        if (produto) {

            produtosEditados.push({

                id: produto.id,

                nome: inputs[0].value,

                qtd: parseInt(inputs[1].value),

                valor: parseFloat(inputs[2].value)
            });
        }
    });

    try {

        const resposta = await fetch('/api/editar_insumos', {

            method: 'POST',

            headers: {
                'Content-Type': 'application/json'
            },

            body: JSON.stringify(produtosEditados)
        });

        const resultado = await resposta.json();

        alert(resultado.mensagem);

        document.getElementById("btnSalvarGeral").remove();

        carregarProdutos();

    } catch (erro) {

        console.log("Erro:", erro);

    }
}

function abrirModal() {
    document.getElementById("modalProduto").style.display = "flex";
}

function fecharModal() {
    document.getElementById("modalProduto").style.display = "none";
}

async function salvarProduto() {

    const dados = {

        nome: document.getElementById("nomeProduto").value,
        qtd: document.getElementById("qtdProduto").value,
        valor: document.getElementById("valorProduto").value,

        modelo: document.getElementById("modeloProduto").value,
        peso: document.getElementById("pesoProduto").value,
        altura: document.getElementById("alturaProduto").value,
        largura: document.getElementById("larguraProduto").value,
        unidade_medida: document.getElementById("unidadeProduto").value
    };

    try {

        const resposta = await fetch('/api/adicionar_insumo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(dados)
        });

        const resultado = await resposta.json();

        alert(resultado.mensagem);

        fecharModal();

        carregarProdutos();

    } catch (erro) {

        console.log("Erro ao salvar:", erro);

    }
}

// restrição para add produto
document.addEventListener('DOMContentLoaded', () => {

    carregarProdutos();

    console.log("ROLE NO LOAD:", USER_ROLE);

    if (USER_ROLE !== "admin") {

        const btnEditar = document.getElementById("btnEditar");
        if (btnEditar) btnEditar.style.display = "none";

        const btnAdd = document.getElementById("btnAdicionar");
        if (btnAdd) btnAdd.style.display = "none";
    }
})

function abrirPerfil() {

    const modal = document.getElementById("profileModal");

    const nome = document.getElementById("nomeUsuario").innerText;

    document.getElementById("nomePerfil").innerText = nome;

    if (modal.style.display === "block") {

        modal.style.display = "none";

    } else {

        modal.style.display = "block";
    }
}

function logout() {

    window.location.href = "/";
};