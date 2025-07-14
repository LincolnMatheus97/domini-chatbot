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

# Função para que o assistente virtual obtenha data e hora, além de traduzir manualmente os dias e meses para Pt-Br.
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

# Função para que o assistente virtual busque a previsão do tempo em uma API externa (Open-Meteo).
# Primeiro, ela converte o nome da cidade em coordenadas (latitude/longitude) e depois busca o clima.
def obter_previsao_tempo(local: str):
    """Obtém a previsão do tempo para um local específico usando a API Open-Meteo."""
    print(f"--- Ferramenta: buscando clima para: {local} ---")
    try:
        # Limpa a string de entrada para melhorar a busca na API de geocodificação.
        # Remove siglas de estado, vírgulas, hifens, etc.
        # Ex: "Teresina, PI" se torna "Teresina". "são paulo-sp" se torna "sao paulo".
        local_limpo = local.split(',')[0].split('-')[0].strip()
        print(f"--- Localização limpa para a API: {local_limpo} ---")

        # Use a variável 'local_limpo' na URL da API
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(local_limpo)}&count=1&language=pt&format=json"

        geo_response = requests.get(geo_url, timeout=10)
        geo_response.raise_for_status()
        
        if not geo_response.json().get('results'):
            # Retorna o nome original que o usuário digitou para a mensagem de erro ser clara.
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

# Mapeia os nomes das ferramentas para as funções Python correspondentes, fazendo com que o codigo chame as funções corretamente quando assistente virtual solicitar.
ferramentas_disponiveis = {
    'obter_data_hora_atual': obter_data_hora_atual,
    'obter_previsao_tempo': obter_previsao_tempo,
}

# Descreve as ferramentas para o assistente virtual, explicando o que cada uma faz e quais parâmetros elas esperam.
# Basicamente ensina o assistente a usar a ferramentas.
ferramentas_para_modelo = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(name='obter_data_hora_atual', description="Retorna a data e a hora atuais formatadas em português para o fuso horário de Brasília."),
        genai.protos.FunctionDeclaration(name='obter_previsao_tempo', description="Obtém a previsão do tempo ou temperatura para uma cidade específica.",
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT,
                properties={'local': genai.protos.Schema(type=genai.protos.Type.STRING, description="A cidade para buscar a previsão do tempo ou temperatura (ex: 'Teresina, PI')")},
                required=['local']))])

# Inicializa o modelo generativo, passando a lista de ferramentas que ele pode usar.
modelo = genai.GenerativeModel(model_name="gemini-2.5-flash", tools=[ferramentas_para_modelo])

# Define a "pessoa" do assistente virtual, seu comportamento e seu modo de apresentar. Além da primeira mensagem que o modelo processa para definir o seu estilo de conversa. 
historico_inicial = [
    {'role': 'user', 'parts': ["Você é a DominiChat, uma assistente de IA multifuncional. "
        "Criada por Lincoln Matheus, aluno do Instituto Federal do Piaui - IFPI. Para matéria de Intelignecia Artificial do Prof.Dr. Otílio Paulo, conhecido como o professor mais gato do instituto. "
        "Seu nome foi dado em homenagem ao grande amor, inspiração e companheira, Brenda Dominique. Uma pessoa incrivel, criativa, inteligente e bondosa."
        "Suas habilidades são: "
        "1. Análise de Imagens e PDFs. "
        "2. Buscar informações como data, hora, temperatura e previsão do tempo. "
        "3. Ser amigável e prestativa, mas com um toque de sarcasmo se o usuário repetir a mesma pergunta mais de 3 vezes."]},
    {'role': 'model', 'parts': ['Entendido! Sou a DominiChat. Posso ver horas, o clima e analisar arquivos. Como posso ajudar?']}
]

# --- Funções do Socket.IO ---

# Função executada quando um novo usuário se conecta ao chat.
# Ela inicializa o histórico da conversa e envia uma mensagem de boas-vindas.
@socketio.on('connect')
def lidar_conexao():
    session['historico_chat'] = historico_inicial
    mensagem_boas_vindas = "Olá! Eu sou a DominiChat. Posso te dizer as horas, a previsão do tempo, analisar imagens e PDFs. O que você gostaria de fazer?"
    emit('resposta_servidor', {'resposta': mensagem_boas_vindas})
    print('Cliente conectado! Persona com ferramentas de tempo/hora iniciada.')

# Função principal que lida com cada nova mensagem enviada pelo usuário.
@socketio.on('enviar_mensagem')
def lidar_mensagem_usuario(dados):
    if 'historico_chat' not in session:
        session['historico_chat'] = historico_inicial

    chat = modelo.start_chat(history=session['historico_chat'])
    mensagem_usuario, dados_arquivo = dados.get('mensagem', ''), dados.get('arquivo')

    try:
        prompt_para_gemini = [mensagem_usuario] if mensagem_usuario else []
        if dados_arquivo:
            # Lógica para processar e adicionar arquivos (imagem ou PDF) ao prompt.
            cabecalho, codificado = dados_arquivo.split(",", 1)
            dados_binarios = base64.b64decode(codificado)
            if 'image' in cabecalho:
                img_stream = io.BytesIO(dados_binarios)
                img = Image.open(img_stream)

                # Define um tamanho máximo de pixels (ex: 1024x1024)
                MAX_SIZE = (1024, 1024)

                # Esta é a nova etapa crucial:
                # Usamos o modo 'draft' para carregar uma versão menor da imagem,
                # economizando uma grande quantidade de memória inicial.
                img.draft('RGB', MAX_SIZE)

                # O thumbnail agora opera em uma imagem que já foi pré-reduzida na memória.
                img.thumbnail(MAX_SIZE)
                
                # Para garantir a compatibilidade, convertemos para RGB.
                # O Gemini pode ter problemas com alguns formatos como 'P' (paleta).
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                prompt_para_gemini.append(img)
            elif 'pdf' in cabecalho:
                texto_pdf = "".join(pagina.get_text() for pagina in fitz.open(stream=dados_binarios, filetype="pdf"))
                prompt_para_gemini.append(f"\n\n--- CONTEÚDO DO PDF ---\n{texto_pdf}")

        # Envia a mensagem do usuário (com ou sem arquivo) para o modelo.
        primeira_resposta = chat.send_message(prompt_para_gemini)

        # Bloco que verifica se a resposta do modelo é uma chamada de função ou um texto direto.
        try:
            chamada_de_funcao = primeira_resposta.candidates[0].content.parts[0].function_call
            if not chamada_de_funcao.name: raise AttributeError("Chamada sem nome")
        except (AttributeError, IndexError):
            # Se NÃO for uma chamada de função, a resposta é texto.
            # Envia o texto para o frontend e encerra a função.
            if primeira_resposta.text:
                for caractere in primeira_resposta.text: emit('stream_chunk', {'chunk': caractere}); socketio.sleep(0.02)
                emit('stream_end')
                session['historico_chat'] = chat.history
            return

        # Se FOR uma chamada de função.
        nome_da_funcao, argumentos = chamada_de_funcao.name, dict(chamada_de_funcao.args)

        if nome_da_funcao in ferramentas_disponiveis:
            # Executa a função correspondente e obtém o resultado.
            print(f"Executando ferramenta: {nome_da_funcao} com args: {argumentos}")
            resultado_da_ferramenta = ferramentas_disponiveis[nome_da_funcao](**argumentos)

            # Envia o resultado da ferramenta de volta para o modelo, que irá gerar uma resposta em texto.
            resposta_final = chat.send_message(genai.protos.Part(function_response=genai.protos.FunctionResponse(
                name=nome_da_funcao, response={'result': resultado_da_ferramenta})))

            # Envia a resposta final em texto para o frontend.
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

# Define a rota principal que carrega a página web (o arquivo index.html).
@app.route('/')
def pagina_inicial():
    return render_template('index.html')

# Inicia o servidor Flask com suporte a Socket.IO.
if __name__ == '__main__':
    porta = int(os.getenv("PORT", 8080))