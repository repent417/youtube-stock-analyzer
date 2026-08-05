import os
import re
import tempfile
import time
from pathlib import Path
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from faster_whisper import WhisperModel
from config import TRANSCRIPTS_DIR, sanitize_filename, WHISPER_MODEL_SIZE

_whisper_model_cache = None

def get_whisper_model():
    """全域單例加載 Faster-Whisper 模型"""
    global _whisper_model_cache
    if _whisper_model_cache is None:
        print(f"🎙️ [地端] 正在初始化 Faster-Whisper 模型 ({WHISPER_MODEL_SIZE})...")
        _whisper_model_cache = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=16)
    return _whisper_model_cache

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

def get_transcript(video_id: str, url: str, allow_audio_fallback: bool = True) -> dict:
    """
    抓取影片字幕逐字稿，並回傳格式化內容與來源標籤：
    {
        'text': 逐字稿文字,
        'source': "📜 YouTube CC 字幕" 或 "🎙️ Faster-Whisper 地端轉譯 (無預設 CC 字幕)",
        'has_cc': True / False
    }
    """
    # 嘗試方法 1: youtube-transcript-api 抓取預設 CC 字幕 (最新 API 相容 api.list)
    try:
        api = YouTubeTranscriptApi()
        transcript_list = None
        if hasattr(api, 'list'):
            transcript_list = api.list(video_id)
        elif hasattr(api, 'list_transcripts'):
            transcript_list = api.list_transcripts(video_id)
            
        if transcript_list:
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
                    # 相容物件屬性與字典寫法
                    start_sec = int(getattr(item, 'start', item.get('start', 0) if isinstance(item, dict) else 0))
                    text = getattr(item, 'text', item.get('text', '') if isinstance(item, dict) else '').strip()
                    
                    mins = start_sec // 60
                    secs = start_sec % 60
                    time_str = f"[{mins:02d}:{secs:02d}]"
                    if text:
                        text_lines.append(f"{time_str} {text}")
                        
                if text_lines:
                    return {
                        'text': "\n".join(text_lines),
                        'source': "📜 YouTube CC 字幕",
                        'has_cc': True
                    }
    except Exception as e:
        print(f"ℹ️ youtube-transcript-api 未取得字幕: {e}")

    # 嘗試方法 2: yt-dlp 原生 CC 字幕抓取備援
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-TW', 'zh-Hant', 'zh', 'en'],
            'extractor_args': {'youtube': {'player_client': ['android_vr', 'web_embedded']}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get('subtitles', {}) or info.get('automatic_captions', {})
            if subs:
                for lang in ['zh-TW', 'zh-Hant', 'zh', 'en']:
                    if lang in subs:
                        sub_info = subs[lang]
                        # 找到 vtt 或 json3
                        sub_url = None
                        for fmt in sub_info:
                            if fmt.get('ext') in ['vtt', 'json3', 'srv3']:
                                sub_url = fmt.get('url')
                                break
                        if sub_url:
                            import urllib.request
                            req = urllib.request.urlopen(sub_url)
                            raw_sub = req.read().decode('utf-8', errors='ignore')
                            # 簡單解析 vtt / srv3 清除標籤
                            lines = []
                            for line in raw_sub.splitlines():
                                line = line.strip()
                                if line and not line.startswith('WEBVTT') and not '-->' in line and not line.isdigit():
                                    clean_line = re.sub(r'<[^>]+>', '', line)
                                    if clean_line and clean_line not in lines:
                                        lines.append(clean_line)
                            if lines:
                                return {
                                    'text': "\n".join(lines[:1000]),
                                    'source': "📜 YouTube CC 字幕 (yt-dlp)",
                                    'has_cc': True
                                }
    except Exception as e:
        pass

    # 若不允許音訊轉譯 (預設常規模式)，直接傳回無字幕標記
    if not allow_audio_fallback:
        return {
            'text': "",
            'source': "NO_CC",
            'has_cc': False
        }

    # 嘗試方法 3: Faster-Whisper 本地 CPU 語音轉譯
    print("🎙️ 影片無預設字幕，啟動 Faster-Whisper 本地 CPU 轉譯...")
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
            
            actual_audio = None
            for f in os.listdir(temp_dir):
                if f.startswith("audio."):
                    actual_audio = os.path.join(temp_dir, f)
                    break

            if actual_audio and os.path.exists(actual_audio):
                model = get_whisper_model()
                segments, info = model.transcribe(actual_audio, beam_size=5, language="zh")
                
                text_lines = []
                for seg in segments:
                    start_sec = int(seg.start)
                    mins = start_sec // 60
                    secs = start_sec % 60
                    time_str = f"[{mins:02d}:{secs:02d}]"
                    text = seg.text.strip()
                    if text:
                        text_lines.append(f"{time_str} {text}")

                if text_lines:
                    return {
                        'text': "\n".join(text_lines),
                        'source': "🎙️ Faster-Whisper 地端轉譯 (無預設 CC 字幕)",
                        'has_cc': False
                    }
    except Exception as e:
        print(f"⚠️ Faster-Whisper 地端轉譯失敗: {e}")

    return {
        'text': "（警告：未能取得字幕，將嘗試僅由影片資訊進行分析）",
        'source': "⚠️ 未能取得字幕",
        'has_cc': False
    }

def save_transcript(channel: str, date: str, title: str, transcript: str) -> Path:
    """將原始字幕寫入 原始字幕/<頻道名稱>/<日期>_<標題>.txt"""
    clean_channel = sanitize_filename(channel, max_length=50)
    clean_title = sanitize_filename(title)
    
    channel_dir = TRANSCRIPTS_DIR / clean_channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    raw_filename = f"{date}_{clean_title}.txt"
    filename = sanitize_filename(raw_filename, max_length=70)
    file_path = channel_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(transcript)
        
    return file_path
