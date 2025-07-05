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

        # Mapas para tradução manual, garantindo que funcione em qualquer sistema
        dias_semana = {
            'Monday': 'segunda-feira', 'Tuesday': 'terça-feira', 'Wednesday': 'quarta-feira',
            'Thursday': 'quinta-feira', 'Friday': 'sexta-feira', 'Saturday': 'sábado', 'Sunday': 'domingo'
        }
        meses = {
            'January': 'janeiro', 'February': 'fevereiro', 'March': 'março', 'April': 'abril',
            'May': 'maio', 'June': 'junho', 'July': 'julho', 'August': 'agosto',
            'September': 'setembro', 'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'
        }

        # Obtém os nomes em inglês para usar como chave
        dia_semana_en = agora.strftime('%A')
        mes_en = agora.strftime('%B')

        # Busca a tradução nos nossos mapas
        dia_semana_pt = dias_semana.get(dia_semana_en, dia_semana_en)
        mes_pt = meses.get(mes_en, mes_en)

        # Monta a string final com os valores traduzidos
        return (f"São {agora.hour} horas e {agora.minute} minutos de {dia_semana_pt}, "
                f"{agora.day} de {mes_pt} de {agora.year}.")

    except Exception as e:
        print(f"Erro em obter_data_hora_atual: {e}")
        return "Não consegui obter a data e hora."

def obter_previsao_tempo(local: str):
    """Obtém a previsão do tempo para um local específico usando a API Open-Meteo."""
    print(f"--- Ferramenta: buscando clima para: {local} ---")
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(local)}&count=1&language=pt&format=json"
        geo_response = requests.get(geo_url, timeout=10)
        geo_response.raise_for_status()
        if not geo_response.json().get('results'):
            return f"Não consegui encontrar a cidade '{local}'."
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
        genai.protos.FunctionDeclaration(name='obter_previsao_tempo', description="Obtém a previsão do tempo para uma cidade específica.",
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT,
                properties={'local': genai.protos.Schema(type=genai.protos.Type.STRING, description="A cidade para buscar a previsão do tempo (ex: 'Teresina, PI')")},
                required=['local']))])

modelo = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[ferramentas_para_modelo])

historico_inicial = [
    {'role': 'user', 'parts': ["Você é a DominiChat, uma assistente de IA multifuncional criada por Lincoln Matheus, inspirada em seu grande amor, Brenda Dominique. Suas habilidades são: 1. Análise de Imagens e PDFs. 2. Buscar informações como data, hora e previsão do tempo. 3. Ser amigável e prestativa, mas com um toque de sarcasmo se o usuário repetir a mesma pergunta mais de 3 vezes."]},
    {'role': 'model', 'parts': ['Entendido! Sou a DominiChat. Posso ver horas, o clima e analisar arquivos. Como posso ajudar?']}
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

    chat = modelo.start_chat(history=session['historico_chat'])
    mensagem_usuario, dados_arquivo = dados.get('mensagem', ''), dados.get('arquivo')

    try:
        prompt_para_gemini = [mensagem_usuario] if mensagem_usuario else []
        if dados_arquivo:
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)
            if 'image' in cabecalho:
                prompt_para_gemini.append(Image.open(io.BytesIO(dados_binarios)))
            elif 'pdf' in cabecalho:
                texto_pdf = "".join(pagina.get_text() for pagina in fitz.open(stream=dados_binarios, filetype="pdf"))
                prompt_para_gemini.append(f"\n\n--- CONTEÚDO DO PDF ---\n{texto_pdf}")

        primeira_resposta = chat.send_message(prompt_para_gemini)

        try:
            chamada_de_funcao = primeira_resposta.candidates[0].content.parts[0].function_call
            if not chamada_de_funcao.name: raise AttributeError("Chamada sem nome")
        except (AttributeError, IndexError):
            if primeira_resposta.text:
                for caractere in primeira_resposta.text: emit('stream_chunk', {'chunk': caractere}); socketio.sleep(0.02)
                emit('stream_end')
                session['historico_chat'] = chat.history
            return

        nome_da_funcao, argumentos = chamada_de_funcao.name, dict(chamada_de_funcao.args)
        
        if nome_da_funcao in ferramentas_disponiveis:
            print(f"Executando ferramenta: {nome_da_funcao} com args: {argumentos}")
            resultado_da_ferramenta = ferramentas_disponiveis[nome_da_funcao](**argumentos)
            
            resposta_final = chat.send_message(genai.protos.Part(function_response=genai.protos.FunctionResponse(
                name=nome_da_funcao, response={'result': resultado_da_ferramenta})))
            
            if resposta_final.text:
                for caractere in resposta_final.text: emit('stream_chunk', {'chunk': caractere}); socketio.sleep(0.02)
        else:
            print(f"Função '{nome_da_funcao}' não encontrada.")
            emit('resposta_servidor', {'resposta': "Desculpe, tentei usar uma ferramenta que não conheço."})

        emit('stream_end')
        session['historico_chat'] = chat.history

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