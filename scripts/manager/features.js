const studio = {kind: null, index: -1, revision: null, original: null, dirty: false, busy: false, cloud: null, cloudBusy: false, cloudError: '', cloudResult: null};

function studioField(name, label, value = '', multiline = false, required = false) {
  const attributes = `name="${name}" id="studio-${name}" ${required ? 'required' : ''}`;
  return `<div class="studio-field"><label for="studio-${name}">${label}</label>${multiline ? `<textarea ${attributes} rows="5">${escapeHtml(value)}</textarea>` : `<input ${attributes} value="${escapeHtml(value)}">`}</div>`;
}

function studioImageField(name, label, value) {
  return studioField(name, label, value) + `<div class="studio-field"><label for="studio-image-choice">或选择已上传的本地素材</label><select id="studio-image-choice" data-image-field="${name}"><option value="">选择素材（不改变当前图片）</option>${state.images.map(image => `<option value="${escapeHtml(image.path)}">${escapeHtml(image.path)}</option>`).join('')}</select></div>`;
}

function renderStudioView(view) {
  if (view !== 'cloud' && (!state.projects || !state.about || state.needsRestart)) return empty('旧版服务不支持此编辑功能', '请按页面上方提示关闭旧服务并重新启动；刷新网页不会重载 Python 后端。');
  if (view === 'projects') {
    return `<div class="filterbar"><p class="muted">共 ${state.projects.length} 个作品 · 按下方顺序展示</p><div class="row-actions"><a class="button" href="/projects/" target="_blank" rel="noopener">预览作品页 ↗</a><button class="button primary" data-studio="new-project">新增作品</button></div></div><div class="guide-grid">${state.projects.map((project, index) => `<section class="panel guide-card"><span class="badge">${escapeHtml(project.status || '未设状态')}</span><h2>${escapeHtml(project.title)}</h2><p>${escapeHtml(project.description)}</p><div class="page-links"><button class="button" data-studio="edit-project" data-index="${index}">编辑</button><button class="button" data-studio="move-up" data-index="${index}" ${index === 0 ? 'disabled' : ''}>上移</button><button class="button" data-studio="move-down" data-index="${index}" ${index === state.projects.length - 1 ? 'disabled' : ''}>下移</button><button class="button" data-studio="delete-project" data-index="${index}">移除</button></div></section>`).join('') || empty('还没有作品，添加你的第一个游戏吧。')}</div>`;
  }
  if (view === 'about') {
    return `<section class="panel guide-card"><p class="eyebrow">ABOUT YOU</p><h2>${escapeHtml(state.about.name)}</h2><p>${escapeHtml(state.about.tagline || '还没有填写个人简介')}</p><div class="about-source-preview">${escapeHtml(state.about.body || '关于页面的内容将在这里维护。')}</div><div class="page-links"><button class="button primary" data-studio="edit-about">编辑关于页面</button><a class="button" href="/about/" target="_blank" rel="noopener">预览关于页 ↗</a></div></section>`;
  }
  const pending = studio.cloud;
  const cloudNotice = studio.cloudError ? `<div class="cloud-notice cloud-error" role="alert">${escapeHtml(studio.cloudError)}</div>` : studio.cloudResult ? `<div class="cloud-notice" role="status">${escapeHtml(studio.cloudResult.message)}<br>提交：<code>${escapeHtml(studio.cloudResult.commit.slice(0, 12))}</code></div>` : '';
  return `<section class="panel guide-card"><p class="eyebrow">GITHUB SYNC</p><h2>发布到你的博客仓库</h2>${cloudNotice}<p>目标：Seven39c5bb / Seven39c5bb.github.io · main</p><p>先生成本地页面、检查远端和待发布文件，确认后创建提交并推送。不自动合并、不强制推送。需要本机 Git 已登录 GitHub，并配置提交姓名和邮箱。</p><p>仅发布公开站点文件与工作台代码，不包含本地草稿、回收站、备份。已有待推送提交将完整推送，不能过滤其历史文件。下方列表不是敏感内容扫描，请确认没有私密素材。</p><div class="page-links"><button class="button primary" data-studio="cloud-prepare" ${studio.cloudBusy ? 'disabled' : ''}>${studio.cloudBusy ? '正在连接 GitHub…' : '检查变更与远端'}</button></div></section>${pending ? `<section class="panel guide-card cloud-preview"><h2>发布前确认</h2><p>本次文件变更 ${pending.changes.length} 项 · 已有待推送提交 ${pending.commits.length} 个 · 跳过 ${pending.excluded.length} 项</p><ul class="cloud-file-list">${pending.changes.map(item => `<li><code>${escapeHtml(item.status)}</code> ${escapeHtml(item.path)} <small>${(item.size / 1024).toFixed(0)} KB</small></li>`).join('') || '<li>没有新增文件变更</li>'}</ul>${pending.commits.length ? `<h3>同时推送这些已有提交</h3><ul class="cloud-file-list">${pending.commits.map(commit => `<li>${escapeHtml(commit)}</li>`).join('')}</ul>` : ''}${pending.excluded.length ? `<details><summary>未包含的文件</summary><ul>${pending.excluded.map(item => `<li>${escapeHtml(item.path)}</li>`).join('')}</ul></details>` : ''}<p>图片上传到 img/ 后也会发布，即使只用于本地草稿。GitHub Pages 部署完成时间取决于仓库配置，推送成功不等于网站已更新。</p><div class="page-links"><button class="button primary" data-studio="cloud-publish" ${studio.cloudBusy || (!pending.changes.length && !pending.commits.length) ? 'disabled' : ''}>确认提交并推送 GitHub</button></div></section>` : ''}`;
}

function openStudioEditor(kind, index = -1) {
  studio.kind = kind;
  studio.index = index;
  studio.dirty = false;
  studio.revision = state[`${kind}_revision`];
  studio.original = JSON.parse(JSON.stringify(state[kind]));
  select('#studio-dialog-title').textContent = kind === 'projects' ? (index < 0 ? '新增游戏作品' : '编辑游戏作品') : '编辑关于页面';
  if (kind === 'appearance') {
    select('#studio-dialog-title').textContent = '编辑样式与颜色';
    select('#studio-fields').innerHTML = appearanceFields(studio.original);
    updateAppearancePreview();
  } else if (kind === 'projects') {
    const project = studio.original[index] || {};
    select('#studio-fields').innerHTML = studioField('title', '作品名称', project.title, false, true) + studioField('slug', '唯一英文标识（小写字母、数字、连字符）', project.slug, false, true) + studioField('description', '作品介绍', project.description, true, true) + studioField('status', '开发状态，例如开发中 / 即将推出 / 已发布', project.status) + studioField('tags', '标签（用逗号分隔）', (project.tags || []).join(', ')) + studioField('engine', '开发引擎', project.engine) + studioField('role', '我的职责', project.role) + studioImageField('cover', '封面（本地路径或 HTTPS 地址）', project.cover) + ['steam_url', 'play_url', 'download_url', 'source_url'].map((field, position) => studioField(field, ['Steam 地址', '在线游玩地址', '下载地址', '源码地址'][position] + '（HTTPS 或有效本地路径）', project[field])).join('');
  } else {
    const about = studio.original;
    select('#studio-fields').innerHTML = studioField('name', '展示名称', about.name, false, true) + studioField('tagline', '一句话介绍', about.tagline) + studioImageField('avatar', '头像（/img/ 下的本地图片）', about.avatar) + studioField('body', '关于正文（分段、**粗体**、## 二级标题）', about.body, true) + studioField('links', '个人链接（每行：名称 | HTTPS 地址）', about.links.map(link => `${link.label} | ${link.url}`).join('\n'), true);
  }
  select('#studio-dialog').showModal();
}

function closeStudioEditor() {
  if (studio.busy || (studio.dirty && !confirm('资料尚未保存，确定关闭？'))) return;
  studio.dirty = false;
  select('#studio-dialog').close();
}

async function saveStudioEditor(event) {
  event.preventDefault();
  if (studio.busy) return;
  const fields = Object.fromEntries(new FormData(select('#studio-form')).entries());
  let record;
  if (studio.kind === 'appearance') {
    record = appearanceRecord(fields);
  } else if (studio.kind === 'projects') {
    const project = {...(studio.original[studio.index] || {}), ...fields, tags: fields.tags.split(/[,，]/).map(tag => tag.trim()).filter(Boolean)};
    project.slug = project.slug.trim();
    record = [...studio.original];
    if (studio.index < 0) record.push(project); else record[studio.index] = project;
  } else {
    record = {...studio.original, ...fields, links: fields.links.split('\n').filter(line => line.trim()).map(line => {
      const separator = line.indexOf('|');
      if (separator < 1) throw new Error('每行链接请使用「名称 | https://地址」格式');
      return {label: line.slice(0, separator).trim(), url: line.slice(separator + 1).trim()};
    })};
  }
  studio.busy = true;
  select('#studio-form').querySelectorAll('button,input,textarea,select').forEach(element => { element.disabled = true; });
  try {
    await api(`${studio.kind}/save`, {record, revision: studio.revision});
    studio.dirty = false;
    studio.cloud = null;
    select('#studio-dialog').close();
    toast('已保存并生成本地页面，可在「云端同步」中检查并发布。');
    await load();
  } finally {
    studio.busy = false;
    select('#studio-form').querySelectorAll('button,input,textarea,select').forEach(element => { element.disabled = false; });
  }
}

async function studioAction(button) {
  const action = button.dataset.studio;
  if (studio.busy || studio.cloudBusy) return;
  const index = Number(button.dataset.index);
  if (action === 'new-project') return openStudioEditor('projects');
  if (action === 'edit-project') return openStudioEditor('projects', index);
  if (action === 'edit-about') return openStudioEditor('about');
  if (action === 'edit-appearance') return openStudioEditor('appearance');
  if (['delete-project', 'move-up', 'move-down'].includes(action)) {
    const records = [...state.projects];
    if (action === 'delete-project') {
      if (!confirm(`从作品页移除「${records[index].title}」？旧资料会保留在历史备份中。`)) return;
      records.splice(index, 1);
    } else {
      const next = index + (action === 'move-up' ? -1 : 1);
      if (next < 0 || next >= records.length) return;
      [records[index], records[next]] = [records[next], records[index]];
    }
    studio.busy = true;
    try { await api('projects/save', {record: records, revision: state.projects_revision}); studio.cloud = null; await load(); toast('作品列表已更新。'); }
    finally { studio.busy = false; }
    return;
  }
  if (action === 'cloud-prepare' || action === 'cloud-publish') {
    if (action === 'cloud-publish' && (!studio.cloud || !confirm('确认将列出的文件和已有提交推送到 GitHub？公开素材与代码将进入远端仓库。'))) return;
    const ticket = studio.cloud?.ticket;
    studio.cloudBusy = true;
    studio.cloudError = '';
    studio.cloudResult = null;
    if (action === 'cloud-prepare') studio.cloud = null;
    render();
    try {
      if (action === 'cloud-prepare') studio.cloud = await api('cloud/prepare', {});
      else {
        const result = await api('cloud/publish', {ticket});
        studio.cloudResult = result;
        studio.cloud = null;
        toast(result.message);
      }
    } catch (error) {
      studio.cloud = null;
      studio.cloudError = error.message;
      throw error;
    } finally { studio.cloudBusy = false; render(); }
  }
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-studio]');
  if (button) safely(() => studioAction(button));
});
select('#studio-form').addEventListener('submit', event => safely(() => saveStudioEditor(event)));
select('#studio-form').addEventListener('input', () => { studio.dirty = true; });
select('#studio-form').addEventListener('change', event => {
  studio.dirty = true;
  if (event.target.dataset.imageField && event.target.value) select(`#studio-${event.target.dataset.imageField}`).value = event.target.value;
});
select('#studio-close').addEventListener('click', closeStudioEditor);
select('#studio-dialog').addEventListener('cancel', event => { event.preventDefault(); closeStudioEditor(); });
window.addEventListener('beforeunload', event => {
  if (studio.dirty || studio.busy || studio.cloudBusy) { event.preventDefault(); event.returnValue = ''; }
});
