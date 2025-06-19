# app.py

import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import base64
import io
from PIL import Image

# --- Configuração Inicial ---
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_GEMINAI"))

# --- Cria a Aplicação Flask ---
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Configuração do Modelo Gemini ---
modelo = genai.GenerativeModel("gemini-1.5-flash-latest")
chat_texto = modelo.start_chat(history=[]) # Chat para conversas apenas de texto

# --- Eventos do Socket.IO ---

@socketio.on('conectar')
def lidar_conexao():
    """Esta função é chamada quando um novo usuário se conecta."""
    print('Cliente conectado com sucesso!')

@socketio.on('enviar_mensagem') # Ouvindo o evento 'enviar_mensagem'
def lidar_mensagem_usuario(dados):
    """
    Recebe uma mensagem do usuário via WebSocket, envia para o Gemini
    e emite a resposta de volta para o mesmo usuário.
    """
    mensagem_usuario = dados.get('mensagem', '')
    dados_imagem = dados.get('imagem')

    print(f'Mensagem recebida: "{mensagem_usuario}"')
    if dados_imagem:
        print('Imagem recebida!')

    try:
        # --- LÓGICA ATUALIZADA ---
        if dados_imagem:
            # 1. Decodificar a imagem Base64
            cabecalho, codificado = dados_imagem.split(",", 1)
            dados_binarios = base64.b64decode(codificado)
            
            # 2. Abrir a imagem com a biblioteca PIL
            imagem = Image.open(io.BytesIO(dados_binarios))

            # 3. Enviar texto + imagem para o Gemini
            resposta = modelo.generate_content([mensagem_usuario, imagem])
        else:
            # Se não houver imagem, usa o chat contínuo apenas de texto
            resposta = chat_texto.send_message(mensagem_usuario)

        # Emite a resposta de volta para o frontend
        # A chave do dicionário 'resposta' deve ser a mesma lida no script.js
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
