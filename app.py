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
        'parts': ['Olá. A partir de agora, seu nome é L²NT, um assistente de IA criado por Lincoln Matheus para seu portfólio. Seja sempre amigável, prestativo e responda em português do Brasil.']
    },
    {
        'role': 'model',
        'parts': ['Entendido! Meu nome é L²NT e estou pronto para ajudar. Como posso ser útil hoje?']
    }
]

# --- Funções do Socket.IO ---

@socketio.on('conectar')
def lidar_conexao():
    session['historico_chat'] = historico_inicial
    primeira_mensagem_bot = historico_inicial[1]['parts'][0]
    emit('resposta_servidor', {'resposta': primeira_mensagem_bot})
    print('Cliente conectado com sucesso! Historico de chat iniciado.')

@socketio.on('enviar_mensagem')
def lidar_mensagem_usuario(dados):
    if 'historico_chat' not in session:
        session['historico_chat'] = historico_inicial

    mensagem_usuario = dados.get('mensagem', '')
    dados_arquivo = dados.get('arquivo')

    try:
        if dados_arquivo and 'image' in dados_arquivo:
            print("Processando como imagem...")
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)
            imagem = Image.open(io.BytesIO(dados_binarios))
            
            prompt_completo_usuario = [mensagem_usuario, imagem]
            
            resposta = modelo.generate_content(session['historico_chat'] + prompt_completo_usuario)
            
            session['historico_chat'].append({'role': 'user', 'parts': [mensagem_usuario, imagem]})
            session['historico_chat'].append({'role': 'model', 'parts': [resposta.text]})
            
        else:
            chat = modelo.start_chat(history=session['historico_chat'])
            prompt_para_gemini = [mensagem_usuario] if mensagem_usuario else []

            if dados_arquivo and 'pdf' in dados_arquivo:
                print("Processando como PDF...")
                cabecalho, codificado = dados_arquivo.split(",", 1)
                dados_binarios = base64.b64decode(codificado)
                texto_pdf = ""
                with fitz.open(stream=dados_binarios, filetype="pdf") as doc:
                    for pagina in doc:
                        texto_pdf += pagina.get_text()
                prompt_para_gemini.append(f"\n\n--- CONTEÚDO DO PDF ---\n{texto_pdf}")
            
            resposta = chat.send_message(prompt_para_gemini)
            
            session['historico_chat'] = chat.history
            
        emit('resposta_servidor', {'resposta': resposta.text})       
                
    except Exception as e:
        print(f'Erro: {str(e)}')
        emit('resposta_servidor', {'resposta': f'Ocorreu um erro: {str(e)}'})

# --- Rota HTTP Principal ---
@app.route('/')
def pagina_inicial():
    return render_template('index.html')

# --- Execução Local ---
if __name__ == '__main__':
    porta = int(os.getenv("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=porta, debug=True)