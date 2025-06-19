import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

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
    """
    Recebe uma mensagem do usuário via WebSocket, envia para o Gemini
    e emite a resposta de volta para o mesmo usuário.
    """
    user_message = data['message']
    print(f'Mensagem recebida: {user_message}')
    
    try:
        # Envia a mensagem para o Gemini
        response = chat.send_message(user_message)
        
        # Emite um evento 'server_response' de volta para o frontend
        emit('server_response', {'reply': response.text})
        
    except Exception as e:
        print(f'Erro: {str(e)}')
        emit('server_response', {'reply': f'Ocorreu um erro: {str(e)}'})

# --- Rota HTTP para verificar se a API está no ar  ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Execução Local ---
if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)