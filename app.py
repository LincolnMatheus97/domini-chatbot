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
model = genai.GenerativeModel("gemini-1.5-flash-latest")
chat = model.start_chat(history=[])

# --- Eventos do Socket.IO ---

@socketio.on('connect')
def handle_connect():
    """Esta função é chamada quando um novo usuário se conecta."""
    print('Cliente conectado com sucesso!')

@socketio.on('handle_message') # Ouvindo o evento 'handle_message'
def handle_user_message(data):
    user_message = data.get('message', '') # Pega a mensagem, se existir
    image_data = data.get('image') # Pega a imagem, se existir

    print(f'Mensagem recebida: "{user_message}"')
    if image_data:
        print('Imagem recebida!')

    try:
        # --- LÓGICA ATUALIZADA ---
        if image_data:
            # 1. Decodificar a imagem Base64
            # A imagem vem como "data:image/jpeg;base64,ABCD...", precisamos tirar o cabeçalho
            header, encoded = image_data.split(",", 1)
            binary_data = base64.b64decode(encoded)
            
            # 2. Abrir a imagem com a biblioteca PIL (Pillow)
            img = Image.open(io.BytesIO(binary_data))

            # 3. Enviar texto + imagem para o Gemini
            # Para multimodal, usamos model.generate_content com uma lista de conteúdos
            response = model.generate_content([user_message, img])
        else:
            # Se não houver imagem, funciona como antes (só texto)
            response = chat.send_message(user_message)

        # Emite a resposta de volta para o frontend
        emit('server_response', {'reply': response.text})

    except Exception as e:
        print(f'Erro: {str(e)}')
        emit('server_response', {'reply': f'Ocorreu um erro ao processar sua solicitação: {str(e)}'})

# --- Rota HTTP para verificar se a API está no ar  ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Execução Local ---
if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)