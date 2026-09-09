const appearanceColors = {
  transition_color: '切换动画颜色', primary_color: '主题强调色', hover_color: '按钮悬停色',
  light_background: '浅色模式背景', dark_background: '深色模式背景',
  light_card: '浅色模式卡片', dark_card: '深色模式卡片'
};
const appearanceNumbers = {
  card_radius: ['卡片圆角', 0, 32, 'px'], font_size: ['正文字号', 12, 22, 'px'],
  header_height: ['内页头图高度', 200, 600, 'px'], transition_duration: ['头图过渡时长（0 为关闭）', 0, 2000, 'ms']
};

function renderAppearance() {
  if (!state.appearance || state.needsRestart) return empty('请重启工作台服务', '关闭旧终端后重新双击 manage-blog.cmd，加载新版样式管理功能。');
  const record = state.appearance;
  return `<section class="panel guide-card"><p class="eyebrow">YOUR BLOG, YOUR PALETTE</p><h2>让博客有自己的颜色</h2><p>切换动画已设为 ${escapeHtml(record.transition_color)}。进入页面时彩色遮罩渐隐，以轻柔过渡融入雾青遮罩与背景图片；同步加载样式避免闪现旧颜色。</p><div class="appearance-swatches">${Object.entries(appearanceColors).map(([name, label]) => `<div><span style="background:${escapeHtml(record[name])}"></span><strong>${label}</strong><code>${escapeHtml(record[name])}</code></div>`).join('')}</div><p>${Object.entries(appearanceNumbers).map(([name, [label, , , unit]]) => `${label}：${record[name]} ${unit}`).join(' · ')}</p><div class="page-links"><button class="button primary" data-studio="edit-appearance">编辑样式与颜色</button><a class="button" href="/projects/" target="_blank" rel="noopener">预览博客 ↗</a></div><p>保存仅更新本地文件；确认效果后到「云端同步」发布。背景图经过降饱和与柔和遮罩处理；正文、导航、卡片与代码块会随明暗模式统一切换。</p></section>`;
}

function appearanceFields(record) {
  const colors = Object.entries(appearanceColors).map(([name, label]) => `<div class="studio-field"><label for="studio-${name}">${label}</label><div class="appearance-color-input"><input type="color" data-color-for="${name}" value="${escapeHtml(record[name])}" aria-label="${label}取色器"><input id="studio-${name}" name="${name}" value="${escapeHtml(record[name])}" pattern="#[0-9a-fA-F]{6}" maxlength="7" required title="请输入六位 HEX 颜色，例如 #39c5bb"></div></div>`).join('');
  const numbers = Object.entries(appearanceNumbers).map(([name, [label, minimum, maximum, unit]]) => `<div class="studio-field"><label for="studio-${name}">${label} / ${unit}</label><input type="number" id="studio-${name}" name="${name}" min="${minimum}" max="${maximum}" step="1" value="${record[name]}" required></div>`).join('');
  return `<p class="appearance-note">下方色块展示动画颜色；真实博客中的色块会渐隐。调整数值实时查看示意，恢复默认不会立即保存。</p><div class="appearance-controls">${colors}${numbers}</div><div class="appearance-preview-grid">${['light', 'dark'].map(mode => `<div class="appearance-preview" id="appearance-preview-${mode}"><div class="appearance-preview-header">${mode === 'light' ? '浅色模式' : '深色模式'} · 游戏作品</div><div class="appearance-preview-card"><h3>我的创作与记录</h3><p>用自己的颜色，记录每一次灵感。</p><span class="appearance-preview-button">查看作品 ↗</span></div></div>`).join('')}</div><button type="button" class="button" id="appearance-reset">恢复默认配色与样式</button>`;
}

function appearanceRecord(fields) {
  const record = {};
  for (const name of Object.keys(appearanceColors)) {
    if (!/^#[0-9a-fA-F]{6}$/.test(fields[name])) throw new Error('请填写六位 HEX 颜色，例如 #39c5bb。');
    record[name] = fields[name].toLowerCase();
  }
  for (const [name, [label, minimum, maximum]] of Object.entries(appearanceNumbers)) {
    const value = Number(fields[name]);
    if (fields[name] === '' || !Number.isInteger(value) || value < minimum || value > maximum) throw new Error(`${label}应为 ${minimum}–${maximum} 之间的整数。`);
    record[name] = value;
  }
  return record;
}

function updateAppearancePreview() {
  let record;
  try { record = appearanceRecord(Object.fromEntries(new FormData(select('#studio-form')).entries())); }
  catch { return; }
  for (const mode of ['light', 'dark']) {
    const preview = select(`#appearance-preview-${mode}`);
    preview.style.backgroundColor = record[`${mode}_background`];
    preview.style.color = mode === 'dark' ? '#d4e0d8' : '#3e514c';
    preview.style.fontSize = `${record.font_size}px`;
    const header = preview.querySelector('.appearance-preview-header');
    header.style.backgroundColor = record.transition_color;
    header.style.backgroundImage = 'linear-gradient(135deg, #1b413bc2, #243f37ad)';
    header.style.color = '#f4f8f4';
    header.style.height = `${record.header_height / 4}px`;
    header.style.transitionDuration = `${record.transition_duration}ms`;
    const card = preview.querySelector('.appearance-preview-card');
    card.style.backgroundColor = record[`${mode}_card`];
    card.style.borderRadius = `${record.card_radius}px`;
    preview.style.setProperty('--preview-primary', record.primary_color);
    preview.style.setProperty('--preview-hover', record.hover_color);
    preview.querySelector('.appearance-preview-button').style.color = '#fcfdf9';
  }
}

select('#studio-form').addEventListener('input', event => {
  if (studio.kind !== 'appearance') return;
  const name = event.target.dataset.colorFor;
  if (name) select(`#studio-${name}`).value = event.target.value;
  else if (event.target.name in appearanceColors && /^#[0-9a-fA-F]{6}$/.test(event.target.value)) {
    select(`[data-color-for="${event.target.name}"]`).value = event.target.value;
  }
  updateAppearancePreview();
});
select('#studio-form').addEventListener('click', event => {
  if (event.target.id !== 'appearance-reset' || studio.busy) return;
  if (!confirm('将编辑器中的样式恢复默认？仍需点击「保存并生成」才会生效。')) return;
  select('#studio-fields').innerHTML = appearanceFields(state.appearance_defaults);
  studio.dirty = true;
  updateAppearancePreview();
});
