import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify

# --- Configuração Inicial ---
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_GEMINAI"))

# --- Cria a Aplicação Flask ---
app = Flask(__name__)

# --- Configuração do Modelo Gemini ---
model = genai.GenerativeModel("gemini-1.5-flash-latest")
chat = model.start_chat(history=[])

# --- Criação do Endpoint da API ---
@app.route('/chat', methods=['POST'])
def handle_chat():
    # Pega a mensagem enviada pelo frontend no formato JSON
    # Ex: {"message": "Qual a capital do Piauí?"}
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"error": "Nenhuma mensagem fornecida"}), 400

    user_message = data['message']

    try:
        # Envia a mensagem para o Gemini
        response = chat.send_message(user_message)
        
        # Retorna a resposta do Gemini para o frontend
        return jsonify({"reply": response.text})
    except Exception as e:
        # Retorna uma mensagem de erro se algo der errado
        return jsonify({"error": str(e)}), 500

# Rota principal para verificar se a API está no ar
@app.route('/')
def index():
    return "API do Chatbot Gemini está no ar!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)