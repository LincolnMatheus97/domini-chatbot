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

// Selecionando os elementos do HTML
const chatBox = getById('chat-box');
const messageForm = getById('message-form');
const messageInput = getById('message-input');
const imageInput = getById('image-input');

// --- 2. Lógica para Enviar Mensagens ---
messageForm.addEventListener('submit', (e) => {
    e.preventDefault(); // Impede o recarregamento da página

    const messageText = messageInput.value.trim();

    if (messageText) {
        // Adiciona a mensagem do usuário na tela
        addMessage(messageText, 'user-message');
        // Envia a mensagem para o servidor via WebSocket
        socket.emit('handle_message', { message: messageText });
    }

    // Limpa o campo de texto
    messageInput.value = '';
});

// --- Lógica para Enviar Imagens ---
imageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (event) {
        const imageData = event.target.result; // A imagem em formato base64

        // Adiciona a imagem na tela do usuário
        addMessage('', 'user-message', imageData);

        // Envia a imagem e um texto opcional para o servidor
        // (O backend atual só processa texto, mas está preparado para receber mais)
        // Para o Gemini analisar a imagem, o backend precisa ser ajustado.
        socket.emit('handle_message', {
            message: "Descreva esta imagem para mim.",
            image: imageData
        });
    };
    reader.readAsDataURL(file);
});


// --- 3. Lógica para Receber Mensagens ---
socket.on('server_response', (data) => {
    addMessage(data.reply, 'bot-message');
});

socket.on('connect', () => {
    console.log('Conectado ao servidor com sucesso! ID:', socket.id);
});

// --- 4. Função Auxiliar para Adicionar Mensagens na Tela ---
function addMessage(text, className, imageData = null) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', className);

    if (text) {
        messageElement.innerText = text;
    }

    if (imageData) {
        const imgElement = document.createElement('img');
        imgElement.src = imageData;
        messageElement.appendChild(imgElement);
    }

    chatBox.appendChild(messageElement);
    // Rola a caixa de chat para a última mensagem
    chatBox.scrollTop = chatBox.scrollHeight;
}