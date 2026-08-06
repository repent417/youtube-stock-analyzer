import argparse
import sys
import io
import shutil
import re
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
NOTES_DIR = BASE_DIR / "影片筆記"
TRANSCRIPTS_DIR = BASE_DIR / "原始字幕"
INDEX_DIR = BASE_DIR / "個股索引"

def delete_channel_data(channel_name: str, dry_run: bool = False):
    """
    一鍵刪除特定頻道的所有筆記、字幕與個股索引關聯
    """
    channel_name = channel_name.strip()
    print(f"🔍 [{ 'DRY-RUN 預覽' if dry_run else '正式執行' }] 正在掃描頻道: 『{channel_name}』...")
    
    # 尋找匹配的頻道目錄 (精確比對與模糊比對)
    matching_note_dirs = []
    for d in NOTES_DIR.iterdir():
        if d.is_dir() and (channel_name.lower() in d.name.lower() or d.name.lower() in channel_name.lower()):
            matching_note_dirs.append(d)

    matching_transcript_dirs = []
    for d in TRANSCRIPTS_DIR.iterdir():
        if d.is_dir() and (channel_name.lower() in d.name.lower() or d.name.lower() in channel_name.lower()):
            matching_transcript_dirs.append(d)

    if not matching_note_dirs and not matching_transcript_dirs:
        print(f"⚠️ 找不到頻道 『{channel_name}』 的任何筆記或字幕目錄！")
        return

    # 1. 統計與刪除筆記目錄
    note_files = []
    for d in matching_note_dirs:
        files = list(d.glob('*.md'))
        note_files.extend(files)
        print(f"📁 發現影片筆記目錄: {d.relative_to(BASE_DIR)} (包含 {len(files)} 篇研報)")

    # 2. 統計與刪除字幕目錄
    transcript_files = []
    for d in matching_transcript_dirs:
        files = list(d.glob('*.txt'))
        transcript_files.extend(files)
        print(f"📄 發現原始字幕目錄: {d.relative_to(BASE_DIR)} (包含 {len(files)} 篇逐字稿)")

    # 3. 掃描與清理 個股索引/ 內的頻道連結
    modified_index_files = []
    deleted_index_files = []

    for index_file in INDEX_DIR.glob('*.md'):
        content = index_file.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()
        
        new_lines = []
        has_channel_entry = False
        
        for line in lines:
            # 比對是否為該頻道的紀錄行
            is_target_channel = False
            for d in matching_note_dirs:
                if f"頻道：`{d.name}`" in line or f"（頻道：`{channel_name}`）" in line:
                    is_target_channel = True
                    break
                    
            if is_target_channel:
                has_channel_entry = True
            else:
                new_lines.append(line)
                
        if has_channel_entry:
            # 檢查剩下的內容是否包含剩餘的分析紀錄 (以 '- **[' 開頭)
            remaining_entries = [l for l in new_lines if l.strip().startswith('- **[')]
            
            if not remaining_entries:
                deleted_index_files.append(index_file)
            else:
                modified_index_files.append((index_file, '\n'.join(new_lines) + '\n'))

    print(f"\n📊 掃描統計彙整:")
    print(f"  - 筆記目錄: {len(matching_note_dirs)} 個 ({len(note_files)} 篇研報)")
    print(f"  - 字幕目錄: {len(matching_transcript_dirs)} 個 ({len(transcript_files)} 篇逐字稿)")
    print(f"  - 需更新連結的個股索引: {len(modified_index_files)} 個")
    print(f"  - 變成空檔並需刪除的個股索引: {len(deleted_index_files)} 個")

    if dry_run:
        print("\n💡 以上為 DRY-RUN 預覽，未實際修改任何檔案。如需實際執行刪除，請勿傳入 --dry-run。")
        return

    # 執行正式刪除
    print("\n🗑️ 開始執行刪除作業...")
    
    # 刪除筆記目錄
    for d in matching_note_dirs:
        shutil.rmtree(d)
        print(f"  ✅ 已刪除筆記目錄: {d.name}")

    # 刪除字幕目錄
    for d in matching_transcript_dirs:
        shutil.rmtree(d)
        print(f"  ✅ 已刪除字幕目錄: {d.name}")

    # 更新個股索引
    for index_file, new_content in modified_index_files:
        index_file.write_text(new_content, encoding='utf-8')
        print(f"  ✏️ 已移除頻道連結: {index_file.name}")

    # 刪除空個股索引
    for index_file in deleted_index_files:
        index_file.unlink()
        print(f"  🗑️ 已刪除無紀錄個股索引: {index_file.name}")

    print("\n🎉 頻道 『" + channel_name + "』 的所有資料與連動索引已全數清理完畢！")

def main():
    parser = argparse.ArgumentParser(description="一鍵清理特定財經頻道的所有筆記、字幕與個股索引連結工具")
    parser.add_argument("--channel", type=str, required=True, help="欲刪除的頻道名稱 (例如 恥股夯妮)")
    parser.add_argument("--dry-run", action="store_true", help="僅測試預覽，不實際刪除檔案")
    args = parser.parse_args()

    delete_channel_data(args.channel, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
