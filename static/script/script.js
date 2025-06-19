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

document.addEventListener('DOMContentLoaded', () => {

    // --- 1. Seleção de Elementos ---
    const socket = io();
    const caixaChat = getById('caixa_chat');
    const inputMensagem = getById('input_mensagem');
    const inputArquivo = getById('input_arquivo');
    const previewAnexo = getById('preview_anexo');
    const previewImagem = getById('preview_imagem');
    const previewPdfNome = getById('preview_pdf_nome');

    let anexoTemporario = null;

    // --- 2. Ligando os Eventos às Funções de Callback ---
    
    capturarClick('botao_abrir_menu', lidarCliqueMenu);
    capturarClick('anexar_imagem_btn', lidarCliqueAnexarImagem);
    capturarClick('anexar_pdf_btn', lidarCliqueAnexarPdf);
    capturarClick('remover_anexo_btn', lidarCliqueRemoverAnexo);
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

        adicionarMensagem(textoMensagem, 'mensagem_usuario', anexoTemporario ? anexoTemporario.dados : null);

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
    
    function adicionarMensagem(texto, classeCss, dadosImagem = null) {
        const elementoMensagem = document.createElement('div');
        elementoMensagem.classList.add('mensagem', classeCss);
        if (texto) {
            const textoEl = document.createElement('p');
            textoEl.innerText = texto;
            elementoMensagem.appendChild(textoEl);
        }
        if (dadosImagem && dadosImagem.startsWith('data:image')) {
            const imgEl = document.createElement('img');
            imgEl.src = dadosImagem;
            elementoMensagem.appendChild(imgEl);
        }
        caixaChat.appendChild(elementoMensagem);
        caixaChat.scrollTop = caixaChat.scrollHeight;
    }
    
    socket.on('resposta_servidor', (dados) => {
        adicionarMensagem(dados.resposta, 'mensagem_bot');
    });

    socket.on('conectar', () => {
        socket.emit('conectar');
        console.log('Conectado ao servidor!');
    });
});