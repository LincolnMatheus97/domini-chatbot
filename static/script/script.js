// --- #. Utils ---
function getById(id) {
    return document.getElementById(id);
}

function enviarMensagem(id, funcao) {
    getById(id).addEventListener('submit', funcao);
}

function enviarImagem(id, funcao) {
    getById(id).addEventListener('change', funcao);
}

// --- 1. Conexão e Seleção de Elementos ---
const socket = io();

// Selecionando os elementos do HTML uma única vez
const caixaChat = getById('caixa_chat');
const inputMensagem = getById('input_mensagem');
const inputImagem = getById('input_imagem');


// --- 2. Definição das Funções de Callback ---
enviarMensagem('formulario_mensagem', lidarEnvioDeTexto);
enviarImagem('input_imagem', lidarSelecaoDeImagem);

function lidarEnvioDeTexto(evento) {
    evento.preventDefault(); // Impede o recarregamento da página

    const textoMensagem = inputMensagem.value.trim();

    if (textoMensagem) {
        adicionarMensagem(textoMensagem, 'mensagem_usuario');
        socket.emit('enviar_mensagem', { mensagem: textoMensagem });
    }

    inputMensagem.value = ''; // Limpa o campo de input
}

function lidarSelecaoDeImagem(evento) {
    const arquivo = evento.target.files[0];
    if (!arquivo) return;

    const leitor = new FileReader();

    leitor.onload = function (eventoLeitor) {
        const dadosImagem = eventoLeitor.target.result;

        adicionarMensagem('', 'mensagem_usuario', dadosImagem);

        socket.emit('enviar_mensagem', {
            mensagem: "Descreva esta imagem para mim, em português.",
            imagem: dadosImagem
        });
    };

    leitor.readAsDataURL(arquivo);
}

// --- 3. Lógica para Receber Mensagens do Servidor ---
socket.on('resposta_servidor', (dados) => {
    adicionarMensagem(dados.resposta, 'mensagem_bot');
});

socket.on('conectar', () => {
    socket.emit('conectar');
    console.log('Conectado ao servidor com sucesso! ID:', socket.id);
});


// --- 4. Função Auxiliar para Adicionar Mensagens na Tela ---
function adicionarMensagem(texto, classeCss, dadosImagem = null) {
    const elementoMensagem = document.createElement('div');
    elementoMensagem.classList.add('mensagem', classeCss);

    if (texto) {
        elementoMensagem.innerText = texto;
    }

    if (dadosImagem) {
        const elementoImg = document.createElement('img');
        elementoImg.src = dadosImagem;
        elementoMensagem.appendChild(elementoImg);
    }

    caixaChat.appendChild(elementoMensagem);
    caixaChat.scrollTop = caixaChat.scrollHeight;
}