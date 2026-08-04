import os
import re
import tempfile
import time
import mimetypes
from pathlib import Path
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from config import TRANSCRIPTS_DIR, GEMINI_API_KEY, sanitize_filename

def extract_video_id(url: str) -> str:
    """從 YouTube 網址中解析出 video_id"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""

def get_video_info(url: str) -> dict:
    """使用 yt-dlp 抓取影片元資料 (頻道、標題、上傳日期等)"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'extractor_args': {'youtube': {'player_client': ['android_vr', 'web_embedded']}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        upload_date = info.get('upload_date', '')
        if upload_date and len(upload_date) == 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        else:
            formatted_date = "未知日期"
            
        return {
            'id': info.get('id', ''),
            'title': info.get('title', '無標題'),
            'channel': info.get('uploader', info.get('channel', '未知頻道')),
            'upload_date': formatted_date,
            'duration': info.get('duration_string', ''),
            'url': url
        }

def get_transcript(video_id: str, url: str) -> dict:
    """
    抓取影片字幕逐字稿，並回傳格式化內容與來源標籤：
    {
        'text': 逐字稿文字,
        'source': "📜 YouTube CC 字幕" 或 "🎙️ Gemini AI 音訊轉譯 (無預設 CC 字幕)"
    }
    """
    # 嘗試方法 1: youtube-transcript-api
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list_transcripts(video_id)
        
        transcript = None
        try:
            transcript = transcript_list.find_transcript(['zh-TW', 'zh-Hant', 'zh', 'zh-CN', 'zh-Hans', 'en'])
        except Exception:
            for t in transcript_list:
                transcript = t
                break
                
        if transcript:
            fetched = transcript.fetch()
            text_lines = []
            for item in fetched:
                start_sec = int(item.get('start', 0))
                mins = start_sec // 60
                secs = start_sec % 60
                time_str = f"[{mins:02d}:{secs:02d}]"
                text = item.get('text', '').strip()
                if text:
                    text_lines.append(f"{time_str} {text}")
            return {
                'text': "\n".join(text_lines),
                'source': "📜 YouTube CC 字幕"
            }
    except Exception as e:
        print(f"ℹ️ youtube-transcript-api 未取得字幕: {e}")

    # 嘗試方法 2: Gemini 音訊轉文字
    if GEMINI_API_KEY:
        print("🎙️ 影片無預設字幕，啟動 Gemini AI 音訊轉譯 (Audio Transcription)...")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_tmpl = os.path.join(temp_dir, 'audio.%(ext)s')
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': audio_tmpl,
                    'extractor_args': {'youtube': {'player_client': ['android_vr', 'web_embedded']}},
                    'quiet': True,
                    'no_warnings': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # 尋找下載好的音訊檔案
                actual_audio = None
                for f in os.listdir(temp_dir):
                    if f.startswith("audio."):
                        actual_audio = os.path.join(temp_dir, f)
                        break

                if actual_audio and os.path.exists(actual_audio):
                    # 推斷正確的音訊 MIME Type (預設音訊 audio/webm)
                    ext = Path(actual_audio).suffix.lower()
                    mime_map = {
                        '.webm': 'audio/webm',
                        '.m4a': 'audio/m4a',
                        '.mp3': 'audio/mp3',
                        '.wav': 'audio/wav',
                        '.ogg': 'audio/ogg'
                    }
                    mime_type = mime_map.get(ext, 'audio/webm')

                    client = genai.Client(api_key=GEMINI_API_KEY)
                    uploaded_file = client.files.upload(
                        file=actual_audio,
                        config=types.UploadFileConfig(mime_type=mime_type)
                    )
                    
                    # 等待狀態變更為 ACTIVE
                    for _ in range(30):
                        if uploaded_file.state.name != "PROCESSING":
                            break
                        time.sleep(2)
                        uploaded_file = client.files.get(name=uploaded_file.name)
                        
                    if uploaded_file.state.name != "ACTIVE":
                        raise Exception(f"檔案上傳狀態無效: {uploaded_file.state.name}")
                        
                    response = None
                    for attempt in range(10):
                        try:
                            response = client.models.generate_content(
                                model='gemini-3.5-flash',
                                contents=[
                                    uploaded_file,
                                    "請將這段語音完整轉錄為繁體中文逐字稿，附上大約的時間標記（例如 [01:23]），保持標的代號與專有名詞精準。"
                                ]
                            )
                            if response:
                                break
                        except Exception as e:
                            err_str = str(e)
                            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                                print(f"⏳ 音訊轉譯 [Attempt {attempt+1}/10] 觸發 Gemini API 限流，等待 65 秒...")
                                time.sleep(65)
                            else:
                                raise e

                    
                    try:
                        client.files.delete(name=uploaded_file.name)
                    except Exception:
                        pass

                    if response and response.text:
                        return {
                            'text': response.text,
                            'source': "🎙️ Gemini AI 音訊轉譯 (無預設 CC 字幕)"
                        }

        except Exception as e:
            print(f"⚠️ Gemini 音訊轉譯失敗: {e}")

    return {
        'text': "（警告：未能取得字幕，將嘗試僅由影片資訊進行分析）",
        'source': "⚠️ 未能取得字幕"
    }

def save_transcript(channel: str, date: str, title: str, transcript: str) -> Path:
    """將原始字幕寫入 原始字幕/<頻道名稱>/<日期>_<標題>.txt"""
    clean_channel = sanitize_filename(channel)
    clean_title = sanitize_filename(title)
    
    channel_dir = TRANSCRIPTS_DIR / clean_channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{date}_{clean_title}.txt"
    file_path = channel_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(transcript)
        
    return file_path
