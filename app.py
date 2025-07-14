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

# --- 1. DEFINIÇÃO DAS FERRAMENTAS ---

def obter_data_hora_atual():
    """Retorna a data e a hora atuais formatadas em português para o fuso horário de Brasília."""
    print("--- Ferramenta: obtendo data e hora atual ---")
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

        dia_semana_en = agora.strftime('%A')
        mes_en = agora.strftime('%B')
        dia_semana_pt = dias_semana.get(dia_semana_en, dia_semana_en)
        mes_pt = meses.get(mes_en, mes_en)

        return (f"São {agora.hour} horas e {agora.minute} minutos de {dia_semana_pt}, "
                f"{agora.day} de {mes_pt} de {agora.year}.")

    except Exception as e:
        print(f"Erro em obter_data_hora_atual: {e}")
        return "Não consegui obter a data e hora."


def obter_previsao_tempo(local: str):
    """Obtém a previsão do tempo para um local específico usando a API Open-Meteo."""
    print(f"--- Ferramenta: buscando clima para: {local} ---")
    try:
        local_limpo = local.split(',')[0].split('-')[0].strip()
        print(f"--- Localização limpa para a API: {local_limpo} ---")

        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(local_limpo)}&count=1&language=pt&format=json"
        geo_response = requests.get(geo_url, timeout=10)
        geo_response.raise_for_status()

        if not geo_response.json().get('results'):
            return f"Não consegui encontrar a cidade '{local}'. Por favor, tente digitar apenas o nome da cidade."

        location = geo_response.json()['results'][0]
        latitude, longitude, nome_cidade = location['latitude'], location['longitude'], location['name']

        weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
                       f"&current=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1")

        weather_response = requests.get(weather_url, timeout=10)
        weather_response.raise_for_status()

        data = weather_response.json()
        temp_atual = data['current']['temperature_2m']
        temp_max, temp_min = data['daily']['temperature_2m_max'][0], data['daily']['temperature_2m_min'][0]

        return f"A temperatura atual em {nome_cidade} é de {temp_atual}°C, com máxima de {temp_max}°C e mínima de {temp_min}°C."

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão em obter_previsao_tempo: {e}")
        return "Desculpe, não consegui me conectar ao serviço de meteorologia no momento."
    except Exception as e:
        print(f"Erro inesperado em obter_previsao_tempo: {e}")
        return "Ocorreu um erro inesperado ao buscar a previsão do tempo."

# --- Configuração Inicial e do Modelo ---
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_GEMINAI"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "j8rQWR3C$!r$WFPWEgRxqz")
socketio = SocketIO(app, cors_allowed_origins="*")

ferramentas_disponiveis = {
    'obter_data_hora_atual': obter_data_hora_atual,
    'obter_previsao_tempo': obter_previsao_tempo,
}

ferramentas_para_modelo = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(name='obter_data_hora_atual', description="Retorna a data e a hora atuais formatadas em português para o fuso horário de Brasília."),
        genai.protos.FunctionDeclaration(name='obter_previsao_tempo', description="Obtém a previsão do tempo ou temperatura para uma cidade específica.",
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT,
                properties={'local': genai.protos.Schema(type=genai.protos.Type.STRING, description="A cidade para buscar a previsão do tempo ou temperatura (ex: 'Teresina, PI')")},
                required=['local']))])

modelo = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[ferramentas_para_modelo])

historico_inicial = [
    {'role': 'user', 'parts': ["Você é a DominiChat, uma assistente de IA multifuncional. "
        "Criada por Lincoln Matheus, aluno do Instituto Federal do Piaui - IFPI. Para matéria de Intelignecia Artificial do Prof.Dr. Otílio Paulo, conhecido como o professor mais gato do instituto. "
        "Seu nome foi dado em homenagem ao grande amor, inspiração e companheira, Brenda Dominique. Uma pessoa incrivel, criativa, inteligente e bondosa."
        "Suas instruções são claras e você deve segui-las rigorosamente:\n"
        "1. Para qualquer pergunta sobre data ou hora atual, você **obrigatoriamente** deve chamar a ferramenta `obter_data_hora_atual` e retornar a informação formatada.\n"
        "2. Para qualquer pergunta sobre tempo, clima ou temperatura de uma cidade, você **obrigatoriamente** deve chamar a ferramenta `obter_previsao_tempo` com o nome da cidade extraído da pergunta do usuário.\n"
        "3. Você pode analisar o conteúdo de imagens e arquivos PDF enviados pelo usuário.\n"]},
    {'role': 'model', 'parts': ['Entendido! Sou a DominiChat. Minhas instruções são claras. Posso obter a hora, o clima e analisar arquivos. Como posso ajudar?']}
]

# --- Funções do Socket.IO ---

@socketio.on('connect')
def lidar_conexao():
    session['historico_chat'] = historico_inicial
    mensagem_boas_vindas = "Olá! Eu sou a DominiChat. Posso te dizer as horas, a previsão do tempo, analisar imagens e PDFs. O que você gostaria de fazer?"
    emit('resposta_servidor', {'resposta': mensagem_boas_vindas})
    print('Cliente conectado! Persona com ferramentas de tempo/hora iniciada.')

@socketio.on('enviar_mensagem')
def lidar_mensagem_usuario(dados):
    if 'historico_chat' not in session:
        session['historico_chat'] = historico_inicial

    mensagem_usuario, dados_arquivo = dados.get('mensagem', ''), dados.get('arquivo')

    try:
        prompt_para_gemini = []
        if mensagem_usuario:
            prompt_para_gemini.append(mensagem_usuario)

        if dados_arquivo:
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)

            if 'image' in cabecalho:
                imagem_original = Image.open(io.BytesIO(dados_binarios)).convert("RGB")
                imagem_original.thumbnail((512, 512))
                imagem_processada = io.BytesIO()
                imagem_original.save(imagem_processada, format="JPEG", quality=70)
                imagem_processada.seek(0)
                imagem_final = Image.open(imagem_processada)
                prompt_para_gemini.append(imagem_final)

            elif 'pdf' in cabecalho:
                MAX_PDF_CHARS = 2500
                texto_pdf = ""
                with fitz.open(stream=dados_binarios, filetype="pdf") as doc:
                    for pagina in doc:
                        texto_pdf += pagina.get_text()
                        if len(texto_pdf) >= MAX_PDF_CHARS:
                            break
                texto_pdf = texto_pdf[:MAX_PDF_CHARS]
                prompt_para_gemini.append(f"\n\n--- Início do conteúdo do PDF ---\n{texto_pdf}")
                if len(texto_pdf) >= MAX_PDF_CHARS:
                    prompt_para_gemini.append("\n--- (Fim do trecho. O restante do PDF foi omitido) ---")

        if not prompt_para_gemini:
            emit('stream_end')
            return

        chat = modelo.start_chat(history=session['historico_chat'])
        resposta_do_modelo = chat.send_message(prompt_para_gemini, stream=True)

        texto_completo_stream = ""
        for chunk in resposta_do_modelo:
            if chunk.text:
                texto_para_stream = chunk.text
                texto_completo_stream += texto_para_stream
                for caractere in texto_para_stream:
                    emit('stream_chunk', {'chunk': caractere})
                    socketio.sleep(0.02)

        emit('stream_end')

        session['historico_chat'].append({'role': 'user', 'parts': prompt_para_gemini})
        session['historico_chat'].append({'role': 'model', 'parts': [texto_completo_stream]})

    except Exception as e:
        print(f'Erro no backend: {type(e).__name__}: {str(e)}')
        emit('stream_end')
        emit('resposta_servidor', {'resposta': f'Ocorreu um erro no servidor: {str(e)}'})

# --- Rota e Execução ---

@app.route('/')
def pagina_inicial():
    return render_template('index.html')

if __name__ == '__main__':
    porta = int(os.getenv("PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=porta, debug=False)
