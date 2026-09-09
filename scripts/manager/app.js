const icons = {
  dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  book: '<path d="M12 5C8 2 3 3 3 3v16s5-1 9 2c4-3 9-2 9-2V3s-5-1-9 2v16"/>',
  external: '<path d="M14 3h7v7M10 14 21 3M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M20 7V3l-3 3a8 8 0 0 0-13 5M4 17v4l3-3a8 8 0 0 0 13-5M20 7h-5M4 17h5"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  pen: '<path d="m14 5 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14z"/>',
  leaf: '<path d="M20 3C6 2 2 8 5 15c5 6 15 3 15-12ZM5 21 15 9"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
};
const select = selector => document.querySelector(selector);
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const labels = {published: '已收录', draft: '草稿', trash: '回收站'};
const state = {records: [], images: [], token: '', view: 'overview', filter: 'all', query: '', current: null, dirty: false, busy: false, pickerMode: null, replacement: null, replacing: false};
let toastTimeout;

function hydrateIcons() {
  document.querySelectorAll('[data-icon]').forEach(element => { element.innerHTML = icon(element.dataset.icon); });
}

function toast(message, error = false) {
  const element = select('#toast');
  element.textContent = message;
  element.classList.toggle('error', error);
  element.hidden = false;
  element.showPopover?.();
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => { element.hidePopover?.(); element.hidden = true; }, error ? 8000 : 4200);
}

async function api(path, payload) {
  const options = payload === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Manager-Token': state.token}, body: JSON.stringify(payload)
  };
  const response = await fetch(`/api/${path}`, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败');
  return result;
}

async function load() {
  const response = await api('state');
  Object.assign(state, response, {projects: response.projects, about: response.about});
  state.needsRestart = !response.server_info || response.server_info.needs_restart || !response.projects || !response.about || !response.appearance;
  const warning = select('#service-warning');
  warning.hidden = !state.needsRestart;
  warning.textContent = state.needsRestart ? '当前连接的是旧版工作台服务，作品和关于页面的编辑功能尚未加载。仅刷新网页无效：请先关闭所有运行 blog_manager.py 的旧终端窗口，再双击 manage-blog.cmd。如果仍有端口占用，可运行 python scripts/blog_manager.py --port 8766，打开新地址。' : '';
  select('#nav-count').textContent = state.records.filter(record => record.status !== 'trash').length;
  render();
}

async function safely(action) {
  try { await action(); } catch (error) { toast(error.message || '连接失败，请检查管理工具是否还在运行。', true); }
}

function safeImage(path) {
  return state.images.some(image => image.path === path) ? path : '';
}

function imageUrl(path) {
  const image = state.images.find(item => item.path === path);
  return image ? `${path.split('/').map(encodeURIComponent).join('/')}?v=${image.revision || ''}` : '';
}

function thumbnail(record) {
  const path = safeImage(record.cover);
  return path ? `<img class="thumb" src="${escapeHtml(imageUrl(path))}" alt="" loading="lazy">` : '<span class="thumb"></span>';
}

function rating(record) {
  return record.body.match(/(?:游戏|个人)?评分[：:]\s*(\d+(?:\.\d+)?)/)?.[1] || '—';
}

function empty(message, detail = '') {
  return `<div class="empty">${icon('leaf')}${escapeHtml(message)}<p>${escapeHtml(detail)}</p></div>`;
}

function articleTable(records, compact = false) {
  if (!records.length) return empty('这里还没有文章', state.view === 'trash' ? '移入回收站的文章可以随时恢复为草稿。' : '从一篇新记录开始吧，或试试其他搜索关键词。');
  return `<div class="table-wrap"><table class="${compact ? 'overview-table' : ''}"><thead><tr><th>文章</th><th>状态</th><th class="date-cell">收录日期</th><th>${compact ? '评分' : '操作'}</th></tr></thead><tbody>${records.map(record => `<tr>
    <td><div class="article-cell">${thumbnail(record)}<div><button class="article-title" data-action="${record.status === 'trash' ? 'restore' : 'edit'}" data-slug="${escapeHtml(record.slug)}" data-status="${record.status}">${escapeHtml(record.title)}</button><p class="article-meta">游戏评测 <span>· ${record.body.replace(/\s/g, '').length.toLocaleString()} 字</span></p></div></div></td>
    <td><span class="badge ${record.status}">${labels[record.status]}</span></td><td class="date-cell">${escapeHtml(record.imported)}</td>
    <td>${compact ? `<span style="color:#7c957f">${rating(record)}</span>` : `<div class="row-actions">${record.status === 'trash' ? `<button data-action="restore" data-slug="${record.slug}" data-status="trash">恢复草稿</button>` : `<button data-action="edit" data-slug="${record.slug}" data-status="${record.status}">编辑</button>${record.status === 'published' ? `<a href="/games/${record.slug}/" target="_blank" rel="noopener">预览</a>` : ''}<button class="danger" data-action="trash" data-slug="${record.slug}" data-status="${record.status}" aria-label="移入回收站：${escapeHtml(record.title)}">回收</button>`}</div>`}</td></tr>`).join('')}</tbody></table></div>`;
}

function statCard(label, value, note, symbol) {
  return `<div class="stat"><span class="stat-label">${label}</span><span class="stat-icon">${icon(symbol)}</span><div class="stat-value">${value}</div><p class="stat-foot">${note}</p></div>`;
}

function quickAction(action, title, description, symbol) {
  return `<button class="quick-action" data-action="${action}"><span class="quick-icon">${icon(symbol)}</span><span><strong>${title}</strong><small>${description}</small></span><span class="arrow">↗</span></button>`;
}

function overview() {
  const active = state.records.filter(record => record.status !== 'trash');
  const published = active.filter(record => record.status === 'published');
  const words = published.reduce((total, record) => total + record.body.replace(/\s/g, '').length, 0);
  return `<section class="hero"><div class="hero-copy"><p class="hero-kicker">A LITTLE SPACE FOR BIG IDEAS</p><h2>欢迎回来，Seven 👋</h2><p>游戏里的冒险，生活里的灵感。<br>在这里，继续书写属于你的故事。</p></div><div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="paper">${icon('leaf')}<span class="paper-line"></span><span class="paper-line"></span><span class="paper-line short"></span><span class="paper-line short"></span></div><div class="pencil"></div><span class="spark">✦</span><span class="spark small">✧</span></div></section>
    <section class="stats" aria-label="博客统计">${statCard('已收录文章', published.length.toString().padStart(2, '0'), '每一篇都是热爱的印记', 'file')}${statCard('草稿箱', active.length - published.length, '留给还在酝酿的灵感', 'pen')}${statCard('图片素材', state.images.length, '所有图片均存储在本地', 'image')}${statCard('累计创作字数', (words / 1000).toFixed(1) + 'k', '按正文非空白字符统计', 'book')}</section>
    <div class="overview-grid"><section class="panel"><div class="panel-heading"><div><h2>最近的文章</h2><p>继续打磨你的记录</p></div><button class="text-button" data-action="articles">查看全部 ↗</button></div>${articleTable(active.slice(0, 5), true)}<div class="below-note"><span>共 ${active.length} 篇文章 · 最近更新优先</span><span>每一个字，都有意义</span></div></section>
    <aside class="panel quick-panel"><div class="panel-heading"><h2>快捷操作</h2><span class="muted">↗</span></div><div class="quick-actions">${quickAction('new', '开始写作', '记录一个新想法', 'pen')}${quickAction('upload', '上传图片', '给文字多一些画面', 'upload')}${quickAction('build', '重新生成博客', '同步文章与所有索引', 'refresh')}${quickAction('backup', '导出内容备份', '文章、素材与本地历史', 'download')}</div><div class="note"><strong>✧ 只管创作，其余交给工作台</strong>保存时自动保留上一版。草稿与回收站只留在本机，不会进入公开站点。</div></aside></div>`;
}

function mediaCard(image, picker = false) {
  return `<${picker ? 'button' : 'article'} class="media-card" ${picker ? `data-image="${escapeHtml(image.path)}"` : ''}><img src="${escapeHtml(imageUrl(image.path))}" alt="${escapeHtml(image.name)}" loading="lazy"><div class="media-card-copy"><strong>${escapeHtml(image.name)}</strong><p title="${escapeHtml(image.path)}">${escapeHtml(image.path)}</p><p>${(image.size / 1024).toFixed(0)} KB · 本地素材</p>${picker ? '' : `<div class="media-card-actions"><button class="button small" data-action="copy-image" data-path="${escapeHtml(image.path)}">复制引用</button><button class="button small" data-action="replace-image" data-path="${escapeHtml(image.path)}">替换图片</button></div>`}</div></${picker ? 'button' : 'article'}>`;
}

function guide() {
  return `<div class="guide-grid"><section class="panel guide-card"><p class="eyebrow">01 / WRITE</p><h2>从写作到本地预览</h2><ol><li>点击「写一篇文章」，填写标题与英文路径。</li><li>写正文、选择封面，并设置 0–10 分的评分。</li><li>暂未完成？保存草稿。它不会出现在博客中。</li><li>点击「保存并生成」，更新文章、首页、分类、标签、归档和搜索索引。</li><li>打开本地博客预览，再进入「云端同步」检查并确认发布。</li></ol></section>
    <section class="panel guide-card"><p class="eyebrow">02 / KEEP SAFE</p><h2>你的内容，安全留存</h2><p>修改前的文章会保存在 <code>.blog-manager/history/</code>。草稿和回收站也在 <code>.blog-manager/</code> 中，该目录已被 Git 忽略。</p><p>回收站支持恢复为草稿；重新收录需要再次「保存并生成」。导出备份包含文章 JSON、全部图片、草稿、回收站和历史版本，不含站点程序。</p><div class="page-links"><button class="button" data-action="backup">${icon('download')}导出内容备份</button></div></section>
    <section class="panel guide-card"><p class="eyebrow">03 / EXPLORE</p><h2>站点页面导航</h2><p>工作台支持游戏评测、游戏作品和关于页面编辑。以下页面可一键预览；其他静态页暂不提供正文编辑。</p><div class="page-links">${[['/', '博客首页'], ['/games/', '游戏评测'], ['/about/', '关于我'], ['/archives/', '归档'], ['/categories/', '分类'], ['/tags/', '标签']].map(([path, title]) => `<a class="button" href="${path}" target="_blank" rel="noopener">${title} ↗</a>`).join('')}</div></section>
    <section class="panel guide-card"><p class="eyebrow">04 / PUBLISH</p><h2>关于发布和恢复</h2><p>「已收录」指内容已加入本地站点，不表示 GitHub 已上线。普通保存只改本地文件。在「云端同步」检查变更后，确认提交并推送 GitHub；Pages 部署状态需另行确认。</p><p>更换电脑前，请导出内容备份。恢复时先关闭工具，解压 ZIP，将需要的文件按原路径复制回仓库，再重新生成。历史版本应复制到对应的文章目录，并恢复为 <code>slug.json</code> 文件名。</p></section></div>`;
}

function render() {
  const names = {overview: ['博客概览', '把想法写下来，让热爱有迹可循。'], articles: ['文章管理', '整理每一次冒险，也收藏每一个灵感。'], media: ['图片素材', '让文字之外的画面，也井井有条。'], trash: ['回收站', '暂时收起的记录，随时可以重新开始。'], guide: ['使用指南', '一个轻量、安心、属于你的博客工作台。'], projects: ['游戏作品', '从想法到可游玩的世界，管理你的创作。'], about: ['关于页面', '让读者认识作品背后的你。'], cloud: ['云端同步', '检查文件，确认发布，同步到 GitHub。']};
  names.appearance = ['样式与颜色', '调配博客的颜色与外观，预览后再发布。'];
  const [title, subtitle] = names[state.view];
  select('#breadcrumb').textContent = state.view === 'overview' ? '概览' : title;
  select('#page-title').innerHTML = `${title}<span class="heading-dot">.</span>`;
  select('#page-subtitle').textContent = subtitle;
  const primaryAction = select('#new-post');
  const studioView = state.view === 'projects' || state.view === 'about';
  primaryAction.innerHTML = icon(state.view === 'about' ? 'pen' : 'plus') + (state.view === 'projects' ? '新增游戏作品' : state.view === 'about' ? '编辑关于页面' : '写一篇文章');
  primaryAction.disabled = studioView && (!state.projects || !state.about || state.needsRestart);
  if (state.view === 'appearance') {
    primaryAction.innerHTML = icon('pen') + '编辑样式与颜色';
    primaryAction.disabled = !state.appearance || state.needsRestart;
  }
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === state.view));
  if (state.view === 'overview') select('#content').innerHTML = overview();
  else if (state.view === 'appearance') select('#content').innerHTML = renderAppearance();
  else if (['projects', 'about', 'cloud'].includes(state.view)) select('#content').innerHTML = renderStudioView(state.view);
  else if (state.view === 'guide') select('#content').innerHTML = guide();
  else if (state.view === 'media') {
    select('#content').innerHTML = `<div class="filterbar"><div class="search"><input id="media-search" type="search" placeholder="搜索文件名或路径…" aria-label="搜索素材"></div><button class="button" data-action="upload">${icon('upload')}上传图片</button></div><div id="media-results" class="media-grid"></div>`;
    renderMedia();
  } else {
    select('#content').innerHTML = `<div class="filterbar"><div class="tabs">${(state.view === 'trash' ? ['trash'] : ['all', 'published', 'draft']).map(status => `<button class="tab ${state.filter === status || state.view === 'trash' ? 'active' : ''}" data-filter="${status}">${status === 'all' ? '全部文章' : labels[status]} <span>${state.records.filter(record => status === 'all' ? record.status !== 'trash' : record.status === status).length}</span></button>`).join('')}</div><div class="search"><input id="article-search" type="search" placeholder="搜索文章标题或正文…" aria-label="搜索文章" value="${escapeHtml(state.query)}"></div></div><div id="article-results" class="panel"></div>`;
    renderArticles();
  }
}

function renderArticles() {
  const records = state.records.filter(record => (state.view === 'trash' ? record.status === 'trash' : record.status !== 'trash' && (state.filter === 'all' || record.status === state.filter)) && `${record.title} ${record.body} ${record.slug}`.toLowerCase().includes(state.query.toLowerCase()));
  select('#article-results').innerHTML = articleTable(records);
}

function renderMedia() {
  const query = select('#media-search').value.toLowerCase();
  const images = state.images.filter(image => image.path.toLowerCase().includes(query));
  select('#media-results').innerHTML = images.length ? images.map(image => mediaCard(image)).join('') : empty('没有找到图片');
}

function navigate(view) {
  state.view = view;
  state.filter = 'all';
  state.query = '';
  render();
}

function setDirty() {
  state.dirty = true;
  select('#save-status').textContent = '有未保存的修改';
  select('#word-count').textContent = `${select('#post-body').value.replace(/\s/g, '').length.toLocaleString()} 字`;
}

function updateCover() {
  const path = safeImage(select('#post-cover').value);
  select('#choose-cover').innerHTML = path ? `<img src="${escapeHtml(imageUrl(path))}" alt="当前封面，点击更换">` : `${icon('image')}<span>从素材库选择封面</span>`;
}

function openEditor(record = null) {
  if (state.dirty && !confirm('放弃当前未保存的修改？')) return;
  state.current = record;
  state.dirty = false;
  select('#editor-form').reset();
  select('#editor-heading').textContent = record ? '编辑文章' : '写一篇新文章';
  select('#post-title').value = record?.title || '';
  select('#post-slug').value = record?.slug || '';
  select('#post-slug').disabled = !!record;
  select('#post-date').value = record?.imported || new Date().toLocaleDateString('sv-SE');
  select('#post-score').value = record && rating(record) !== '—' ? rating(record) : '';
  select('#post-body').value = record?.body || '';
  select('#post-cover').value = record?.cover || '';
  select('#save-status').textContent = record ? `${labels[record.status]} · 原文及来源信息会保留` : '草稿只保存在本机';
  select('#save-draft').textContent = record?.status === 'published' ? '转为草稿' : '保存草稿';
  select('#word-count').textContent = `${(record?.body || '').replace(/\s/g, '').length.toLocaleString()} 字`;
  select('#body-preview').innerHTML = '<p class="muted">点击「刷新预览」查看排版。</p>';
  updateCover();
  select('#editor').showModal();
}

function closeEditor() {
  if (state.busy) return;
  if (state.dirty && !confirm('修改还没有保存，确定关闭？')) return;
  state.dirty = false;
  select('#editor').close();
}

function editorRecord() {
  let body = select('#post-body').value;
  const score = select('#post-score').value;
  if (score !== '') {
    const pattern = /((?:游戏|个人)?评分[：:]\s*)\d+(?:\.\d+)?/;
    body = pattern.test(body) ? body.replace(pattern, `$1${score}`) : `${body.trimEnd()}\n\n游戏评分：${score}`;
  }
  const original = state.current || {};
  const {status, revision, ...record} = original;
  return {...record, title: select('#post-title').value.trim(), slug: select('#post-slug').value.trim(), imported: select('#post-date').value,
    cover: select('#post-cover').value.trim(), body, source_id: original.source_id || '', source_updated: original.source_id ? original.source_updated : new Date().toISOString()};
}

async function save(status) {
  if (state.busy || !select('#editor-form').reportValidity()) return;
  if (status === 'draft' && state.current?.status === 'published' && !confirm('转为草稿会从本地博客及索引中移除此文，线上网站要等你推送后才会变化。继续？')) return;
  const record = editorRecord();
  const payload = {record, status, previous_status: state.current?.status, revision: state.current?.revision};
  state.busy = true;
  select('#editor-form').querySelectorAll('button, input, textarea').forEach(element => { element.disabled = true; });
  try {
    const result = await api('save', payload);
    state.current = result.record;
    state.dirty = false;
    select('#post-body').value = record.body;
    select('#save-status').textContent = `已保存 · ${new Date().toLocaleTimeString('zh-CN')}`;
    select('#save-draft').textContent = status === 'published' ? '转为草稿' : '保存草稿';
    toast(status === 'draft' ? '草稿已安全保存在本机' : `已保存，并更新 ${result.changed} 个本地站点文件。尚未推送上线。`);
    await load();
  } finally {
    state.busy = false;
    select('#editor-form').querySelectorAll('button, input, textarea').forEach(element => { element.disabled = false; });
    select('#post-slug').disabled = !!state.current;
  }
}

function insertText(before, after = '') {
  const textarea = select('#post-body');
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selected = textarea.value.slice(start, end);
  textarea.setRangeText(`${before}${selected}${after}`, start, end, 'end');
  textarea.focus();
  setDirty();
}

function openPicker(mode) {
  state.pickerMode = mode;
  select('#picker-search').value = '';
  renderPicker();
  select('#media-picker').showModal();
}

function renderPicker() {
  const query = select('#picker-search').value.toLowerCase();
  const candidates = state.images.filter(image => image.path.toLowerCase().includes(query) && (state.pickerMode !== 'body' || image.path.startsWith('/img/games/')));
  select('#picker-grid').innerHTML = candidates.length ? candidates.map(image => mediaCard(image, true)).join('') : empty('还没有合适的图片', '点击上传图片，把画面添加进来。');
}

function readImageFile(file) {
  if (!file.size || file.size > 12 * 1024 * 1024) throw new Error('请选择非空且不超过 12 MB 的图片。');
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(new Error('读取图片失败'));
    reader.readAsDataURL(file);
  });
}

function imageExtension(name) {
  return name.split('.').pop().toLowerCase().replace(/^jpeg$/, 'jpg');
}

function openImageReplacement(path) {
  const image = state.images.find(item => item.path === path);
  if (!image?.revision) throw new Error('请重启工作台并刷新页面，再使用图片替换功能。');
  state.replacement = {image, file: null, data: null};
  select('#replace-image-path').textContent = path;
  select('#replace-image-before').src = imageUrl(path);
  select('#replace-image-after').hidden = true;
  select('#replace-image-after').removeAttribute('src');
  select('#replace-image-placeholder').hidden = false;
  select('#replace-image-file').value = '';
  const extension = imageExtension(image.name);
  select('#replace-image-file').accept = extension === 'jpg' ? '.jpg,.jpeg' : `.${extension}`;
  select('#replace-image-note').textContent = `请选择 ${extension.toUpperCase()} 格式的图片。替换的是文件内容，不会修改文章中的图片路径。`;
  select('#confirm-replace-image').disabled = true;
  select('#replace-image-dialog').showModal();
}

function closeImageReplacement() {
  if (state.replacing) return;
  state.replacement = null;
  select('#replace-image-after').removeAttribute('src');
  select('#replace-image-file').value = '';
  select('#replace-image-dialog').close();
}

async function prepareImageReplacement(file) {
  const replacement = state.replacement;
  if (!replacement || state.replacing) return;
  replacement.file = file;
  replacement.data = null;
  select('#confirm-replace-image').disabled = true;
  select('#replace-image-after').hidden = true;
  select('#replace-image-after').removeAttribute('src');
  select('#replace-image-placeholder').hidden = false;
  select('#replace-image-note').textContent = '请选择新图片。';
  if (!file) return;
  try {
    if (imageExtension(file.name) !== imageExtension(replacement.image.name)) throw new Error('新图片必须与原图格式相同；JPG 与 JPEG 可以互换。');
    const data = await readImageFile(file);
    const preview = new Image();
    preview.src = `data:${file.type || 'image/x-icon'};base64,${data}`;
    await preview.decode();
    if (state.replacement !== replacement || replacement.file !== file) return;
    replacement.data = data;
    select('#replace-image-after').src = preview.src;
    select('#replace-image-after').hidden = false;
    select('#replace-image-placeholder').hidden = true;
    select('#replace-image-note').textContent = `${file.name} · ${preview.naturalWidth} × ${preview.naturalHeight} · ${(file.size / 1024).toFixed(0)} KB。请检查新旧图片，确认后再替换。`;
    select('#confirm-replace-image').disabled = false;
  } catch (error) {
    if (state.replacement !== replacement || replacement.file !== file) return;
    select('#replace-image-note').textContent = error.message || '无法预览此文件，请选择有效的图片。';
    toast(select('#replace-image-note').textContent, true);
  }
}

async function confirmImageReplacement() {
  const replacement = state.replacement;
  if (state.replacing || !replacement?.data) return;
  state.replacing = true;
  select('#replace-image-dialog').querySelectorAll('button, input').forEach(element => { element.disabled = true; });
  select('#confirm-replace-image').textContent = '正在备份并替换…';
  try {
    const result = await api('replace-image', {path: replacement.image.path, revision: replacement.image.revision, name: replacement.file.name, data: replacement.data});
    state.replacement = null;
    select('#replace-image-dialog').close();
    select('#replace-image-after').removeAttribute('src');
    select('#replace-image-file').value = '';
    toast(result.changed ? '图片已替换，旧图已备份。原引用地址保持不变，尚未推送上线。' : '所选图片与原图相同，无需替换。');
    const query = select('#media-search')?.value;
    await load();
    if (state.view === 'media' && query !== undefined) { select('#media-search').value = query; renderMedia(); }
    if (select('#editor').open) updateCover();
    if (select('#media-picker').open) renderPicker();
  } finally {
    state.replacing = false;
    select('#replace-image-dialog').querySelectorAll('button, input').forEach(element => { element.disabled = false; });
    select('#confirm-replace-image').disabled = !state.replacement?.data;
    select('#confirm-replace-image').textContent = '确认替换';
  }
}

async function uploadFiles(files) {
  let uploaded = 0;
  for (const file of files) {
    if (file.size > 12 * 1024 * 1024) throw new Error(`「${file.name}」超过 12 MB，请压缩后上传。此前成功上传的图片已保留。`);
    toast(`正在上传 ${file.name}…`);
    const data = await readImageFile(file);
    await api('upload', {name: file.name, data});
    uploaded += 1;
  }
  await load();
  if (select('#media-picker').open) renderPicker();
  toast(`已上传 ${uploaded} 张图片；相同内容会自动去重。`);
}

async function action(name, button) {
  const record = state.records.find(item => item.slug === button?.dataset.slug && item.status === button?.dataset.status);
  if (name === 'new') openEditor();
  else if (name === 'articles') navigate('articles');
  else if (name === 'edit') openEditor(record);
  else if (name === 'upload') select('#upload-input').click();
  else if (name === 'replace-image') openImageReplacement(button.dataset.path);
  else if (name === 'backup') {
    const link = document.createElement('a');
    link.href = '/api/backup';
    link.download = 'seven-blog-backup.zip';
    link.click();
  } else if (name === 'copy-image') {
    await navigator.clipboard.writeText(`![](${button.dataset.path})`);
    toast('图片引用已复制，可粘贴到正文中。');
  } else if (name === 'build') {
    button.disabled = true;
    try { const result = await api('build', {}); toast(`生成完成，更新了 ${result.changed} 个文件。尚未推送到 GitHub。`); }
    finally { button.disabled = false; }
  } else if (name === 'trash' || name === 'restore') {
    if (name === 'trash' && !confirm(`将「${record.title}」移入回收站？本地站点会移除此文，你可以随时恢复草稿。`)) return;
    button.disabled = true;
    try {
      await api(name, {slug: record.slug, status: record.status, revision: record.revision});
      await load();
      toast(name === 'trash' ? '已移入回收站，原文仍保留在本机。' : '已恢复为草稿，请在文章管理中继续编辑。');
    } finally { button.disabled = false; }
  }
}

document.addEventListener('click', event => {
  const navigation = event.target.closest('[data-view]');
  if (navigation) navigate(navigation.dataset.view);
  const button = event.target.closest('[data-action]');
  if (button) safely(() => action(button.dataset.action, button));
  const filter = event.target.closest('[data-filter]');
  if (filter) { state.filter = filter.dataset.filter; render(); }
  const image = event.target.closest('[data-image]');
  if (image) {
    if (state.pickerMode === 'cover') { select('#post-cover').value = image.dataset.image; updateCover(); setDirty(); }
    else insertText(`\n![](${image.dataset.image})\n`);
    select('#media-picker').close();
  }
});
document.addEventListener('input', event => {
  if (event.target.id === 'article-search') { state.query = event.target.value; renderArticles(); }
  if (event.target.id === 'media-search') renderMedia();
  if (event.target.id === 'picker-search') renderPicker();
  if (event.target.closest('#editor-form')) setDirty();
  if (event.target.id === 'post-cover') updateCover();
});
select('#new-post').addEventListener('click', () => safely(() => {
  if (state.view === 'projects') openStudioEditor('projects');
  else if (state.view === 'about') openStudioEditor('about');
  else if (state.view === 'appearance') openStudioEditor('appearance');
  else openEditor();
}));
select('#refresh').addEventListener('click', () => safely(async () => { await load(); toast('数据已刷新'); }));
select('#close-editor').addEventListener('click', closeEditor);
select('#editor').addEventListener('cancel', event => { event.preventDefault(); closeEditor(); });
select('#close-picker').addEventListener('click', () => select('#media-picker').close());
select('#choose-cover').addEventListener('click', () => openPicker('cover'));
select('#insert-image').addEventListener('click', () => openPicker('body'));
select('#picker-upload').addEventListener('click', () => select('#upload-input').click());
select('#bold-text').addEventListener('click', () => insertText('**', '**'));
select('#strike-text').addEventListener('click', () => insertText('~~', '~~'));
select('#preview-text').addEventListener('click', () => safely(async () => {
  const result = await api('preview', {record: editorRecord()});
  select('#body-preview').innerHTML = result.html || '<p class="muted">写点什么，再来看看吧。</p>';
  if (window.innerWidth < 850) select('#body-preview').scrollIntoView({behavior: 'smooth'});
}));
select('#editor-form').addEventListener('submit', event => { event.preventDefault(); safely(() => save('published')); });
select('#save-draft').addEventListener('click', () => safely(() => save('draft')));
select('#upload-input').addEventListener('change', event => {
  const files = Array.from(event.target.files);
  event.target.value = '';
  if (files.length) safely(() => uploadFiles(files));
});
select('#close-replace-image').addEventListener('click', closeImageReplacement);
select('#cancel-replace-image').addEventListener('click', closeImageReplacement);
select('#replace-image-dialog').addEventListener('cancel', event => { event.preventDefault(); closeImageReplacement(); });
select('#replace-image-file').addEventListener('change', event => safely(() => prepareImageReplacement(event.target.files[0])));
select('#confirm-replace-image').addEventListener('click', () => safely(confirmImageReplacement));
window.addEventListener('beforeunload', event => { if (state.dirty || state.busy || state.replacing) { event.preventDefault(); event.returnValue = ''; } });
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && select('#editor').open) {
    event.preventDefault();
    safely(() => save(state.current?.status === 'published' ? 'published' : 'draft'));
  }
});
hydrateIcons();
safely(load);
