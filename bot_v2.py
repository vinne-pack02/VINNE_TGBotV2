import telebot
from openai import OpenAI
from ddgs import DDGS 
from PIL import Image
from io import BytesIO
from datetime import datetime
import os, base64, time, requests, urllib.parse, threading, json, queue

# ===================== CONFIGURAÇÃO =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client_groq = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

MODELO_TEXTO = "meta-llama/llama-4-scout-17b-16e-instruct"
MODELO_VISAO = "meta-llama/llama-4-scout-17b-16e-instruct"
ARQUIVO_MEMORIA = "memorias_backup.json"

fila_geracao = queue.Queue()
usuarios_na_fila = set()
ultimo_comando = {}      
busca_lock = threading.Semaphore(2) 
ultima_busca_global = 0 

# ===================== PERSISTÊNCIA =====================

def carregar_memorias():
    if os.path.exists(ARQUIVO_MEMORIA):
        try:
            with open(ARQUIVO_MEMORIA, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def salvar_memorias(mems):
    try:
        with open(ARQUIVO_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(mems, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"❌ [ERRO JSON] {e}")

memorias = carregar_memorias()

# ===================== FUNÇÕES DE APOIO =====================

def obter_preco_crypto(coin_id="bitcoin"):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id.lower()}&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=10).json()
        if coin_id.lower() in res:
            info = res[coin_id.lower()]
            return f"💰 **{coin_id.upper()}**\n💵 Preço: ${info['usd']:,.2f}\n📈 24h: {info.get('usd_24h_change', 0):.2f}%"
        return f"❌ Moeda '{coin_id}' não encontrada."
    except: return "⚠️ Erro na API."

def obter_trending():
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        res = requests.get(url, timeout=10).json()
        lista = [f"{i+1}º {c['item']['name']} ({c['item']['symbol']})" for i, c in enumerate(res['coins'][:10])]
        return "🔥 **Moedas em Tendência:**\n\n" + "\n".join(lista)
    except: return "⚠️ Erro ao buscar tendências."

def pesquisar_web_protegido(query):
    global ultima_busca_global
    with busca_lock:
        agora = time.time()
        if (agora - ultima_busca_global) < 7: time.sleep(7 - (agora - ultima_busca_global))
        try:
            with DDGS() as ddgs:
                res = [f"Fonte: {r['href']}\nConteúdo: {r['body']}" for r in ddgs.text(query, max_results=3)]
                ultima_busca_global = time.time()
                print(f"✅ [!BUSCA] Sucesso: {query[:20]}")
                return "\n\n".join(res) if res else "Sem resultados."
        except Exception as e: 
            print(f"❌ [!BUSCA] Falha: {e}")
            return "OCUPADO"

# ===================== PROCESSADOR DE IMAGENS =====================

def processador_de_fila():
    while True:
        chat_id, prompt, msg_status_id, message_id = fila_geracao.get()
        tentativas = 0
        sucesso = False
        while tentativas < 2 and not sucesso:
            try:
                url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true"
                res = requests.get(url, timeout=90)
                if res.status_code == 200:
                    bot.send_photo(chat_id, res.content, reply_to_message_id=message_id)
                    bot.delete_message(chat_id, msg_status_id)
                    sucesso = True
                    print(f"✅ [!CRIAR] Sucesso T{tentativas+1}")
                else: raise Exception()
            except:
                tentativas += 1
                if tentativas == 1:
                    print(f"🔄 [!CRIAR] Falha T1. Tentando T2...")
                    bot.edit_message_text("🔄 API instável. Tentando novamente...", chat_id, msg_status_id)
                    time.sleep(5)
                else:
                    print(f"❌ [!CRIAR] Falha definitiva.")
                    bot.edit_message_text("❌ Falha ao gerar imagem.", chat_id, msg_status_id)
        usuarios_na_fila.discard(chat_id)
        fila_geracao.task_done()

threading.Thread(target=processador_de_fila, daemon=True).start()

# ===================== HANDLERS =====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = str(message.chat.id)
    mems = len(memorias.get(chat_id, []))
    texto = (
        "🚀 **BOT-VINNE PRO ONLINE**\n\n"
        f"🧠 **Memória:** {mems} interações salvas.\n\n"
        "**Comandos (Use / ou !):**\n"
        "• `!preco [moeda]` - Valor real da cripto.\n"
        "• `!trending` - Moedas em tendência.\n"
        "• `!busca [termo]` - Pesquisa web em tempo real.\n"
        "• `!criar [prompt]` - Gerar imagem IA.\n\n"
        "📸 **Dica:** Envie uma foto ou responda a uma mensagem para contexto!"
    )
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        img = Image.open(BytesIO(bot.download_file(file_info.file_path)))
        img.thumbnail((800, 800))
        buf = BytesIO(); img.save(buf, format="JPEG", quality=80)
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        caption = message.caption or "Analise esta imagem."
        resp = client_groq.chat.completions.create(
            model=MODELO_VISAO,
            messages=[{"role": "user", "content": [{"type": "text", "text": caption}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}]
        )
        bot.reply_to(message, resp.choices[0].message.content)
        print(f"✅ [VISÃO] Sucesso: {message.from_user.first_name}")
    except Exception as e:
        print(f"❌ [VISÃO] Falha: {e}")

@bot.message_handler(func=lambda message: message.text is not None)
def handle_all(message):
    chat_id = str(message.chat.id)
    agora = time.time()
    msg_text = message.text.lower()
    data_hoje = datetime.now().strftime("%d/%m/%Y")

    if chat_id in ultimo_comando and (agora - ultimo_comando[chat_id]) < 1.5: return 
    ultimo_comando[chat_id] = agora
    if chat_id not in memorias: memorias[chat_id] = []

    # --- COMANDOS UNIFICADOS (! E /) ---
    
    if msg_text.startswith("!preco") or msg_text.startswith("/preco"):
        arg = message.text.replace("!preco", "").replace("/preco", "").strip()
        bot.reply_to(message, obter_preco_crypto(arg or "bitcoin"), parse_mode="Markdown")
        return
    
    if msg_text.startswith("!trending") or msg_text.startswith("/trending"):
        bot.reply_to(message, obter_trending(), parse_mode="Markdown")
        return

    if msg_text.startswith("!criar") or msg_text.startswith("/criar"):
        if chat_id in usuarios_na_fila: return
        prompt = message.text.replace("!criar", "").replace("/criar", "").strip()
        msg_st = bot.reply_to(message, "🎨 **Processando imagem...** (Aprox. 1 min)")
        usuarios_na_fila.add(chat_id)
        fila_geracao.put((chat_id, prompt, msg_st.message_id, message.id))
        return

    # --- CHAT COM MEMÓRIA E REPLY ---
    try:
        contexto_web = ""
        if msg_text.startswith("!busca") or msg_text.startswith("/busca"):
            query = message.text.replace("!busca", "").replace("/busca", "").strip()
            res = pesquisar_web_protegido(query)
            if res == "OCUPADO": 
                bot.reply_to(message, "⌛ Aguarde o cooldown de busca.")
                return
            contexto_web = f"\n\n[DADOS WEB]:\n{res}"
        
        texto_final = message.text
        if message.reply_to_message:
            original = message.reply_to_message.text or "[Mídia]"
            texto_final = f"(Em resposta a: '{original}') -> {message.text}"

        instrucao = f"Tu és o BOT-VINNE. DATA ATUAL: {data_hoje}. {contexto_web}"
        historico = [{"role": "system", "content": instrucao}]
        historico.extend(memorias[chat_id][-10:])
        historico.append({"role": "user", "content": texto_final})

        resp = client_groq.chat.completions.create(model=MODELO_TEXTO, messages=historico)
        resposta = resp.choices[0].message.content
        bot.reply_to(message, resposta)

        memorias[chat_id].append({"role": "user", "content": message.text})
        memorias[chat_id].append({"role": "assistant", "content": resposta})
        if len(memorias[chat_id]) > 20: memorias[chat_id] = memorias[chat_id][-20:]
        salvar_memorias(memorias)
    except Exception as e: print(f"❌ [CHAT] Erro: {e}")

if __name__ == "__main__":
    print(f"🚀 SISTEMA ONLINE | {datetime.now().strftime('%H:%M:%S')}")
    bot.infinity_polling(skip_pending=True)
