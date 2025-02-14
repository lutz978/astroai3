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

def ObterIdiomaDoPais(country_name):
    prompt = f"Qual é o idioma oficial do país {country_name}?"
    response = APIdaOpenAI(prompt)
    match = re.search(r"([A-Za-z]+)", response.strip())
    return match.group(1).lower() if match else "unknown"

def ObterTranscricao(video_id, youtube):
    try:
        captions = youtube.captions().list(part="snippet", videoId=video_id).execute()
        if not captions.get("items"):
            return None
        caption_id = captions["items"][0]["id"]
        caption = youtube.captions().download(id=caption_id).execute()
        return caption.decode("utf-8")
    except:
        return None

def ObterComentarios(video_id, youtube, max_comments=5):
    try:
        comments_response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_comments,
            order="relevance"
        ).execute()
        comentarios = [item["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for item in comments_response.get("items", [])]
        return "\n".join(comentarios)
    except:
        return ""

def ObterVideosPopulares(country_name, niche):
    country_code = ObterCountryCode(country_name)
    if not country_code:
        return []
    
    target_language = ObterIdiomaDoPais(country_name)
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    data_limite = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(timespec="seconds").replace("+00:00", "Z")
    
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
    videos_response = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()
    
    niche_videos = []
    for item in videos_response.get("items", []):
        title = item["snippet"]["title"]
        description = item["snippet"].get("description", "")
        channel_language = item["snippet"].get("defaultLanguage", "")
        
        if channel_language and channel_language.lower() != target_language.lower():
            continue
        
        detected_lang = detect(title + " " + description) if not channel_language else channel_language
        if detected_lang != target_language:
            continue
        
        statistics = item.get("statistics", {})
        transcricao = ObterTranscricao(item["id"], youtube)
        comentarios = ObterComentarios(item["id"], youtube)
        
        niche_videos.append({
            "id": item["id"],
            "title": title,
            "views": int(statistics.get("viewCount", 0)),
            "likes": int(statistics.get("likeCount", 0)),
            "comments": int(statistics.get("commentCount", 0)),
            "transcription": transcricao,
            "user_comments": comentarios
        })
    return niche_videos

def GerarSugestaoDeConteudo(profile_info, youtube_data, country_name):
    prompt = (
        f"Perfil do criador: {profile_info}\n\n"
        f"Aqui estão alguns vídeos populares do YouTube analisados:\n"
    )
    
    for video in youtube_data:
        prompt += (
            f"- Título: {video['title']} (Views: {video['views']}, Likes: {video['likes']}, Comentários: {video['comments']})\n"
            f"  Transcrição (se disponível): {video['transcription'][:500]}...\n"
            f"  Comentários principais: {video['user_comments'][:300]}...\n"
        )
    
    prompt += (
        "\nCom base nesses vídeos, gere 10 sugestões de conteúdo bem detalhadas. Para cada sugestão, mencione o vídeo específico de referência e explique claramente como ele serviu de inspiração."
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
            perfil_criador = f"Nicho: {niche}, Público-alvo: {audience}, Formato: {format_preference}, País: {country_name}"
            youtube_data = ObterVideosPopulares(country_name, niche)
            videos_filtrados = [v for v in youtube_data if v['views'] >= min_views] if min_views else youtube_data
            sugestoes_de_conteudo = GerarSugestaoDeConteudo(perfil_criador, videos_filtrados, country_name)
            st.subheader("Sugestões de conteúdo:")
            escrever_texto_gradualmente(sugestoes_de_conteudo, 0.01)

if __name__ == "__main__":
    main()
