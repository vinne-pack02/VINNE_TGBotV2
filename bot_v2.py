import telebot
from openai import OpenAI
from ddgs import DDGS 
from PIL import Image
from io import BytesIO
import os
import base64
import time
import random
import requests
import urllib.parse
import pandas as pd

# ===================== CONFIGURAÇÃO (PRODUÇÃO) =====================
# Lemos APENAS das variáveis de ambiente. Não colocamos chaves aqui!
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Variáveis de ambiente TELEGRAM_TOKEN ou GROQ_API_KEY não configuradas.")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

client_groq = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
    timeout=60.0 
)

MODELO_TEXTO = "meta-llama/llama-4-scout-17b-16e-instruct"
MODELO_VISAO = "meta-llama/llama-4-scout-17b-16e-instruct"

# DICIONÁRIO DE MEMÓRIA
memorias = {}

# ===================== FUNÇÕES DE APOIO =====================

def gerenciar_memoria(chat_id, nova_mensagem):
    if chat_id not in memorias:
        memorias[chat_id] = []
    memorias[chat_id].append(nova_mensagem)
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

def processar_imagem_entrada(file_content):
    img = Image.open(BytesIO(file_content))
    img.thumbnail((600, 600))
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=75)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def gerar_imagem_gratis(prompt, chat_id):
    """Gera, valida e reconstrói a imagem para evitar erros."""
    try:
        prompt_codificado = urllib.parse.quote(prompt)
        seed = random.randint(0, 999999)
        url = f"https://image.pollinations.ai/prompt/{prompt_codificado}?width=1024&height=1024&seed={seed}&nologo=true"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        print(f"🎨 Gerando imagem: {url}")
        
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                return "ERRO_CONTEUDO"

            # Caminho simples, no Railway isso é um diretório temporário
            caminho_bruto = f"raw_{chat_id}.jpg"
            caminho_final = f"final_{chat_id}.jpg"
            
            with open(caminho_bruto, "wb") as f:
                f.write(response.content)
            
            # Reconstrução Pillow (Limpeza)
            try:
                with Image.open(caminho_bruto) as img:
                    img = img.convert("RGB")
                    img.save(caminho_final, "JPEG", quality=90)
                
                if os.path.exists(caminho_bruto): os.remove(caminho_bruto)
                return caminho_final
            except Exception as e:
                print(f"⚠️ Arquivo corrompido: {e}")
                if os.path.exists(caminho_bruto): os.remove(caminho_bruto)
                return None
        return None
    except Exception as e:
        print(f"⚠️ Erro técnico: {e}")
        return None

# ===================== COMANDOS =====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Olá! Eu sou o **BOT-VINNE** Oficial! 😎\n\n"
        "💬 **Texto:** Mande qualquer mensagem normalmente.\n"
        "🎨 **!criar [texto]** - Eu gero uma imagem para você!\n"
        "🔍 **!busca [texto]** - Pesquiso na internet.\n"
        "🖼️ **Mande foto** - Eu analiso e descrevo imagens.\n"
        "🧠 **Memória** - Lembro das últimas 10 conversas!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# ===================== HANDLER DE TEXTO =====================

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        chat_id = message.chat.id
        texto_usuario = message.text

        # 1. COMANDO !CRIAR
        if texto_usuario.lower().startswith("!criar"):
            prompt_img = texto_usuario.lower().replace("!criar", "").strip()
            if not prompt_img:
                bot.reply_to(message, "⚠️ Diga o que você quer criar! Ex: `!criar um dragão punk`")
                return

            bot.send_chat_action(chat_id, 'upload_photo')
            msg_status = bot.reply_to(message, "🎨 Desenhando sua ideia... Aguarde um instante.")
            
            caminho_imagem = gerar_imagem_gratis(prompt_img, chat_id)
            
            # Pequeno delay para o sistema de arquivos (necessário até no Railway)
            time.sleep(1.0) 
            
            if caminho_imagem == "ERRO_CONTEUDO":
                bot.edit_message_text("❌ A API está recusando o pedido no momento. Tente novamente em 1 minuto!", chat_id, msg_status.message_id)
                return

            if caminho_imagem and os.path.exists(caminho_imagem):
                try:
                    with open(caminho_imagem, "rb") as foto:
                        bot.send_photo(chat_id, foto, caption=f"✨ Aqui está: {prompt_img}", reply_to_message_id=message.message_id)
                    bot.delete_message(chat_id, msg_status.message_id)
                finally:
                    try: os.remove(caminho_imagem)
                    except: pass
            else:
                bot.edit_message_text("❌ Tive um problema ao gerar sua imagem. Tente outro tema!", chat_id, msg_status.message_id)
            return

        # 2. COMANDO !BUSCA
        contexto_web = ""
        if texto_usuario.lower().startswith("!busca"):
            termo = texto_usuario.lower().replace("!busca", "").strip()
            contexto_web = pesquisar_web(termo)

        # 3. LÓGICA DE IA (GROQ)
        bot.send_chat_action(chat_id, 'typing')
        prompt_sistema = "Você é o BOT-VINNE Oficial, divertido, inteligente e direto."
        if contexto_web:
            prompt_sistema += f"\n\nContexto da Web: {contexto_web}"

        mensagens_ia = [{"role": "system", "content": prompt_sistema}]
        mensagens_ia.extend(memorias.get(chat_id, []))
        
        corpo_msg = texto_usuario
        if message.reply_to_message:
            corpo_msg = f"(Respondendo a reply: '{message.reply_to_message.text}') -> {texto_usuario}"
            
        mensagens_ia.append({"role": "user", "content": corpo_msg})

        response = client_groq.chat.completions.create(model=MODELO_TEXTO, messages=mensagens_ia, temperature=0.8)
        resposta = response.choices[0].message.content
        bot.reply_to(message, resposta)

        # Atualiza Memória e LOG no terminal (ainda útil para ver no Railway)
        gerenciar_memoria(chat_id, {"role": "user", "content": texto_usuario})
        gerenciar_memoria(chat_id, {"role": "assistant", "content": resposta})
        
        df_log = pd.DataFrame(memorias[chat_id])
        print("\n📊 MEMÓRIA DO CHAT ATUALIZADA:\n", df_log.to_string(index=False, max_colwidth=30))

    except Exception as e:
        print(f"❌ Erro no Handler: {e}")

# ===================== HANDLER DE FOTOS =====================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        legenda = message.caption if message.caption else "O que é isso?"
        file_info = bot.get_file(message.photo[-1].file_id)
        file_content = bot.download_file(file_info.file_path)
        img_b64 = processar_imagem_entrada(file_content)

        response = client_groq.chat.completions.create(
            model=MODELO_VISAO,
            messages=[{"role": "user", "content": [{"type": "text", "text": legenda}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}]
        )
        bot.reply_to(message, response.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro Visão: {e}")

if __name__ == "__main__":
    print("🚀 BOT-VINNE OFICIAL ONLINE (Rodando no Railway)!")
    # none_stop=True garante que o bot tente reconectar se cair
    bot.polling(none_stop=True, interval=0, timeout=20)
