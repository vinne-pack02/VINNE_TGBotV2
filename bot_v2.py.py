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
    timeout=60.0 
)

MODELO_TEXTO = "meta-llama/llama-4-scout-17b-16e-instruct"
MODELO_VISAO = "meta-llama/llama-4-scout-17b-16e-instruct"

# DICIONÁRIO PARA MEMÓRIA (Últimas 10 mensagens por chat)
memorias = {}

# ===================== FUNÇÕES DE APOIO =====================

def gerenciar_memoria(chat_id, nova_mensagem):
    """Mantém apenas as últimas 10 mensagens na memória do chat."""
    if chat_id not in memorias:
        memorias[chat_id] = []
    
    memorias[chat_id].append(nova_mensagem)
    
    # Se passar de 10, remove a mais antiga (mantendo o System Prompt fora da conta se preferir)
    if len(memorias[chat_id]) > 10:
        memorias[chat_id].pop(0)
    
    return memorias[chat_id]

def pesquisar_web(termo):
    try:
        time.sleep(random.uniform(1.5, 3.0)) 
        with DDGS() as ddgs:
            print(f"🌐 Pesquisando na web: {termo}")
            resultados = [r['body'] for r in ddgs.text(termo, max_results=3)]
            return "\n\n".join(resultados)
    except Exception as e:
        print(f"⚠️ Erro na busca: {e}")
        return ""

def processar_imagem(file_content):
    img = Image.open(BytesIO(file_content))
    img.thumbnail((600, 600))
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=75)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# ===================== COMANDOS INICIAIS =====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Olá! Eu sou o **BOT-VINNE** com Memória! 😎\n\n"
        "✨ **Novidades:**\n"
        "🧠 **Memória:** Eu lembro das nossas últimas 10 interações!\n"
        "💬 **Replies:** Pode responder a uma mensagem minha que eu entenderei o contexto.\n"
        "🔍 **Busca:** !busca <termo>\n"
        "🖼️ **Visão:** Mande foto com legenda."
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

        # Na visão, geralmente mandamos o prompt direto, mas salvamos a resposta na memória de texto
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
        
        resposta_texto = response.choices[0].message.content
        bot.reply_to(message, resposta_texto)
        
        # Salva a interação visual na memória como texto para o bot "lembrar" do que viu
        gerenciar_memoria(message.chat.id, {"role": "user", "content": f"[Usuário mandou foto] {legenda}"})
        gerenciar_memoria(message.chat.id, {"role": "assistant", "content": resposta_texto})

    except Exception as e:
        print(f"Erro Vision: {e}")
        bot.reply_to(message, "❌ Erro ao processar imagem.")

# ===================== HANDLER DE TEXTO =====================

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        chat_id = message.chat.id
        texto_usuario = message.text
        
        # 1. Tratar REPLY (Contexto adicional se for resposta)
        if message.reply_to_message:
            texto_usuario = f"(Respondendo à mensagem: '{message.reply_to_message.text}'): {texto_usuario}"

        # 2. Busca na Web
        contexto_web = ""
        if texto_usuario.lower().startswith("!busca"):
            termo = texto_usuario.lower().replace("!busca", "").strip()
            if termo:
                contexto_web = pesquisar_web(termo)
                if not contexto_web:
                    bot.reply_to(message, "⚠️ Sem internet no momento. Respondendo com o que sei.")
            else:
                bot.reply_to(message, "O que você quer buscar?")
                return

        # 3. Preparar Mensagens para a IA
        prompt_sistema = "Você é o BOT-VINNE, um assistente divertido e direto. Você tem memória das últimas mensagens."
        if contexto_web:
            prompt_sistema += f"\n\nContexto extraído da internet agora: {contexto_web}"

        # Criar a lista de mensagens para o Groq
        mensagens_ia = [{"role": "system", "content": prompt_sistema}]
        
        # Adiciona o histórico da memória (as últimas 10)
        historico = memorias.get(chat_id, [])
        mensagens_ia.extend(historico)
        
        # Adiciona a mensagem atual
        mensagens_ia.append({"role": "user", "content": texto_usuario})

        response = client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=mensagens_ia,
            temperature=0.7
        )
        
        resposta_final = response.choices[0].message.content
        bot.reply_to(message, resposta_final)

        # 4. Atualizar a Memória
        gerenciar_memoria(chat_id, {"role": "user", "content": texto_usuario})
        gerenciar_memoria(chat_id, {"role": "assistant", "content": resposta_final})

    except Exception as e:
        print(f"Erro Texto: {e}")
        bot.reply_to(message, "❌ Tive um problema ao processar sua mensagem.")

# ===================== START =====================

if __name__ == "__main__":
    print("🚀 BOT-VINNE Online com Memória e Contexto de Reply!")
    bot.polling(none_stop=True)
