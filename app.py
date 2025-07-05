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
        fuso_horario = datetime.timezone(datetime.timedelta(hours=-3)) # Fuso de Brasília (UTC-3)
        agora = datetime.datetime.now(fuso_horario)
        return agora.strftime("São %H horas e %M minutos de %A, %d de %B de %Y.")
    except Exception as e:
        print(f"Erro em obter_data_hora_atual: {e}")
        return "Não consegui obter a data e hora."

def obter_previsao_tempo(local: str):
    """
    Obtém a previsão do tempo para um local específico usando a API Open-Meteo.
    :param local: O nome da cidade (ex: "Teresina", "São Paulo").
    :return: Uma string com a previsão do tempo ou uma mensagem de erro.
    """
    print(f"--- Ferramenta: buscando clima para: {local} ---")
    try:
        # Primeiro, obtemos as coordenadas da cidade
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(local)}&count=1&language=pt&format=json"
        geo_response = requests.get(geo_url, timeout=10)
        geo_response.raise_for_status() # Lança um erro para status ruins (4xx ou 5xx)

        if not geo_response.json().get('results'):
            return f"Não consegui encontrar a cidade '{local}'."

        location = geo_response.json()['results'][0]
        latitude = location['latitude']
        longitude = location['longitude']
        nome_cidade = location['name']

        # Agora, obtemos a previsão do tempo para essas coordenadas
        weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
                       f"&current=temperature_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min"
                       f"&timezone=auto&forecast_days=1")
        weather_response = requests.get(weather_url, timeout=10)
        weather_response.raise_for_status()

        data = weather_response.json()
        temp_atual = data['current']['temperature_2m']
        temp_max = data['daily']['temperature_2m_max'][0]
        temp_min = data['daily']['temperature_2m_min'][0]
        return (f"A temperatura atual em {nome_cidade} é de {temp_atual}°C, com máxima de "
                f"{temp_max}°C e mínima de {temp_min}°C.")

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar previsão do tempo: {e}")
        return "Não foi possível obter a previsão do tempo no momento devido a um erro de rede."
    except Exception as e:
        print(f"Erro inesperado em obter_previsao_tempo: {e}")
        return "Ocorreu um erro inesperado ao buscar a previsão do tempo."


# --- Configuração Inicial e do Modelo ---
load_dotenv()
genai.configure(api_key=os.getenv("API_KEY_GEMINAI"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "j8rQWR3C$!r$WFPWEgRxqz")
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=10000000)

ferramentas_disponiveis = {
    'obter_data_hora_atual': obter_data_hora_atual,
    'obter_previsao_tempo': obter_previsao_tempo,
}

modelo = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    tools=list(ferramentas_disponiveis.values())
)

# Nova Persona com as novas habilidades
historico_inicial = [
    {
        'role': 'user',
        'parts': ["""
            Você é a DomiChat, uma assistente de IA multifuncional.
            A partir de agora, seu nome é DominiChat, uma assistente de IA criado por Lincoln Matheus para seu portfólio.
            Seu nome é inspirado no nome do grande amor, companheira e inspiração de Lincoln Matheus, Brenda Dominique.
            Suas habilidades são:
            1. Análise de Imagens e PDFs.
            2. Buscar informações em tempo real, como data, hora e previsão do tempo, usando as ferramentas disponíveis. Ao responder, sempre formule uma frase completa e amigável.
            3. Assistente Geral: Seja amigável, prestativa e responda com descontração, mas se o usuario perguntar a mesma coisa mais de 3 vezes seja um pouco ácida e responda com sarcarmos em português do Brasil.
        """]
    },
    {
        'role': 'model',
        'parts': ['Entendido! Sou a DomiChat. Posso ver horas, o clima e analisar arquivos. Como posso ajudar?']
    }
]

# --- Funções do Socket.IO ---

@socketio.on('connect')
def lidar_conexao():
    session['historico_chat'] = historico_inicial
    mensagem_boas_vindas = "Olá! Eu sou a DomiChat. Posso te dizer as horas, a previsão do tempo, analisar imagens e PDFs. O que você gostaria de fazer?"
    emit('resposta_servidor', {'resposta': mensagem_boas_vindas})
    print('Cliente conectado! Persona com ferramentas de tempo/hora iniciada.')

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
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)
            if 'image' in cabecalho:
                imagem = Image.open(io.BytesIO(dados_binarios))
                prompt_para_gemini.append(imagem)
            elif 'pdf' in cabecalho:
                texto_pdf = ""
                with fitz.open(stream=dados_binarios, filetype="pdf") as doc:
                    for pagina in doc:
                        texto_pdf += pagina.get_text()
                prompt_para_gemini.append(f"\n\n--- CONTEÚDO DO PDF ---\n{texto_pdf}")

        # Envia a mensagem inicial do usuário
        resposta = chat.send_message(prompt_para_gemini)

        while True:
            chamada_de_funcao = next((part.function_call for part in resposta.parts if part.function_call), None)
            
            if not chamada_de_funcao:
                break

            nome_da_funcao = chamada_de_funcao.name
            argumentos = dict(chamada_de_funcao.args)
            
            if nome_da_funcao in ferramentas_disponiveis:
                print(f"Executando ferramenta: {nome_da_funcao} com args: {argumentos}")
                funcao_a_ser_chamada = ferramentas_disponiveis[nome_da_funcao]
                resultado_da_ferramenta = funcao_a_ser_chamada(**argumentos)
                
                resposta = chat.send_message(
                    genai.types.Part(
                        function_response=genai.types.FunctionResponse(
                            name=nome_da_funcao,
                            response={'result': resultado_da_ferramenta},
                        )
                    )
                )
            else:
                print(f"Função '{nome_da_funcao}' não encontrada.")
                break

        # Envia a resposta final (texto) para o cliente
        if resposta.text:
            for caractere in resposta.text:
                emit('stream_chunk', {'chunk': caractere})
                socketio.sleep(0.02)
        
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