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
                const linkPdf = document.createElement('a');
                linkPdf.href = anexo.dados;
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
    
    socket.on('resposta_servidor', (dados) => {
        adicionarMensagem(dados.resposta, 'mensagem_bot');
    });

    socket.on('conectar', () => {
        socket.emit('conectar');
        console.log('Conectado ao servidor!');
    });
});