from openai import OpenAI
from googleapiclient.discovery import build
from langdetect import detect
from datetime import datetime, timedelta, timezone
import re
import streamlit as st
import time

API_KEY = st.secrets["API_KEY"]
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]

client = OpenAI(api_key=API_KEY)
def APIdaOpenAI(prompt):
    completion = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=[{"role": "user", "content": prompt}])
    return completion.choices[0].message.content

def ObterCountryCode(country_name):
    prompt = f"Qual é o código ISO 3166-1 alfa-2 para o país {country_name}?"
    response = APIdaOpenAI(prompt)
    match = re.search(r"\b([A-Z]{2})\b", response.strip())  # Procura por 2 letras maiúsculas (código do país)
    if match:
        return match.group(1)
    else:
        return None  # Se não encontrar um código válido

def ObterIdiomaDoPais(country_name):
    """Usa a API da OpenAI para obter o idioma oficial de um país a partir do seu nome."""
    prompt = f"Qual é o idioma oficial do país {country_name}?"
    response = APIdaOpenAI(prompt)

    # A API retorna uma resposta com o idioma, vamos tentar extrair o nome do idioma
    match = re.search(r"([A-Za-z]+)", response.strip())
    if match:
        return match.group(1).lower()  # Retorna o idioma em minúsculas
    else:
        return "unknown"

#Função que analisa os vídeos mais populares com base no país pedido
def ObterVideosPopulares(country_name, niche):
    """Busca vídeos populares do YouTube e filtra pelo idioma do canal ou título/descrição, com base no país escolhido."""

    # Obtém o código do país
    country_code = ObterCountryCode(country_name)
    if not country_code:
        print("País não encontrado ou não suportado.")
        return []

    # Obtém o idioma do país (agora dinamicamente via OpenAI)
    target_language = ObterIdiomaDoPais(country_name)

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    data_limite = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(timespec="seconds").replace("+00:00", "Z")

    # Buscar vídeos pelo país e nicho
    search_response = youtube.search().list(
        part="snippet",
        q=niche,
        regionCode=country_code,
        type="video",
        maxResults=10,
        order="date",
        publishedAfter=data_limite
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

    # Buscar vídeos em alta no país
    trending_response = youtube.videos().list(
        part="snippet,statistics",
        chart="mostPopular",
        regionCode=country_code,
        maxResults=10  # Ajuste conforme necessário
    ).execute()

    trending_videos = []
    for item in trending_response.get("items", []):
        trending_videos.append({
            "id": item["id"],
            "title": item["snippet"]["title"],
            "views": int(item["statistics"].get("viewCount", 0)),
            "likes": int(item["statistics"].get("likeCount", 0)),
            "comments": int(item["statistics"].get("commentCount", 0))
        })

    # Obter estatísticas e informações dos vídeos filtrados pelo nicho
    videos_response = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    ).execute()

    niche_videos = []
    for item in videos_response.get("items", []):
        title = item["snippet"]["title"]
        description = item["snippet"].get("description", "")
        channel_language = item["snippet"].get("defaultLanguage", "")

        if channel_language and channel_language.lower() != target_language.lower():
            continue  # Ignora vídeos em idiomas diferentes

        detected_lang = detect(title + " " + description) if not channel_language else channel_language
        if detected_lang != target_language:
            continue  # Ignora vídeos em idiomas diferentes

        statistics = item.get("statistics", {})
        niche_videos.append({
            "id": item["id"],
            "title": title,
            "views": int(statistics.get("viewCount", 0)),
            "likes": int(statistics.get("likeCount", 0)),
            "comments": int(statistics.get("commentCount", 0))
        })

    
    return niche_videos

#Função que gera as sugestões de conteúdo
def GerarSugestaoDeConteudo(profile_info, youtube_data, country_name):
    """Gera sugestões de conteúdo com base no perfil do criador e nos vídeos filtrados do país específico."""
    prompt = (
        f"Você é um assistente criativo e interativo especializado em sugerir ideias de conteúdo para criadores de vídeos no YouTube.\n\n"
        f"Perfil do criador: {profile_info}\n\n"
        f"Estamos trabalhando com vídeos populares filtrados por país: {country_name}. Aqui estão alguns vídeos populares do YouTube relacionados ao nicho do criador e ao país escolhido:\n"
    )

    # Incluir apenas os vídeos filtrados pelo país
    for video in youtube_data:
        prompt += (
            f"- Título: {video['title']}, Visualizações: {video['views']}, "
            f"Likes: {video['likes']}, Comentários: {video['comments']}\n"
        )

    prompt += (
    "\nCom base nesses vídeos e no perfil do criador, sugira 10 ideias criativas de vídeos que sejam relevantes para o público do criador. "
    "Cada sugestão deve estar diretamente relacionada a um ou mais dos vídeos listados acima, explicando como essa inspiração foi derivada."
    )
    
    prompt += (
        "\nExplique o motivo das ideias sugeridas, por exemplo: 'Esta ideia pode ser engajante porque no país escolhido ("
        f"{country_name}) essa ideia desperta a curiosidade devido aos vídeos populares que analisamos'."
    )

    prompt += (
    "\nEm seguida, escolha 3 dessas 10 ideias que você considera as melhores, justifique sua escolha e forneça detalhes sobre "
    f"estatísticas dos vídeos ({youtube_data}) e títulos disponíveis ({', '.join(video['title'] for video in youtube_data)}) "
    f"no idioma original do país {country_name} para apoiar a sugestão.")

    response = APIdaOpenAI(prompt)
    return response

def escrever_texto_gradualmente(texto, delay=0.05):
    output_area = st.empty()  
    for i in range(1, len(texto) + 1):
        output_area.markdown(f"<p>{texto[:i]}</p>", unsafe_allow_html=True)
        time.sleep(delay)  # Aguarda um pequeno intervalo entre cada caractere

def main():
    st.title("AstroAI - Seu assistente de criação de conteúdo no Youtube")
    st.subheader("Receba sugestões de conteúdo personalizadas!")
    st.write("Responda às perguntas abaixo.")

    # Solicitar dados do usuário com animação
    niche = st.text_input("Qual é o seu nicho? (ex.: Educação Física, Culinária, Tecnologia)")
    audience = st.text_input("Quem é o seu público-alvo? (ex.: jovens adultos, mães, profissionais da área)")
    format_preference = st.text_input("Qual formato de vídeo você prefere criar? (ex.: vídeos curtos, lives, tutoriais)")
    country_name = st.text_input("Digite o nome do país para buscar vídeos populares:")
    min_views = st.number_input("Número mínimo de visualizações (opcional):", min_value=0, step=1000)

    if st.button("Gerar Sugestões"):
        if not niche or not audience or not format_preference or not country_name:
            st.error("Preencha todas as informações antes de continuar.")
        else:
            perfil_criador = f"Nicho: {niche}, Público-alvo: {audience}, Formato: {format_preference}, País: {country_name}"
            youtube_data = ObterVideosPopulares(country_name, niche)
            videos_filtrados = [v for v in youtube_data if v['views'] >= min_views] if min_views else youtube_data
            sugestoes_de_conteudo = GerarSugestaoDeConteudo(perfil_criador, videos_filtrados, country_name)
            st.subheader("Sugestões de conteúdo:")
            escrever_texto_gradualmente(sugestoes_de_conteudo, 0.01)

if __name__ == "__main__":
    main()
