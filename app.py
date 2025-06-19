import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template
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
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Configuração do Modelo Gemini ---
modelo = genai.GenerativeModel("gemini-1.5-flash-latest")
chat_texto = modelo.start_chat(history=[])

# --- Funções do Socket.IO ---

@socketio.on('conectar')
def lidar_conexao():
    print('Cliente conectado com sucesso!')

@socketio.on('enviar_mensagem')
def lidar_mensagem_usuario(dados):
    mensagem_usuario = dados.get('mensagem', '')
    dados_arquivo = dados.get('arquivo')

    conteudo_para_gemini = [mensagem_usuario]
    resposta_final = ""

    try:
        if dados_arquivo:
            print('Arquivo recebido!')
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)

            if 'image' in cabecalho:
                print("Processando como imagem...")
                imagem = Image.open(io.BytesIO(dados_binarios))
                conteudo_para_gemini.append(imagem)
                # Para multimodal, usamos model.generate_content
                response = modelo.generate_content(conteudo_para_gemini)
                resposta_final = response.text

            elif 'pdf' in cabecalho:
                print("Processando como PDF...")
                texto_pdf = ""
                with fitz.open(stream=dados_binarios, filetype="pdf") as doc:
                    for pagina in doc:
                        texto_pdf += pagina.get_text()
                
                print(f"Texto extraído do PDF: {texto_pdf[:100]}...") # Log dos primeiros 100 caracteres
                
                # Adiciona o texto extraído ao prompt
                conteudo_para_gemini.append(f"\n\n--- CONTEÚDO DO PDF ---\n{texto_pdf}")
                
                # Envia como uma única string de texto para o chat
                prompt_completo = "\n".join(map(str, conteudo_para_gemini))
                response = chat_texto.send_message(prompt_completo)
                resposta_final = response.text
        else:
            # Se não houver arquivo, funciona como chat de texto contínuo
            print(f'Mensagem de texto recebida: "{mensagem_usuario}"')
            response = chat_texto.send_message(mensagem_usuario)
            resposta_final = response.text
        
        # Emite a resposta de volta para o frontend
        emit('resposta_servidor', {'resposta': resposta_final})

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