// --- #. Utils ---
function getById(id) {
    return document.getElementById(id);
}

function enviarFormulario(id, funcao) {
    getById(id).addEventListener('submit', funcao);
}

function enviarArquivo(id, funcao) {
    getById(id).addEventListener('change', funcao);
}

function capturarClick(id, funcao) {
    getById(id).addEventListener('click', funcao);
}

// --- 1. Seleção de Elementos ---
const socket = io();
const caixaChat = getById('caixa_chat');
const inputMensagem = getById('input_mensagem');
const inputArquivo = getById('input_arquivo');
const previewAnexo = getById('preview_anexo');
const previewImagem = getById('preview_imagem');
const previewPdfNome = getById('preview_pdf_nome');
const botaoTema = getById('botao_tema');
const iconeSol = getById('icone_sol');
const iconeLua = getById('icone_lua');

let anexoTemporario = null;

// --- 2. Ligando os Eventos às Funções de Callback ---

capturarClick('botao_abrir_menu', lidarCliqueMenu);
capturarClick('anexar_imagem_btn', lidarCliqueAnexarImagem);
capturarClick('anexar_pdf_btn', lidarCliqueAnexarPdf);
capturarClick('remover_anexo_btn', lidarCliqueRemoverAnexo);
capturarClick('botao_tema', lidarCliqueTema);
enviarArquivo('input_arquivo', lidarSelecaoDeArquivo);
enviarFormulario('formulario_mensagem', lidarEnvioDoFormulario);


// --- 3. Definição das Funções de Callback ---

function lidarCliqueMenu() {
    const menuAnexo = getById('menu_anexo');
    menuAnexo.classList.toggle('hidden');
}

function lidarCliqueAnexarImagem() {
    inputArquivo.accept = 'image/*';
    inputArquivo.click();
    getById('menu_anexo').classList.add('hidden');
}

function lidarCliqueAnexarPdf() {
    inputArquivo.accept = 'application/pdf';
    inputArquivo.click();
    getById('menu_anexo').classList.add('hidden');
}

function lidarSelecaoDeArquivo(evento) {
    const arquivo = evento.target.files[0];
    if (!arquivo) return;

    const leitor = new FileReader();
    leitor.onload = function (eventoLeitor) {
        anexoTemporario = {
            dados: eventoLeitor.target.result,
            nome: arquivo.name,
            tipo: arquivo.type
        };
        mostrarPreview();
    };
    leitor.readAsDataURL(arquivo);
}

function lidarEnvioDoFormulario(evento) {
    evento.preventDefault();
    const textoMensagem = inputMensagem.value.trim();

    if (!textoMensagem && !anexoTemporario) return;

    adicionarMensagem(textoMensagem, 'mensagem_usuario', anexoTemporario);
    criarPlaceholderRespostaBot();

    const dadosParaEnviar = {
        mensagem: textoMensagem || (anexoTemporario.tipo.includes('image') ? 'Descreva esta imagem para mim.' : 'Resuma o conteúdo deste PDF para mim.')
    };
    if (anexoTemporario) {
        dadosParaEnviar.arquivo = anexoTemporario.dados;
    }

    socket.emit('enviar_mensagem', dadosParaEnviar);

    inputMensagem.value = '';
    lidarCliqueRemoverAnexo(); // Reutilizando a função de remover anexo
}

// --- 4. Funções Auxiliares e Listeners do Socket ---

function mostrarPreview() {
    if (!anexoTemporario) return;
    if (anexoTemporario.tipo.includes('image')) {
        previewImagem.src = anexoTemporario.dados;
        previewImagem.classList.remove('hidden');
        previewPdfNome.classList.add('hidden');
    } else {
        previewPdfNome.textContent = anexoTemporario.nome;
        previewImagem.classList.add('hidden');
        previewPdfNome.classList.remove('hidden');
    }
    previewAnexo.classList.remove('hidden');
}

function lidarCliqueRemoverAnexo() {
    anexoTemporario = null;
    inputArquivo.value = '';
    previewAnexo.classList.add('hidden');
}

function adicionarMensagem(texto, classeCss, anexo = null) {
    const elementoMensagem = document.createElement('div');
    elementoMensagem.classList.add('mensagem', classeCss);
    if (texto) {
        const textoEl = document.createElement('p');
        textoEl.innerText = texto;
        elementoMensagem.appendChild(textoEl);
    }
    if (anexo) {
        if (anexo.tipo.includes('image')) {
            const imgEl = document.createElement('img');
            imgEl.src = anexo.dados;
            elementoMensagem.appendChild(imgEl);
        } else if (anexo.tipo.includes('pdf')) {
            const cabecalho = anexo.dados.split(',')[0];
            const dadosPuros = atob(anexo.dados.split(',')[1]);
            const tipoMime = cabecalho.match(/:(.*?);/)[1];
            const arrayBytes = new Uint8Array(dadosPuros.length);
            for (let i = 0; i < dadosPuros.length; i++) {
                arrayBytes[i] = dadosPuros.charCodeAt(i);
            }
            const pdfBlob = new Blob([arrayBytes], { type: tipoMime });
            const urlPdf = URL.createObjectURL(pdfBlob);
            const linkPdf = document.createElement('a');
            linkPdf.href = urlPdf;
            linkPdf.target = '_blank';
            linkPdf.rel = 'noopener noreferrer';
            linkPdf.classList.add('link-pdf');

            linkPdf.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="M220-200h520v-240H220v240Zm260-320q17 0 28.5-11.5T520-560q0-17-11.5-28.5T480-600q-17 0-28.5 11.5T440-560q0 17 11.5 28.5T480-520Zm-40-200h160v-120H440v120Zm160 480v-120H360v120h240ZM220-80q-24 0-42-18t-18-42v-680q0-24 18-42t42-18h360l200 200v520q0 24-18 42t-42 18H220Zm360-560v-120H220v680h520v-560H580Z"/></svg>
                    <span>${anexo.nome}</span>
                `;
            elementoMensagem.appendChild(linkPdf);
        }
    }

    caixaChat.appendChild(elementoMensagem);
    caixaChat.scrollTop = caixaChat.scrollHeight;
}

function criarPlaceholderRespostaBot() {
    const placeholder = document.createElement('div');
    placeholder.classList.add('mensagem', 'mensagem_bot', 'pensando');

    const textoEl = document.createElement('p');
    textoEl.innerText = 'Pensando...'
    const cursorEl = document.createElement('span');
    cursorEl.classList.add('cursor-piscando');

    textoEl.appendChild(cursorEl);
    placeholder.appendChild(textoEl);

    caixaChat.appendChild(placeholder);
    caixaChat.scrollTop = caixaChat.scrollHeight;
}

const temaSalvo = localStorage.getItem('theme');
if (temaSalvo) {
    document.body.classList.add(temaSalvo);
    if (temaSalvo === 'dark-mode') {
        iconeSol.classList.add('hidden');
        iconeLua.classList.remove('hidden');
    }
}

function lidarCliqueTema() {
    document.body.classList.toggle('dark-mode');

    if (document.body.classList.contains('dark-mode')) {
        localStorage.setItem('theme', 'dark-mode');
        iconeSol.classList.add('hidden');
        iconeLua.classList.remove('hidden');
    } else {
        localStorage.removeItem('theme');
        iconeSol.classList.remove('hidden');
        iconeLua.classList.add('hidden');
    }
}

let primeiraVezStream = true;

socket.on('stream_chunk', (dados) => {
    const placeholder = document.querySelector('.mensagem_bot.pensando');
    if (placeholder) {
        const textoEl = placeholder.querySelector('p');
        const cursor = placeholder.querySelector('.cursor-piscando');

        if (primeiraVezStream) {
            textoEl.innerText = '';
            textoEl.appendChild(cursor);
            primeiraVezStream = false;
        }
        
        textoEl.insertBefore(document.createTextNode(dados.chunk), cursor);
        caixaChat.scrollTop = caixaChat.scrollHeight;
    }
});

socket.on('stream_end', () => {
    const placeholder = document.querySelector('.mensagem_bot.pensando');
    if (placeholder) {
        const cursor = placeholder.querySelector('.cursor-piscando');
        if (cursor) cursor.remove();
        placeholder.classList.remove('pensando');
    }

    primeiraVezStream = true;
});

socket.on('resposta_servidor', (dados) => {
    const placeholder = document.querySelector('.mensagem_bot.pensando');
    if (placeholder) {
        placeholder.remove();
    }

    adicionarMensagem(dados.resposta, 'mensagem_bot');
});

socket.on('connect', () => {
    console.log('Conectado ao servidor!');
});