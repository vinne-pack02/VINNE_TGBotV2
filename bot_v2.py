import telebot
from openai import OpenAI
from ddgs import DDGS 
from PIL import Image
from io import BytesIO
import os, base64, time, random, requests, urllib.parse, uuid, threading, json, queue

# ===================== CONFIGURAÇÃO =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client_groq = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

MODELO_TEXTO = "meta-llama/llama-4-scout-17b-16e-instruct"
MODELO_VISAO = "meta-llama/llama-4-scout-17b-16e-instruct"
ARQUIVO_MEMORIA = "memorias_backup.json"

# ESTADO GLOBAL E PROTEÇÕES
fila_geracao = queue.Queue()
usuarios_na_fila = set()
ultimo_comando = {}      
busca_lock = threading.Semaphore(2) 
ultima_busca_global = 0 
tempos_geracao = []

# ===================== PERSISTÊNCIA =====================

def salvar_memorias(mems):
    try:
        with open(ARQUIVO_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(mems, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"⚠️ Erro JSON: {e}")

def carregar_memorias():
    if os.path.exists(ARQUIVO_MEMORIA):
        try:
            with open(ARQUIVO_MEMORIA, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

memorias = carregar_memorias()

# ===================== BUSCA WEB PROTEGIDA =====================

def pesquisar_web_protegido(query):
    global ultima_busca_global
    with busca_lock:
        agora = time.time()
        tempo_desde_ultima = agora - ultima_busca_global
        if tempo_desde_ultima < 7:
            time.sleep(7 - tempo_desde_ultima)
            
        try:
            with DDGS() as ddgs:
                print(f"🌐 [BUSCA] Pesquisando: {query}")
                time.sleep(random.uniform(1.0, 2.0))
                resultados = []
                for r in ddgs.text(query, max_results=3):
                    texto_limpo = " ".join(r['body'].split())
                    resultados.append(f"Fonte: {r['href']}\nInfo: {texto_limpo}")
                ultima_busca_global = time.time()
                return "\n\n".join(resultados) if resultados else "Sem resultados."
        except Exception as e:
            print(f"⚠️ [RATE LIMIT] Busca: {e}")
            if "202" in str(e) or "Ratelimit" in str(e): return "OCUPADO"
            return "Erro ao acessar a web agora."

# ===================== PROCESSADOR DE FILA COM RETRY =====================

def processador_de_fila():
    while True:
        chat_id, prompt, msg_status_id, message_id = fila_geracao.get()
        inicio = time.time()
        tentativas = 0
        sucesso = False
        
        while tentativas < 2 and not sucesso:
            try:
                url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true"
                res = requests.get(url, timeout=60)
                
                if res.status_code == 200:
                    bot.send_photo(chat_id, res.content, reply_to_message_id=message_id)
                    bot.delete_message(chat_id, msg_status_id)
                    sucesso = True
                    print(f"✅ [IMAGEM] Sucesso na tentativa {tentativas+1} em {time.time() - inicio:.1f}s")
                else:
                    tentativas += 1
                    if tentativas < 2:
                        bot.edit_message_text("🔄 API lenta... Tentando novamente (2/2)", chat_id, msg_status_id)
                        time.sleep(3)
            except Exception as e:
                tentativas += 1
                print(f"⚠️ [RETRY {tentativas}] Erro: {e}")
                if tentativas < 2:
                    bot.edit_message_text("🔄 Erro de conexão. Re-tentando...", chat_id, msg_status_id)
                    time.sleep(3)

        if not sucesso:
            bot.edit_message_text("❌ A imagem demorou demais. Tente um prompt mais simples.", chat_id, msg_status_id)
        
        usuarios_na_fila.discard(chat_id)
        fila_geracao.task_done()

threading.Thread(target=processador_de_fila, daemon=True).start()

# ===================== HANDLERS =====================

# 1. COMANDO START
@bot.message_handler(commands=['start'])
def send_welcome(message):
    texto_ajuda = (
        "👋 **Olá! Eu sou o BOT-VINNE.**\n\n"
        "Aqui estão as minhas funções principais:\n\n"
        "💬 **Conversa Inteligente:** Basta me enviar uma mensagem de texto. Eu lembro do contexto da nossa conversa!\n\n"
        "🔍 **Busca na Web:** Use `!busca` seguido do que deseja saber.\n"
        "   _Ex: !busca preço do Bitcoin agora_\n\n"
        "🎨 **Gerador de Imagens:** Use `!criar` seguido da descrição da imagem.\n"
        "   _Ex: !criar um gato astronauta em marte_\n\n"
        "🖼️ **Visão Artificial:** Envie uma foto e eu direi o que estou vendo nela!\n\n"
        "⏱️ **Proteções:** Possuo cooldown de 3s entre mensagens para evitar spam."
    )
    bot.reply_to(message, texto_ajuda, parse_mode="Markdown")

# 2. VISÃO (Deve vir antes do handler de texto genérico)
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = str(message.chat.id)
    try:
        bot.send_chat_action(chat_id, 'typing')
        file_info = bot.get_file(message.photo[-1].file_id)
        file_content = bot.download_file(file_info.file_path)
        
        img = Image.open(BytesIO(file_content))
        img.thumbnail((800, 800))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        resp = client_groq.chat.completions.create(
            model=MODELO_VISAO,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": message.caption or "Descreva esta imagem em detalhes."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]}]
        )
        bot.reply_to(message, resp.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro Visão: {e}")
        bot.reply_to(message, "⚠️ Não consegui analisar a foto agora.")

# 3. TEXTO E COMANDOS GERAIS
@bot.message_handler(func=lambda message: message.text is not None)
def handle_all(message):
    chat_id = str(message.chat.id)
    agora = time.time()

    # Cooldown 3s
    if chat_id in ultimo_comando and (agora - ultimo_comando[chat_id]) < 3:
        return 
    ultimo_comando[chat_id] = agora

    if chat_id not in memorias: memorias[chat_id] = []

    # COMANDO !CRIAR
    if message.text.lower().startswith("!criar"):
        if chat_id in usuarios_na_fila:
            bot.reply_to(message, "⚠️ Aguarde a imagem anterior!")
            return
        prompt = message.text[7:].strip()
        if not prompt: return
        msg_st = bot.reply_to(message, "🎨 Gerando sua imagem...")
        usuarios_na_fila.add(chat_id)
        fila_geracao.put((chat_id, prompt, msg_st.message_id, message.id))
        return

    # LOGICA DE CHAT / BUSCA
    try:
        bot.send_chat_action(chat_id, 'typing')
        contexto_web = ""
        texto_pergunta = message.text

        # Lógica de Contexto por Reply
        if message.reply_to_message and message.reply_to_message.from_user.is_bot:
            contexto_anterior = message.reply_to_message.text
            texto_pergunta = f"Contexto anterior: '{contexto_anterior}' -> Pergunta atual: {message.text}"

        # COMANDO !BUSCA
        if message.text.lower().startswith("!busca"):
            termo = message.text[7:].strip()
            res_busca = pesquisar_web_protegido(termo)
            if res_busca == "OCUPADO":
                bot.reply_to(message, "⌛ Servidor de busca ocupado. Tente em 1 minuto.")
                return
            contexto_web = f"\n\n[DADOS DA WEB]:\n{res_busca}"
        
        instrucao = (
            f"Tu és o BOT-VINNE, assistente técnico do Vinicius. "
            f"Usa o histórico para manter a persistência.{contexto_web}"
        )

        historico = [{"role": "system", "content": instrucao}]
        historico.extend(memorias[chat_id][-15:])
        historico.append({"role": "user", "content": texto_pergunta})

        resp = client_groq.chat.completions.create(model=MODELO_TEXTO, messages=historico)
        resposta = resp.choices[0].message.content
        bot.reply_to(message, resposta)
        
        memorias[chat_id].append({"role": "user", "content": message.text})
        memorias[chat_id].append({"role": "assistant", "content": resposta})
        if len(memorias[chat_id]) > 30: memorias[chat_id] = memorias[chat_id][-30:]
        salvar_memorias(memorias)
    except Exception as e: print(f"❌ Chat: {e}")

# ===================== LOOP =====================

if __name__ == "__main__":
    print(f"🚀 BOT-VINNE ONLINE | Memórias: {len(memorias)}")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60)
        except Exception as e:
            print(f"⚠️ Reconectando... {e}")
            time.sleep(5)
