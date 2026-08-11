// 全域 SPA 狀態管理與設定
const state = {
  activeTab: 'channels', // 'channels' | 'stocks'
  channels: {},
  stocks: [],
  currentPath: '',
  currentNoteStem: '',
  currentRawMd: '',
  fontSize: parseFloat(localStorage.getItem('web_reader_font_size')) || 1.05,
  theme: localStorage.getItem('web_reader_theme') || 'dark-purple',
  fontFamily: localStorage.getItem('web_reader_font_family') || 'sans'
};

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  applyStoredSettings();
  bindEvents();
  await loadChannels();
  await loadStocks();
}

function applyStoredSettings() {
  // 1. 載入主題
  document.body.setAttribute('data-theme', state.theme);
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-theme') === state.theme);
  });

  // 2. 載入字體大小
  updateReaderFontSize(state.fontSize);
  const slider = document.getElementById('font-size-slider');
  const label = document.getElementById('font-size-label');
  if (slider) slider.value = state.fontSize;
  if (label) label.innerText = `${state.fontSize.toFixed(2)}rem`;

  // 3. 載入字型風格
  updateReaderFontFamily(state.fontFamily);
  const fontSelect = document.getElementById('font-family-select');
  if (fontSelect) fontSelect.value = state.fontFamily;
}

function bindEvents() {
  // 分頁切換
  document.getElementById('tab-channels').addEventListener('click', () => switchTab('channels'));
  document.getElementById('tab-stocks').addEventListener('click', () => switchTab('stocks'));

  // 搜尋
  const searchInput = document.getElementById('search-input');
  let searchTimer = null;
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => handleSearch(e.target.value), 250);
  });

  // 閱讀器工具列按鈕
  document.getElementById('btn-font-plus').addEventListener('click', () => changeFontSize(0.08));
  document.getElementById('btn-font-minus').addEventListener('click', () => changeFontSize(-0.08));
  document.getElementById('btn-copy-link').addEventListener('click', copyCurrentLink);

  // 設定對話框按鈕
  const modal = document.getElementById('settings-modal');
  document.getElementById('btn-settings').addEventListener('click', () => {
    modal.style.display = 'flex';
  });

  document.getElementById('modal-close-btn').addEventListener('click', () => {
    modal.style.display = 'none';
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });

  // 主題切換
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const themeName = btn.getAttribute('data-theme');
      state.theme = themeName;
      localStorage.setItem('web_reader_theme', themeName);
      document.body.setAttribute('data-theme', themeName);
      document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      showToast(`🎨 已切換至「${btn.innerText.trim()}」主題`);
    });
  });

  // 字體大小 Slider
  const fontSlider = document.getElementById('font-size-slider');
  fontSlider.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    state.fontSize = val;
    localStorage.setItem('web_reader_font_size', val);
    document.getElementById('font-size-label').innerText = `${val.toFixed(2)}rem`;
    updateReaderFontSize(val);
  });

  // 字型風格 Select
  const fontSelect = document.getElementById('font-family-select');
  fontSelect.addEventListener('change', (e) => {
    const fontVal = e.target.value;
    state.fontFamily = fontVal;
    localStorage.setItem('web_reader_font_family', fontVal);
    updateReaderFontFamily(fontVal);
    showToast(`✍️ 已切換內文字型風格`);
  });

  // 手機版側邊欄開關
  const mobileBtn = document.getElementById('mobile-toggle-btn');
  if (mobileBtn) {
    mobileBtn.addEventListener('click', () => {
      document.querySelector('.sidebar').classList.toggle('open');
    });
  }
}

function updateReaderFontSize(sizeRem) {
  document.documentElement.style.setProperty('--reader-font-size', `${sizeRem}rem`);
}

function updateReaderFontFamily(fontKey) {
  let fontStr = "'Inter', 'Noto Sans TC', sans-serif";
  if (fontKey === 'serif') {
    fontStr = "'Noto Serif TC', Georgia, serif";
  } else if (fontKey === 'mono') {
    fontStr = "Consolas, 'Courier New', monospace";
  }
  document.documentElement.style.setProperty('--reader-font-family', fontStr);
}

function changeFontSize(delta) {
  state.fontSize = Math.min(Math.max(0.8, state.fontSize + delta), 1.6);
  localStorage.setItem('web_reader_font_size', state.fontSize);
  
  const slider = document.getElementById('font-size-slider');
  const label = document.getElementById('font-size-label');
  if (slider) slider.value = state.fontSize;
  if (label) label.innerText = `${state.fontSize.toFixed(2)}rem`;

  updateReaderFontSize(state.fontSize);
  showToast(`🔤 字體大小: ${state.fontSize.toFixed(2)}rem`);
}

function copyCurrentLink() {
  if (!state.currentPath) {
    showToast('⚠️ 請先點選開啟一篇研報筆記再進行複製');
    return;
  }

  const fullUrl = `${window.location.origin}/#${state.currentPath}`;

  // 優先嘗試 Clipboard API (相容 localhost 與 HTTPS)
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(fullUrl).then(() => {
      showToast('🔗 已將研報網址複製至剪貼簿！可在內網傳發開啟');
    }).catch(() => {
      fallbackCopyText(fullUrl);
    });
  } else {
    fallbackCopyText(fullUrl);
  }
}

function fallbackCopyText(text) {
  try {
    const tempInput = document.createElement('input');
    tempInput.style.position = 'fixed';
    tempInput.style.opacity = '0';
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand('copy');
    document.body.removeChild(tempInput);
    showToast('🔗 已將研報網址複製至剪貼簿！');
  } catch (err) {
    showToast(`🔗 網址: ${text}`);
  }
}

function showToast(msg) {
  const toast = document.getElementById('toast-notification');
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2400);
}

function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll('.nav-tab').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`tab-${tabName}`).classList.add('active');

  const channelsView = document.getElementById('sidebar-channels');
  const stocksView = document.getElementById('sidebar-stocks');

  if (tabName === 'channels') {
    channelsView.style.display = 'block';
    stocksView.style.display = 'none';
  } else {
    channelsView.style.display = 'none';
    stocksView.style.display = 'block';
  }
}

async function loadChannels() {
  try {
    const res = await fetch('/api/channels');
    const data = await res.json();
    state.channels = data.channels;
    
    document.getElementById('stat-notes-count').innerText = data.total_notes.toLocaleString();
    renderChannelsUI();
  } catch (err) {
    console.error('加載頻道列表失敗:', err);
  }
}

function renderChannelsUI() {
  const container = document.getElementById('sidebar-channels');
  container.innerHTML = '';

  for (const [channelName, notes] of Object.entries(state.channels)) {
    const group = document.createElement('div');
    group.className = 'channel-group';

    const header = document.createElement('div');
    header.className = 'channel-header';
    header.innerHTML = `
      <span>📺 ${escapeHtml(channelName)}</span>
      <span class="channel-badge">${notes.length} 篇</span>
    `;

    const notesList = document.createElement('div');
    notesList.className = 'channel-notes';
    notesList.style.display = 'none';

    notes.forEach(note => {
      const item = document.createElement('a');
      item.className = 'note-item';
      item.innerText = note.title;
      item.title = note.title;
      item.addEventListener('click', () => loadNote(note.path));
      notesList.appendChild(item);
    });

    header.addEventListener('click', () => {
      const isOpen = notesList.style.display === 'block';
      notesList.style.display = isOpen ? 'none' : 'block';
    });

    group.appendChild(header);
    group.appendChild(notesList);
    container.appendChild(group);
  }
}

async function loadStocks() {
  try {
    const res = await fetch('/api/stocks');
    const data = await res.json();
    state.stocks = data.stocks;
    
    document.getElementById('stat-stocks-count').innerText = data.total_stocks.toLocaleString();
    renderStocksUI(state.stocks);
  } catch (err) {
    console.error('加載個股索引失敗:', err);
  }
}

function renderStocksUI(stocksList) {
  const container = document.getElementById('sidebar-stocks');
  container.innerHTML = '';

  const grid = document.createElement('div');
  grid.className = 'stock-grid';

  stocksList.forEach(stock => {
    const item = document.createElement('a');
    item.className = 'stock-item';
    item.innerHTML = `
      <span class="stock-code">${escapeHtml(stock.code)}</span>
      <span class="stock-name">${escapeHtml(stock.name)}</span>
    `;
    item.addEventListener('click', () => loadNote(stock.path));
    grid.appendChild(item);
  });

  container.appendChild(grid);
}

async function loadNote(filePath) {
  try {
    document.querySelector('.sidebar').classList.remove('open');

    const res = await fetch(`/api/note?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) {
      showToast('⚠️ 無法開啟指定的筆記檔案');
      return;
    }

    const data = await res.json();
    state.currentPath = data.path;
    state.currentNoteStem = data.stem;
    state.currentRawMd = data.raw_md;

    document.getElementById('current-path-text').innerText = data.path;
    const body = document.getElementById('reader-body');
    body.innerHTML = `<div class="markdown-body">${data.html}</div>`;

    // 重新套用當前設定的字體與風格
    updateReaderFontSize(state.fontSize);
    updateReaderFontFamily(state.fontFamily);

    document.querySelector('.reader-container').scrollTop = 0;
  } catch (err) {
    console.error('加載筆記失敗:', err);
  }
}

async function loadWikiLink(targetStem) {
  try {
    const res = await fetch(`/api/resolve_wikilink?target=${encodeURIComponent(targetStem)}`);
    const data = await res.json();
    
    if (data.found) {
      await loadNote(data.path);
    } else {
      showToast(`⚠️ 找不到 WikiLink 目標: [[${targetStem}]]`);
    }
  } catch (err) {
    console.error('解析 WikiLink 失敗:', err);
  }
}

async function handleSearch(query) {
  if (!query.trim()) {
    renderChannelsUI();
    renderStocksUI(state.stocks);
    return;
  }

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    
    if (state.activeTab === 'stocks') {
      const filteredStocks = state.stocks.filter(s => 
        s.full_name.toLowerCase().includes(query.toLowerCase()) || 
        s.code.toLowerCase().includes(query.toLowerCase())
      );
      renderStocksUI(filteredStocks);
    } else {
      const searchResultsView = document.getElementById('sidebar-channels');
      searchResultsView.innerHTML = '';
      
      const titleEl = document.createElement('div');
      titleEl.className = 'channel-header';
      titleEl.style.background = 'rgba(168, 85, 247, 0.2)';
      titleEl.innerText = `🔍 搜尋結果 (${data.results.length} 項)`;
      searchResultsView.appendChild(titleEl);

      data.results.forEach(resItem => {
        const item = document.createElement('a');
        item.className = 'note-item';
        item.style.display = 'block';
        item.innerText = `${resItem.channel === '個股歷史索引' ? '📈' : '📄'} ${resItem.title}`;
        item.addEventListener('click', () => loadNote(resItem.path));
        searchResultsView.appendChild(item);
      });
    }
  } catch (err) {
    console.error('搜尋失敗:', err);
  }
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m];
  });
}
