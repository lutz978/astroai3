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
    match = re.search(r"\b([A-Z]{2})\b", response.strip())
    return match.group(1) if match else None

def ObterVideosPopulares(country_name, niche):
    country_code = ObterCountryCode(country_name)
    if not country_code:
        return []

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    data_limite = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(timespec="seconds").replace("+00:00", "Z")
    
    busca = youtube.search().list(
        q=niche,
        part="snippet",
        type="video",
        regionCode=country_code,
        maxResults=10,
        order="viewCount"
    )
    resultado = busca.execute()
    
    video_ids = [item["id"]["videoId"] for item in resultado["items"]]
    
    # Agora obtemos as visualizações de cada vídeo
    detalhes_videos = youtube.videos().list(
        part="statistics",
        id=','.join(video_ids)
    ).execute()

    videos = []
    for item in detalhes_videos["items"]:
        video_id = item["id"]
        titulo = item["snippet"]["title"]
        descricao = item["snippet"]["description"]
        views = item["statistics"]["viewCount"]
        link = f"https://www.youtube.com/watch?v={video_id}"
        
        videos.append({
            "titulo": titulo,
            "descricao": descricao,
            "link": link,
            "views": int(views)
        })
    
    return videos

def GerarSugestaoDeConteudo(profile_info, youtube_data, country_name):
    referencias = "\n".join([f"{v['titulo']} ({v['link']})" for v in youtube_data])
    prompt = f"""
    Baseando-se nos seguintes vídeos populares do YouTube:
    {referencias}
    Gere 10 sugestões detalhadas de conteúdo para um criador de conteúdo, com o perfil abaixo.
    Para cada sugestão, inclua o título do vídeo de referência e o link.
    """
    
    prompt += (
        f"Perfil do criador: {profile_info}\n\n"
    )

    response = APIdaOpenAI(prompt)
    return response

def escrever_texto_gradualmente(texto, delay=0.05):
    output_area = st.empty()
    for i in range(1, len(texto) + 1):
        output_area.markdown(f"<p>{texto[:i]}</p>", unsafe_allow_html=True)
        time.sleep(delay)

def main():
    st.title("AstroAI - Seu assistente de criação de conteúdo no YouTube")
    niche = st.text_input("Qual é o seu nicho?")
    audience = st.text_input("Quem é o seu público-alvo?")
    format_preference = st.text_input("Qual formato de vídeo você prefere criar?")
    country_name = st.text_input("Digite o nome do país para buscar vídeos populares:")
    min_views = st.number_input("Número mínimo de visualizações (opcional):", min_value=0, step=1000)
    
    if st.button("Gerar Sugestões"):
        if not niche or not audience or not format_preference or not country_name:
            st.error("Preencha todas as informações antes de continuar.")
        else:
            profile_info = f"Nicho: {niche}, Público-alvo: {audience}, Formato: {format_preference}, País: {country_name}"
            youtube_data = ObterVideosPopulares(country_name, niche)
            videos_filtrados = [v for v in youtube_data if v['views'] >= min_views] if min_views else youtube_data
            sugestoes_de_conteudo = GerarSugestaoDeConteudo(profile_info, videos_filtrados, country_name)
            st.subheader("Sugestões de conteúdo:")
            escrever_texto_gradualmente(sugestoes_de_conteudo, 0.01)

if __name__ == "__main__":
    main()
