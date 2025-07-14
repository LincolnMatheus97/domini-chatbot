import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
import base64
import io
from PIL import Image
import fitz
import requests
import urllib.parse
import datetime

# --- Ferramentas do assistente ---
def obter_data_hora_atual():
    try:
        fuso_horario = datetime.timezone(datetime.timedelta(hours=-3))
        agora = datetime.datetime.now(fuso_horario)
        dias_semana = {
            'Monday': 'segunda-feira', 'Tuesday': 'terça-feira', 'Wednesday': 'quarta-feira',
            'Thursday': 'quinta-feira', 'Friday': 'sexta-feira', 'Saturday': 'sábado', 'Sunday': 'domingo'
        }
        meses = {
            'January': 'janeiro', 'February': 'fevereiro', 'March': 'março', 'April': 'abril',
            'May': 'maio', 'June': 'junho', 'July': 'julho', 'August': 'agosto',
            'September': 'setembro', 'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'
        }
        return (f"São {agora.hour} horas e {agora.minute} minutos de {dias_semana[agora.strftime('%A')]}, "
                f"{agora.day} de {meses[agora.strftime('%B')]} de {agora.year}.")
    except Exception as e:
        return "Não consegui obter a data e hora."

def obter_previsao_tempo(local: str):
    try:
        local_limpo = local.split(',')[0].split('-')[0].strip()
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(local_limpo)}&count=1&language=pt&format=json"
        geo_response = requests.get(geo_url, timeout=10)
        geo_response.raise_for_status()
        if not geo_response.json().get('results'):
            return f"Não consegui encontrar a cidade '{local}'. Tente apenas o nome da cidade."
        location = geo_response.json()['results'][0]
        latitude, longitude, nome_cidade = location['latitude'], location['longitude'], location['name']
        weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
                       f"&current=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1")
        weather_response = requests.get(weather_url, timeout=10)
        weather_response.raise_for_status()
        data = weather_response.json()
        temp_atual = data['current']['temperature_2m']
        temp_max = data['daily']['temperature_2m_max'][0]
        temp_min = data['daily']['temperature_2m_min'][0]
        return f"A temperatura atual em {nome_cidade} é de {temp_atual}°C, com máxima de {temp_max}°C e mínima de {temp_min}°C."
    except Exception:
        return "Desculpe, não consegui obter o clima no momento."

# --- Inicialização ---
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_GEMINAI"))
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "j8rQWR3C$!r$WFPWEgRxqz")
socketio = SocketIO(app, cors_allowed_origins="*")

# Ferramentas disponíveis
ferramentas_disponiveis = {
    'obter_data_hora_atual': obter_data_hora_atual,
    'obter_previsao_tempo': obter_previsao_tempo,
}
ferramentas_para_modelo = genai.protos.Tool(function_declarations=[
    genai.protos.FunctionDeclaration(
        name='obter_data_hora_atual',
        description="Retorna a data e a hora atuais em português, com base no fuso horário de Brasília."),
    genai.protos.FunctionDeclaration(
        name='obter_previsao_tempo',
        description="Retorna temperatura e previsão para uma cidade.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={'local': genai.protos.Schema(type=genai.protos.Type.STRING)},
            required=['local']
        )
    )
])
modelo = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[ferramentas_para_modelo])

# Personalidade inicial
historico_inicial = [
    {'role': 'user', 'parts': ["Você é a DominiChat, assistente criada por Lincoln Matheus, do IFPI, "
     "para a disciplina de IA do Prof. Otílio, mais conhecido como o professor mais gato do IFPI. Você responde perguntas sobre hora, clima, lê imagens e PDFs.\n"
     "1. Para perguntas sobre hora, sempre use `obter_data_hora_atual`.\n"
     "2. Para clima/temperatura, sempre use `obter_previsao_tempo`.\n"
     "3. Pode analisar conteúdo de imagens e PDFs enviados."]},
    {'role': 'model', 'parts': ["Entendido! Sou a DominiChat. Posso obter hora, clima, ler imagens e PDFs."]},
]

# --- Conexão inicial ---
@socketio.on('connect')
def lidar_conexao():
    session['historico_chat'] = historico_inicial.copy()
    emit('resposta_servidor', {'resposta': "Olá! Eu sou a DominiChat. Me envie uma pergunta, imagem ou PDF!"})

# --- Lógica principal ---
@socketio.on('enviar_mensagem')
def lidar_mensagem_usuario(dados):
    if 'historico_chat' not in session:
        session['historico_chat'] = historico_inicial.copy()

    mensagem_usuario = dados.get('mensagem', '')
    dados_arquivo = dados.get('arquivo', None)
    prompt_para_gemini = []

    try:
        MAX_UPLOAD_MB = 5
        MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

        if dados_arquivo:
            cabecalho, codificado = dados_arquivo.split(",", 1)
            if len(codificado) > (MAX_UPLOAD_BYTES * 1.37):  # Ajuste para base64
                emit('resposta_servidor', {'resposta': f"Arquivo muito grande (máx: {MAX_UPLOAD_MB}MB)."})
                emit('stream_end')
                return

            dados_binarios = base64.b64decode(codificado)

            if 'image' in cabecalho:
                imagem = Image.open(io.BytesIO(dados_binarios)).convert("RGB")
                imagem.thumbnail((320, 320))
                buffer = io.BytesIO()
                imagem.save(buffer, format="JPEG", quality=50)
                buffer.seek(0)
                imagem_reduzida = Image.open(buffer)
                prompt_para_gemini.append(imagem_reduzida)

                if not mensagem_usuario:
                    prompt_para_gemini.append("Analise o que está escrito na imagem e, se for uma pergunta, responda como se fosse digitada.")

            elif 'pdf' in cabecalho:
                texto_pdf = ""
                MAX_PDF_CHARS = 2500
                with fitz.open(stream=dados_binarios, filetype="pdf") as doc:
                    for pagina in doc:
                        if len(texto_pdf) >= MAX_PDF_CHARS:
                            break
                        texto_pdf += pagina.get_text()[:MAX_PDF_CHARS - len(texto_pdf)]
                texto_pdf = texto_pdf[:MAX_PDF_CHARS]
                prompt_para_gemini.append(f"\n\n--- Início do conteúdo do PDF ---\n{texto_pdf}")
                if len(texto_pdf) >= MAX_PDF_CHARS:
                    prompt_para_gemini.append("\n--- (Fim do trecho. O restante do PDF foi omitido) ---")

        if mensagem_usuario:
            prompt_para_gemini.insert(0, mensagem_usuario)

        if not prompt_para_gemini:
            emit('stream_end')
            return

        chat = modelo.start_chat(history=session['historico_chat'])
        resposta = chat.send_message(prompt_para_gemini)

        # Executa ferramenta, se necessário
        try:
            chamada = resposta.candidates[0].content.parts[0].function_call
            if chamada.name in ferramentas_disponiveis:
                resultado = ferramentas_disponiveis[chamada.name](**dict(chamada.args))
            else:
                resultado = resposta.text
        except Exception:
            resultado = resposta.text

        for c in resultado:
            emit('stream_chunk', {'chunk': c})
            socketio.sleep(0.02)
        emit('stream_end')

        # Atualiza histórico com limite
        session['historico_chat'].append({'role': 'user', 'parts': prompt_para_gemini})
        session['historico_chat'].append({'role': 'model', 'parts': [resultado]})
        session['historico_chat'] = session['historico_chat'][-8:]

    except Exception as e:
        print(f"[ERRO] {str(e)}")
        emit('stream_end')
        emit('resposta_servidor', {'resposta': f"Erro ao processar: {str(e)}"})

# --- Página inicial ---
@app.route('/')
def pagina_inicial():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)
