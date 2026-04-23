# VINNE_TGBot

O **BOT-VINNE** é um assistente multifuncional de alto desempenho para Telegram. Ele integra inteligência artificial generativa, visão computacional, pesquisa web em tempo real e geração de imagens em uma única interface conversacional fluida. 

Hospedado na nuvem, o bot foi projetado para oferecer respostas instantâneas e ferramentas criativas 24 horas por dia.

---

## 🚀 Funcionalidades Principais

### 🧠 Inteligência Conversacional
* **IA de Resposta Rápida:** Processamento de mensagens via modelos de última geração para respostas naturais e precisas.
* **Memória de Curto Prazo:** O bot mantém o contexto das últimas 10 interações, permitindo diálogos contínuos e coerentes.
* **Suporte a Contexto:** Entende respostas diretas (*replies*) para responder perguntas sobre mensagens específicas.

### 🖼️ Visão Computacional
* **Análise de Imagens:** Envie qualquer foto e o bot descreverá o conteúdo, identificará objetos, lerá textos ou interpretará o que está acontecendo na cena.

### 🎨 Geração de Arte (Text-to-Image)
* **Comando `!criar`:** Transforma descrições textuais em imagens digitais originais.
* **Reconstrução de Arquivos:** Processamento interno via Pillow para garantir que as imagens geradas sejam compatíveis com todos os clientes do Telegram, evitando erros de carregamento.

### 🔍 Pesquisa Web em Tempo Real
* **Comando `!busca`:** O bot acessa a internet para coletar informações atualizadas, notícias e dados recentes, integrando-os diretamente na resposta da IA.

---

## 🛠️ Tecnologias e Arquitetura

O projeto utiliza uma arquitetura moderna baseada em micro-APIs e bibliotecas de alto desempenho:

| Camada | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Núcleo** | **Python 3.8+** | Linguagem base focada em escalabilidade e rapidez. |
| **Interface** | **pyTelegramBotAPI** | Framework para integração estável com a API do Telegram. |
| **IA de Texto/Visão** | **Groq (Llama 4)** | Engine de inferência ultra-rápida para processamento de linguagem e visão. |
| **Geração de Imagem** | **Flux (Pollinations)** | Modelo de difusão para criação de imagens de alta fidelidade. |
| **Processamento Visual** | **Pillow (PIL)** | Biblioteca para otimização e reconstrução técnica de arquivos JPG/PNG. |
| **Motor de Busca** | **DuckDuckGo Search** | Busca web anonimizada e eficiente para dados em tempo real. |
| **Análise de Dados** | **Pandas** | Organização e estruturação dos logs de memória e sistema. |
| **Hospedagem** | **Railway (Linux)** | Infraestrutura PaaS para execução 24/7 em ambiente Dockerizado. |

---

## 📖 Como Usar

Para interagir com o bot, basta enviar uma mensagem no chat ou utilizar os comandos específicos:

1. **Conversa Comum:** Basta digitar qualquer texto para iniciar um diálogo.
2. **`!criar [descrição]`:** Gera uma imagem baseada no seu texto. 
   * *Exemplo:* `!criar uma abelha roxa em estilo cyberpunk`
3. **`!busca [termo]`:** Realiza uma pesquisa na internet antes de responder.
   * *Exemplo:* `!busca preço do Bitcoin hoje`
4. **Análise de Fotos:** Envie uma imagem com ou sem legenda para que o bot a analise.

---

## ⚙️ Instalação (Desenvolvedores)

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
Hospedagem	Railway (Linux)	Infraestrutura PaaS para execução 24/7 em ambiente Dockerizado.

## 🔑 Configuração das Chaves (API Keys)

Para que o bot funcione corretamente, você precisará obter suas próprias credenciais nos serviços abaixo:

1. **Telegram Token:**
   * Inicie uma conversa com o [@BotFather](https://t.me/botfather) no Telegram.
   * Use o comando `/newbot` e siga as instruções para obter o seu `API Token`.

2. **Groq API Key (IA de Texto/Visão):**
   * Crie uma conta gratuita no [Groq Cloud Console](https://console.groq.com/).
   * Acesse a seção **API Keys** e gere uma nova chave.

---

## 🌍 Variáveis de Ambiente

O projeto utiliza variáveis de ambiente para manter suas chaves seguras. Você deve configurar as seguintes variáveis no seu sistema ou no painel do **Railway**:

| Variável | Descrição |
| :--- | :--- |
| `TELEGRAM_TOKEN` | O token do seu bot gerado pelo BotFather. |
| `GROQ_API_KEY` | Sua chave de API da Groq Cloud. |

### Como configurar localmente:
Se estiver rodando no seu computador (Windows/Linux), crie um arquivo chamado `.env` na raiz do projeto e adicione:
```env
TELEGRAM_TOKEN=seu_token_aqui
GROQ_API_KEY=sua_chave_aqui
