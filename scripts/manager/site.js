let siteLinkId = 0;

function renderSite() {
  if (!state.site || state.needsRestart) return empty('请重启工作台服务', '关闭旧终端后重新双击 manage-blog.cmd，即可使用网站设置。');
  const record = state.site;
  const favicon = imageUrl(record.favicon);
  const links = record.links.map(link => `<li><div><strong>${escapeHtml(link.label)}</strong><span class="badge">${link.enabled ? '已启用' : '已隐藏'}</span><p>${escapeHtml(link.url)}</p></div></li>`).join('');
  return `<section class="panel guide-card"><p class="eyebrow">YOUR LINKS, YOUR IDENTITY</p><h2>个人主页与网站图标</h2><p>不再展示文章 / 标签 / 分类统计和写死的 GitHub 图标。添加的平台链接会以文字按钮展示在首页、个人资料卡和手机侧栏；没有启用链接时不占位置。</p><div class="site-icon-summary">${favicon ? `<img src="${escapeHtml(favicon)}" alt="当前网站图标" width="40" height="40">` : '<span class="site-icon-placeholder">无</span>'}<div><strong>浏览器标签页图标</strong><p>${escapeHtml(record.favicon || '未设置图标')}</p></div></div><ul class="site-links-summary">${links || '<li class="muted">暂未配置个人主页，可添加 GitHub、哔哩哔哩、Steam、itch.io 或其他平台。</li>'}</ul><div class="page-links"><button class="button primary" data-studio="edit-site">编辑网站设置</button><a class="button" href="/" target="_blank" rel="noopener">预览首页 ↗</a></div><p>这里管理全站入口；「关于页面」中的正文链接仍可单独编辑。保存只生成本地页面，确认后到「云端同步」发布。隐藏的链接仍保存在公开配置文件里，请不要填写私密地址。</p></section>`;
}

function siteLinkRow(link = {label: '', url: '', enabled: true}) {
  const identifier = ++siteLinkId;
  return `<fieldset class="site-link-row"><legend>个人主页</legend><div class="site-link-fields"><div class="studio-field"><label for="site-link-label-${identifier}">平台 / 展示名称</label><input id="site-link-label-${identifier}" data-profile-label value="${escapeHtml(link.label)}" maxlength="40" placeholder="例如 GitHub、哔哩哔哩、Steam" required></div><div class="studio-field"><label for="site-link-url-${identifier}">个人主页地址</label><input id="site-link-url-${identifier}" data-profile-url type="url" value="${escapeHtml(link.url)}" maxlength="2048" placeholder="https://…" required></div></div><div class="site-link-actions"><label><input type="checkbox" data-profile-enabled ${link.enabled ? 'checked' : ''}> 在博客显示</label><div><button type="button" class="button" data-site-action="up" aria-label="上移此链接">上移</button><button type="button" class="button" data-site-action="down" aria-label="下移此链接">下移</button><button type="button" class="button" data-site-action="remove" aria-label="移除此链接">移除</button></div></div></fieldset>`;
}

function siteFields(record) {
  const options = state.images.filter(image => /\.(png|ico)$/i.test(image.path)).map(image => `<option value="${escapeHtml(image.path)}">${escapeHtml(image.path)}</option>`).join('');
  return `<section class="site-settings-section"><h3>网站小图标 / Favicon</h3><p class="muted">用于浏览器标签页与收藏夹。建议使用正方形的 32 × 32 或 64 × 64 图标，支持 2 MB 以内的 PNG、ICO。</p>${studioField('favicon', '图标路径（留空即移除）', record.favicon)}<div class="studio-field"><label for="site-icon-choice">从素材库选择</label><select id="site-icon-choice"><option value="">选择已上传的 PNG / ICO</option>${options}</select></div><div class="page-links"><button class="button" type="button" data-site-action="upload-icon">上传新图标</button><button class="button" type="button" data-site-action="default-icon">恢复默认图标</button><button class="button" type="button" data-site-action="clear-icon">移除图标</button></div><input id="site-icon-upload" type="file" accept="image/png,image/x-icon,image/vnd.microsoft.icon,.png,.ico" hidden><div id="site-icon-preview" class="site-icon-preview" aria-live="polite"></div><p class="muted">上传的素材会保留在本地素材库；点击保存后才会用于博客。发布时图片也会公开。</p></section><section class="site-settings-section"><h3>各平台个人主页</h3><p class="muted">按列表顺序展示，最多 20 个。仅接受 HTTPS 地址；可以暂时隐藏，无需删除。留空列表不会展示任何入口。</p><div id="site-link-rows">${record.links.map(siteLinkRow).join('')}</div><button class="button" type="button" data-site-action="add">＋ 添加个人主页</button></section>`;
}

function siteRecord(fields) {
  const links = [...select('#site-link-rows').querySelectorAll('.site-link-row')].map(row => {
    const label = row.querySelector('[data-profile-label]').value.trim();
    const url = row.querySelector('[data-profile-url]').value.trim();
    const enabled = row.querySelector('[data-profile-enabled]').checked;
    if (!label || label.length > 40) throw new Error('请填写 1–40 字的平台名称。');
    let parsed;
    try { parsed = new URL(url); } catch { throw new Error(`「${label}」的个人主页地址无效。`); }
    if (parsed.protocol !== 'https:' || !parsed.hostname || parsed.username || parsed.password || /[\s\\\u0000-\u001f]/.test(url)) throw new Error(`「${label}」需要无账号密码的 HTTPS 地址。`);
    return {label, url, enabled};
  });
  if (links.length > 20) throw new Error('最多添加 20 个个人主页链接。');
  return {favicon: fields.favicon.trim(), links};
}

function updateSiteIconPreview() {
  const path = select('#studio-favicon').value.trim();
  const url = imageUrl(path);
  select('#site-icon-preview').innerHTML = url ? `<div class="site-tab-preview"><img src="${escapeHtml(url)}" alt="16 像素图标预览" width="16" height="16"><span>Seven · 博客</span><span aria-hidden="true">×</span></div><img src="${escapeHtml(url)}" alt="32 像素图标预览" width="32" height="32">` : `<p class="muted">${path ? '请先选择或上传素材库中的图标。' : '不设置网站图标。'}</p>`;
}

async function uploadSiteIcon(file) {
  if (!file || studio.busy) return;
  if (!/\.(png|ico)$/i.test(file.name) || file.size > 2 * 1024 * 1024) throw new Error('请选择 2 MB 以内的 PNG 或 ICO 文件。');
  studio.busy = true;
  select('#studio-form').querySelectorAll('button,input,textarea,select').forEach(element => { element.disabled = true; });
  try {
    const data = await readImageFile(file);
    const result = await api('site/icon/upload', {name: file.name, data});
    const response = await api('state');
    state.images = response.images;
    select('#studio-favicon').value = result.path;
    const choice = select('#site-icon-choice');
    if (![...choice.options].some(option => option.value === result.path)) choice.add(new Option(result.path, result.path));
    choice.value = result.path;
    studio.dirty = true;
    studio.cloud = null;
    updateSiteIconPreview();
    toast('图标已上传；保存并生成后才会应用到博客。');
  } finally {
    studio.busy = false;
    select('#studio-form').querySelectorAll('button,input,textarea,select').forEach(element => { element.disabled = false; });
  }
}

function siteAction(button) {
  if (studio.kind !== 'site' || studio.busy) return;
  const action = button.dataset.siteAction;
  const rows = select('#site-link-rows');
  const row = button.closest('.site-link-row');
  if (action === 'upload-icon') return select('#site-icon-upload').click();
  if (action === 'add') {
    if (rows.children.length >= 20) throw new Error('最多添加 20 个个人主页链接。');
    rows.insertAdjacentHTML('beforeend', siteLinkRow());
    rows.lastElementChild.querySelector('input').focus();
  } else if (action === 'remove' && row) {
    if (!confirm('移除此个人主页链接？保存后才会生效。')) return;
    row.remove();
  } else if (action === 'up' && row?.previousElementSibling) {
    rows.insertBefore(row, row.previousElementSibling);
  } else if (action === 'down' && row?.nextElementSibling) {
    rows.insertBefore(row.nextElementSibling, row);
  } else if (action === 'default-icon' || action === 'clear-icon') {
    select('#studio-favicon').value = action === 'default-icon' ? '/img/favicon.ico' : '';
    select('#site-icon-choice').value = '';
    updateSiteIconPreview();
  }
  studio.dirty = true;
}

select('#studio-form').addEventListener('click', event => {
  const button = event.target.closest('[data-site-action]');
  if (button) safely(() => siteAction(button));
});
select('#studio-form').addEventListener('input', event => {
  if (studio.kind === 'site' && event.target.id === 'studio-favicon') updateSiteIconPreview();
});
select('#studio-form').addEventListener('change', event => {
  if (studio.kind !== 'site') return;
  if (event.target.id === 'site-icon-choice' && event.target.value) {
    select('#studio-favicon').value = event.target.value;
    updateSiteIconPreview();
  } else if (event.target.id === 'site-icon-upload') {
    const file = event.target.files[0];
    event.target.value = '';
    safely(() => uploadSiteIcon(file));
  }
});
