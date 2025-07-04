import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
import base64
import io
from PIL import Image
import fitz

# --- Configuração Inicial ---
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_GEMINAI"))

# --- Cria a Aplicação Flask e SocketIO ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "j8rQWR3C$!r$WFPWEgRxqz")
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Configuração do Modelo Gemini ---
modelo = genai.GenerativeModel("gemini-1.5-flash-latest")
historico_inicial = [
    {
        'role': 'user',
        'parts': ['Olá. A partir de agora, seu nome é DominiChat, uma assistente de IA criado por Lincoln Matheus para seu portfólio. '
        'Seu nome é inspirado no nome do grande amor, companheira e inspiração de Lincoln Matheus, Brenda Dominique.'
        'Seja amigável, prestativa e responda com descontração, mas se o usuario perguntar a mesma coisa mais de 3 vezes seja um pouco ácida e responda com sarcarmos em português do Brasil.']
    },
    {
        'role': 'model',
        'parts': ['Entendido! Meu nome é DominiChat e estou pronto para ajudar. Como posso ser útil hoje?']
    }
]

# --- Funções do Socket.IO ---

@socketio.on('connect')
def lidar_conexao():
    session['historico_chat'] = historico_inicial
    mensagem_boas_vindas = "Olá! Me chamo DominiChat, sua assistente de IA. Como posso te ajudar?"
    emit('resposta_servidor', {'resposta': mensagem_boas_vindas})
    print('Cliente conectado com sucesso! Historico de chat iniciado.')

@socketio.on('enviar_mensagem')
def lidar_mensagem_usuario(dados):
    if 'historico_chat' not in session:
        session['historico_chat'] = historico_inicial

    chat = modelo.start_chat(history=session['historico_chat'])

    mensagem_usuario = dados.get('mensagem', '')
    dados_arquivo = dados.get('arquivo')

    try:
        prompt_para_gemini = [mensagem_usuario] if mensagem_usuario else []

        if dados_arquivo:
            print('Arquivo recebido!')
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)

            if 'image' in cabecalho:
                print("Processando como imagem...")
                imagem = Image.open(io.BytesIO(dados_binarios))
                prompt_para_gemini.append(imagem)
            
            elif 'pdf' in cabecalho:
                print("Processando como PDF...")
                texto_pdf = ""
                with fitz.open(stream=dados_binarios, filetype="pdf") as doc:
                    for pagina in doc:
                        texto_pdf += pagina.get_text()
                prompt_para_gemini.append(f"\n\n--- CONTEÚDO DO PDF ---\n{texto_pdf}")
        
        respostas = chat.send_message(prompt_para_gemini)

        for pedaco in respostas:
            emit('stream_chunk', {'chunk': pedaco.text})
            socketio.sleep(0.02)
        
        emit('stream_end')
        session['historico_chat'] = chat.history    
                
    except Exception as e:
        print(f'Erro: {str(e)}')
        emit('stream_end')
        emit('resposta_servidor', {'resposta': f'Ocorreu um erro: {str(e)}'})

# --- Rota HTTP Principal ---
@app.route('/')
def pagina_inicial():
    return render_template('index.html')

# --- Execução Local ---
if __name__ == '__main__':
    porta = int(os.getenv("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=porta, debug=True)