import os
import sys
import re
import socket
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import markdown

BASE_DIR = Path(__file__).resolve().parent.parent
NOTES_DIR = BASE_DIR / "影片筆記"
INDEX_DIR = BASE_DIR / "個股索引"
WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="YouTube 股票分析網頁研報閱讀器", version="2.0.0")

# 掛載靜態檔案與 Templating
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")

# 全域快取索引 (加快搜尋與載入)
class DataVault:
    def __init__(self):
        self.channels: Dict[str, List[Dict[str, Any]]] = {}
        self.stock_indexes: List[Dict[str, Any]] = []
        self.stem_to_path: Dict[str, Path] = {}
        self.notes_flat: List[Dict[str, Any]] = []
        self.refresh_cache()

    def refresh_cache(self):
        """掃描全庫 Markdown 建立快取"""
        self.channels = {}
        self.stock_indexes = []
        self.stem_to_path = {}
        self.notes_flat = []

        # 1. 掃描 影片筆記/
        if NOTES_DIR.exists():
            for p in NOTES_DIR.rglob("*.md"):
                channel_name = p.parent.name
                rel_path = str(p.relative_to(BASE_DIR)).replace("\\", "/")
                stem = p.stem
                self.stem_to_path[stem] = p
                
                # 提取日期 (檔名開頭 2026-XX-XX)
                date_m = re.match(r"^(\d{4}-\d{2}-\d{2})", stem)
                date_str = date_m.group(1) if date_m else ""
                
                item = {
                    "title": stem,
                    "stem": stem,
                    "date": date_str,
                    "path": rel_path,
                    "channel": channel_name
                }
                
                if channel_name not in self.channels:
                    self.channels[channel_name] = []
                self.channels[channel_name].append(item)
                self.notes_flat.append(item)

            # 按日期排序
            for ch in self.channels:
                self.channels[ch].sort(key=lambda x: x["date"], reverse=True)

        # 2. 掃描 個股索引/
        if INDEX_DIR.exists():
            for p in INDEX_DIR.glob("*.md"):
                stem = p.stem
                rel_path = str(p.relative_to(BASE_DIR)).replace("\\", "/")
                self.stem_to_path[stem] = p
                
                # 拆分代號與名稱 (如 2330_台積電 或 TSM_台積電ADR)
                code = stem.split("_")[0] if "_" in stem else stem
                name = stem.split("_")[1] if "_" in stem else stem
                
                self.stock_indexes.append({
                    "code": code,
                    "name": name,
                    "stem": stem,
                    "full_name": f"{code} {name}",
                    "path": rel_path
                })

            self.stock_indexes.sort(key=lambda x: x["code"])

vault = DataVault()

def get_lan_ips() -> List[str]:
    """獲取本機在內網 (LAN) 的所有 IP 地址"""
    ips = []
    try:
        hostname = socket.gethostname()
        addrs = socket.gethostbyname_ex(hostname)[2]
        ips = [ip for ip in addrs if not ip.startswith("127.")]
    except Exception:
        pass
    return ips if ips else ["127.0.0.1"]

def convert_wikilinks_to_html(md_text: str) -> str:
    """將 Obsidian 雙括號連結 [[NoteStem|DisplayTitle]] 轉換為自訂的超連結"""
    def replace_link(match):
        full_inner = match.group(1)
        if "|" in full_inner:
            target_stem, display = full_inner.split("|", 1)
        else:
            target_stem, display = full_inner, full_inner
            
        target_stem = target_stem.strip()
        display = display.strip()
        
        # 清理錨點 # (如果有)
        clean_target = target_stem.split("#")[0]
        
        return f'<a href="javascript:void(0)" onclick="loadWikiLink(\'{clean_target}\')" class="wikilink-btn" title="查看：{display}">{display}</a>'

    return re.sub(r"\[\[(.*?)\]\]", replace_link, md_text)

# --- API 路由定義 ---

CURRENT_PORT = 23300

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """主頁面"""
    lan_ips = get_lan_ips()
    primary_ip = lan_ips[0] if lan_ips else "localhost"
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "lan_ips": lan_ips,
            "primary_ip": primary_ip,
            "port": CURRENT_PORT
        }
    )


@app.get("/api/lan_info")
async def get_lan_info():
    """提供內網 IP 資訊"""
    ips = get_lan_ips()
    return {
        "ips": ips,
        "port": CURRENT_PORT,
        "urls": [f"http://{ip}:{CURRENT_PORT}" for ip in ips]
    }

@app.get("/api/channels")
async def get_channels():
    """獲取所有頻道與其筆記選單"""
    return {
        "channels": vault.channels,
        "total_notes": len(vault.notes_flat)
    }

@app.get("/api/stocks")
async def get_stocks():
    """獲取所有個股索引選單"""
    return {
        "stocks": vault.stock_indexes,
        "total_stocks": len(vault.stock_indexes)
    }

@app.get("/api/search")
async def search_notes(q: str = Query("", min_length=1)):
    """全文與標題關鍵字模糊搜尋"""
    query = q.strip().lower()
    results = []
    
    # 1. 搜尋筆記標題與頻道
    for item in vault.notes_flat:
        if query in item["title"].lower() or query in item["channel"].lower():
            results.append({
                "type": "note",
                "title": item["title"],
                "channel": item["channel"],
                "path": item["path"],
                "stem": item["stem"]
            })
            if len(results) >= 30:
                break

    # 2. 搜尋個股索引代號與名稱
    for stock in vault.stock_indexes:
        if query in stock["full_name"].lower() or query in stock["code"].lower() or query in stock["name"].lower():
            results.append({
                "type": "stock",
                "title": f"個股歷史索引：{stock['full_name']}",
                "channel": "個股歷史索引",
                "path": stock["path"],
                "stem": stock["stem"]
            })
            if len(results) >= 50:
                break

    return {"query": q, "results": results}

@app.get("/api/resolve_wikilink")
async def resolve_wikilink(target: str):
    """解析雙括號 WikiLink 目標字串，返回相對應的相對檔案路徑"""
    clean_target = target.strip().split("#")[0]
    
    # 精確比對 stem
    if clean_target in vault.stem_to_path:
        p = vault.stem_to_path[clean_target]
        rel_path = str(p.relative_to(BASE_DIR)).replace("\\", "/")
        return {"found": True, "path": rel_path, "stem": clean_target}

    # 模糊比對
    for stem, p in vault.stem_to_path.items():
        if clean_target.lower() in stem.lower() or stem.lower() in clean_target.lower():
            rel_path = str(p.relative_to(BASE_DIR)).replace("\\", "/")
            return {"found": True, "path": rel_path, "stem": stem}

    return {"found": False, "target": target}

@app.get("/api/note")
async def get_note_content(path: str):
    """取得指定路徑 Markdown 的內容並轉譯為 HTML"""
    clean_path = path.replace("\\", "/").strip()
    target_file = BASE_DIR / clean_path
    
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="找不到指定的研報檔案")

    try:
        raw_md = target_file.read_text(encoding="utf-8", errors="ignore")
        
        # 轉換 WikiLinks
        md_with_links = convert_wikilinks_to_html(raw_md)
        
        # 使用 Python Markdown 渲染 HTML
        html_content = markdown.markdown(
            md_with_links,
            extensions=["fenced_code", "tables", "nl2br", "attr_list", "toc"]
        )

        return {
            "path": clean_path,
            "filename": target_file.name,
            "stem": target_file.stem,
            "raw_md": raw_md,
            "html": html_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取檔案失敗: {str(e)}")

@app.post("/api/refresh")
async def refresh_cache():
    """重新整理快取"""
    vault.refresh_cache()
    return {"status": "ok", "total_notes": len(vault.notes_flat), "total_stocks": len(vault.stock_indexes)}

if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="YouTube 股票分析 Web 內網閱讀器")
    parser.add_argument("--port", type=int, default=23300, help="內網服務 Port (預設 23300)")
    args = parser.parse_args()
    
    CURRENT_PORT = args.port
    ips = get_lan_ips()
    
    print("=========================================================")
    print("[SERVER] YouTube Stock Analyzer Web Reader Started!")
    print(f"[SERVER] Local Access: http://localhost:{CURRENT_PORT}")
    for ip in ips:
        print(f"[SERVER] LAN Device Access: http://{ip}:{CURRENT_PORT}")
    print("=========================================================")
    
    uvicorn.run(app, host="0.0.0.0", port=CURRENT_PORT)


