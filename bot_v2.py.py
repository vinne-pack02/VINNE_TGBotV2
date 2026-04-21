import telebot
from openai import OpenAI
from ddgs import DDGS
from PIL import Image
from io import BytesIO
import os
import base64
import time
import random

# ===================== CONFIGURAÇÃO =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
    timeout=60.0 # Timeout maior para processar imagens
)

# Modelos recomendados
MODELO_TEXTO = "llama-3.3-70b-versatile"
MODELO_VISAO = "llama-3.2-11b-vision-preview"

# ===================== FUNÇÕES DE APOIO =====================

def pesquisar_web(termo):
    """Busca no DuckDuckGo com proteção contra bloqueios."""
    try:
        # Pequena pausa aleatória para parecer humano
        time.sleep(random.uniform(1.5, 3.0)) 
        with DDGS() as ddgs:
            print(f"🌐 Pesquisando na web: {termo}")
            resultados = [r['body'] for r in ddgs.text(termo, max_results=3)]
            return "\n\n".join(resultados)
    except Exception as e:
        if "202" in str(e) or "Ratelimit" in str(e):
            print("⏳ Erro: Limite de busca atingido (IP temporariamente bloqueado).")
        else:
            print(f"⚠️ Erro na busca: {e}")
        return ""

def processar_imagem(file_content):
    """Redimensiona para 600px para garantir aceitação do Groq."""
    img = Image.open(BytesIO(file_content))
    img.thumbnail((600, 600))
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=75)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# ===================== COMANDOS INICIAIS =====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Olá! Eu sou o **BOT-VINNE**! 😎\n\n"
        "✨ **Como me usar:**\n"
        "💬 **Conversa:** Mande qualquer texto normalmente.\n"
        "🔍 **Busca Atual:** Comece com **!busca** (ex: `!busca tempo em SP`).\n"
        "🖼️ **Visão:** Me mande uma foto com uma legenda!\n\n"
        "O comando !busca evita que eu seja bloqueado na internet!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# ===================== HANDLER DE FOTOS =====================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        legenda = message.caption if message.caption else "Analise esta imagem."

        file_info = bot.get_file(message.photo[-1].file_id)
        file_content = bot.download_file(file_info.file_path)

        img_b64 = processar_imagem(file_content)

        response = client.chat.completions.create(
            model=MODELO_VISAO,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": legenda},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ],
                }
            ]
        )
        
        bot.reply_to(message, response.choices[0].message.content)

    except Exception as e:
        print(f"Erro Vision: {e}")
        bot.reply_to(message, "❌ Não consegui processar a imagem agora. Verifique o terminal.")

# ===================== HANDLER DE TEXTO =====================

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        texto_usuario = message.text
        contexto_web = ""

        # SÓ PESQUISA SE O USUÁRIO USAR !busca
        if texto_usuario.lower().startswith("!busca"):
            termo = texto_usuario.lower().replace("!busca", "").strip()
            if termo:
                contexto_web = pesquisar_web(termo)
                if not contexto_web:
                    bot.reply_to(message, "⚠️ Minha busca na web está descansando. Vou responder sem internet agora.")
            else:
                bot.reply_to(message, "Diga o que você quer buscar após o comando !busca")
                return

        prompt_sistema = "Você é o BOT-VINNE, um assistente divertido e direto."
        if contexto_web:
            prompt_sistema += f"\n\nContexto extraído da internet agora: {contexto_web}"

        response = client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": texto_usuario}
            ],
            temperature=0.7
        )
        
        bot.reply_to(message, response.choices[0].message.content)

    except Exception as e:
        print(f"Erro Texto: {e}")
        bot.reply_to(message, "❌ Tive um problema ao processar sua mensagem.")

# ===================== START =====================

if __name__ == "__main__":
    print("🚀 BOT-VINNE Online!")
    print("- Use !busca para pesquisar na web.")
    print("- Mande fotos para análise visual.")
    bot.polling(none_stop=True)
