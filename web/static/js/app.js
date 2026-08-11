// 全域 SPA 狀態管理
const state = {
  activeTab: 'channels', // 'channels' | 'stocks'
  channels: {},
  stocks: [],
  currentPath: '',
  currentNoteStem: '',
  currentRawMd: '',
  fontSize: 1.05 // rem
};

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  bindEvents();
  await loadChannels();
  await loadStocks();
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

  // 閱讀器工具列
  document.getElementById('btn-font-plus').addEventListener('click', () => changeFontSize(0.1));
  document.getElementById('btn-font-minus').addEventListener('click', () => changeFontSize(-0.1));
  document.getElementById('btn-copy-link').addEventListener('click', copyCurrentLink);

  // 手機版側邊欄開關
  const mobileBtn = document.getElementById('mobile-toggle-btn');
  if (mobileBtn) {
    mobileBtn.addEventListener('click', () => {
      document.querySelector('.sidebar').classList.toggle('open');
    });
  }
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
    
    // 更新統計與 UI
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
    // 關閉手機側邊欄
    document.querySelector('.sidebar').classList.remove('open');

    const res = await fetch(`/api/note?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) {
      alert('無法開啟指定的筆記檔案');
      return;
    }

    const data = await res.json();
    state.currentPath = data.path;
    state.currentNoteStem = data.stem;
    state.currentRawMd = data.raw_md;

    // 更新頂部路徑與內容
    document.getElementById('current-path-text').innerText = data.path;
    const body = document.getElementById('reader-body');
    body.innerHTML = `<div class="markdown-body">${data.html}</div>`;
    body.style.fontSize = `${state.fontSize}rem`;

    // 高亮對應條目
    updateActiveNoteItem(filePath);

    // 捲動回頁首
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
      alert(`⚠️ 找不到 WikiLink 目標: [[${targetStem}]]`);
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
      // 搜尋頻道筆記
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

function updateActiveNoteItem(filePath) {
  document.querySelectorAll('.note-item, .stock-item').forEach(el => el.classList.remove('active'));
}

function changeFontSize(delta) {
  state.fontSize = Math.min(Math.max(0.85, state.fontSize + delta), 1.6);
  const body = document.getElementById('reader-body');
  if (body) {
    body.style.fontSize = `${state.fontSize}rem`;
  }
}

function copyCurrentLink() {
  if (!state.currentPath) return;
  const fullUrl = `${window.location.origin}/#${state.currentPath}`;
  navigator.clipboard.writeText(fullUrl).then(() => {
    alert('✅ 已複製本篇研報網址！可在內網複製給其他裝置開啟。');
  });
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
