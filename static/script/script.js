// --- #. Utils ---
function getById(id) {
    return document.getElementById(id);
}

function enviarMensagem(id, funcao) {
    getById(id).addEventListener('submit', funcao);
    return getById(id);
}

function enviarImagem(id, funcao) {
    getById(id).addEventListener('change', funcao);
    return getById(id);
}

// --- 1. Conexão com o Backend ---
const socket = io();

// Selecionando os elementos do HTML pelos novos IDs
const caixaChat = document.getElementById('caixa_chat');
const formularioMensagem = document.getElementById('formulario_mensagem');
const inputMensagem = document.getElementById('input_mensagem');
const inputImagem = document.getElementById('input_imagem');

// --- 2. Lógica para Enviar Mensagens de Texto ---
formularioMensagem.addEventListener('submit', (evento) => {
    evento.preventDefault(); // Impede o recarregamento da página

    const textoMensagem = inputMensagem.value.trim();

    if (textoMensagem) {
        // Adiciona a mensagem do usuário na tela
        adicionarMensagem(textoMensagem, 'mensagem_usuario');
        // Envia a mensagem para o servidor com o novo nome de evento
        socket.emit('enviar_mensagem', { mensagem: textoMensagem });
    }

    // Limpa o campo de texto
    inputMensagem.value = '';
});

// --- 3. Lógica para Enviar Imagens ---
inputImagem.addEventListener('change', (evento) => {
    const arquivo = evento.target.files[0];
    if (!arquivo) return;

    const leitor = new FileReader();
    leitor.onload = function (evento) {
        const dadosImagem = evento.target.result; // A imagem em formato base64

        // Adiciona a imagem na tela do usuário
        adicionarMensagem('', 'mensagem_usuario', dadosImagem);

        // Envia a imagem e um texto para o servidor
        socket.emit('enviar_mensagem', {
            mensagem: "Descreva esta imagem para mim, em português.",
            imagem: dadosImagem
        });
    };
    leitor.readAsDataURL(arquivo);
});


// --- 4. Lógica para Receber Mensagens do Servidor ---
// Ouvindo o novo nome de evento e usando a nova chave de dados
socket.on('resposta_servidor', (dados) => {
    adicionarMensagem(dados.resposta, 'mensagem_bot');
});

socket.on('conectar', () => {
    // Emitindo um evento 'conectar' para o backend registrar a conexão
    socket.emit('conectar');
    console.log('Conectado ao servidor com sucesso! ID:', socket.id);
});

// --- 5. Função Auxiliar para Adicionar Mensagens na Tela ---
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
    // Rola a caixa de chat para a última mensagem
    caixaChat.scrollTop = caixaChat.scrollHeight;
}