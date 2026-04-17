/**
 * TicNote Renderer — 统一渲染引擎
 * 驾舱 (app.js) 和只读分享层 (share.html) 共用
 */
const TicNoteRenderer = (() => {

  // ── ASR/Speaker 配置（运行时通过 init(cfg) 注入，默认空）──
  // 业务规则（真实人名/内部术语）绝不硬编码；统一走 cockpit_config.json 三件套。
  let ASR_FIXES = [];              // [[RegExp, replacement], ...]
  let KNOWN_SPEAKER_MAPS = {};     // { filenameKey: { SPEAKER_XX: name } }
  let SPEAKER_HINTS = [];          // [[RegExp, name], ...]
  let JUNK_TITLE_PREFIX = '';      // 可选：TicNote 录音标题的品牌前缀（例："龙湖千丁"），从 cfg 注入

  function fixASR(text) {
    for (const [pat, rep] of ASR_FIXES) text = text.replace(pat, rep);
    return text;
  }

  // ── Speaker constants ──
  const SPEAKER_COLORS = ['#60a5fa','#f59e0b','#a78bfa','#34d399','#f472b6','#38bdf8','#ff9e7a','#e879f9'];

  // init(cfg): 接收 /api/cockpit/config 返回的结构，解析成运行时可用的 RegExp。
  // cfg 结构：
  //   ASR_FIXES:        [{pattern: '/re/', flags: 'g', replacement: 'X'}, ...]
  //   KNOWN_SPEAKER_MAPS: { key: {SPEAKER_XX: name}, ... }
  //   SPEAKER_HINTS:    [{pattern: '/re/', flags: '', replacement: 'X'}, ...]
  //
  // 容错：字段缺失时保持空数组/空对象，其余功能（渲染/分段/Icon）不受影响。
  function init(cfg) {
    if (!cfg || typeof cfg !== 'object') return;
    const toRe = (f) => {
      // pattern 可能为 "/x/" 带斜杠，也可能是裸 pattern
      let body = f.pattern || '';
      if (body.startsWith('/') && body.lastIndexOf('/') > 0) {
        const last = body.lastIndexOf('/');
        body = body.slice(1, last);
      }
      return new RegExp(body, f.flags || '');
    };
    // 逐条容错：某条 pattern 不是合法 JS regex（例如 Python inline flag `(?i)`）时
    // 跳过该条，不要让整个 init 崩掉——剩余规则仍可生效。
    const safeMap = (arr, flagsDefault) => {
      const out = [];
      for (const f of arr) {
        try { out.push([toRe({ ...f, flags: f.flags || flagsDefault }), f.replacement]); }
        catch (e) { if (typeof console !== 'undefined') console.warn('[ticnote-renderer] skip invalid regex:', f.pattern, e.message); }
      }
      return out;
    };
    if (Array.isArray(cfg.ASR_FIXES))    ASR_FIXES = safeMap(cfg.ASR_FIXES, 'g');
    if (Array.isArray(cfg.SPEAKER_HINTS)) SPEAKER_HINTS = safeMap(cfg.SPEAKER_HINTS, '');
    if (cfg.KNOWN_SPEAKER_MAPS && typeof cfg.KNOWN_SPEAKER_MAPS === 'object') {
      KNOWN_SPEAKER_MAPS = { ...cfg.KNOWN_SPEAKER_MAPS };
    }
    if (typeof cfg.JUNK_TITLE_PREFIX === 'string') {
      JUNK_TITLE_PREFIX = cfg.JUNK_TITLE_PREFIX;
    }
  }

  // ── Section icons ──
  const SECTION_ICONS = {
    '会议概述':'📋','核心要点':'🎯','巡检':'🔍','慧眼':'👁️','平台':'🖥️','Agent':'🤖',
    '研发':'🛠️','技能':'🧩','Skill':'🧩','共识':'🤝','未达成':'⚖️','行动':'📌',
    '引用':'🗣️','建议':'💡','亮点':'✨','讨论':'💬','催缴':'📞','资管':'📊',
    '酒店':'🏨','排布':'📐','空间':'🌐','商场':'🛍️','居住':'🏠','社区':'🏘️',
    '挑战':'⚠️','策略':'🎯','生态':'🌳','数据':'💾','安全':'🛡️','风控':'🛡️',
    '商业化':'💰','架构':'🏗️','模式':'📦','痛点':'🔥','竞争':'⚔️',
  };

  function iconForTitle(title) {
    for (const [k,v] of Object.entries(SECTION_ICONS)) {
      if (title.includes(k)) return v;
    }
    if (/^[\u{1F000}-\u{1FFFF}]/u.test(title)) return '';
    return '📄';
  }

  // ── Junk strip ──
  const JUNK_LINES = ['新功能','TicNote Cloud','编辑','总结','转录','思维导图','顿悟','深度研究','播客','1.0X','内容由 Shadow 生成','Shadow 2.0'];

  function stripJunk(text) {
    const lines = text.split('\n');
    const clean = [];
    let seenContent = false;
    for (const line of lines) {
      const t = line.trim();
      if (!seenContent) {
        if (!t) continue;
        if (JUNK_LINES.some(j => t.includes(j))) continue;
        if (/^\d+:\d+$/.test(t)) continue;
        if (t === '/') continue;
        if (/^\d{4}年\d{2}月\d{2}日/.test(t) && !t.includes('|')) continue;
        if (JUNK_TITLE_PREFIX && t.startsWith(JUNK_TITLE_PREFIX)) continue;
        if (/\.m4a$|\.record$/.test(t)) continue;
        if (/^\d{4}-\d{2}-\d{2}\s[\d:]+\|/.test(t)) { clean.push(t); seenContent = true; continue; }
        if (t.startsWith('出席人员')) { clean.push(t); seenContent = true; continue; }
        if (t.length < 20 && !t.startsWith('#') && !t.startsWith('📋') && !t.startsWith('🎯')) { continue; }
        seenContent = true;
      }
      if (t === '内容由 Shadow 生成，仅供参考') break;
      clean.push(line);
    }
    return clean.join('\n');
  }

  // ── Parsing ──
  function parseSummarySections(text) {
    const sections = [];
    const lines = text.split('\n');
    let current = null;
    const emojiHeadRe = /^([\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}]+)\s*(.+)$/u;

    for (const line of lines) {
      const t = line.trim();
      if (!t) { if (current) current.body += '\n'; continue; }
      const em = t.match(emojiHeadRe);
      if (em && t.length < 80) {
        if (current) sections.push(current);
        current = { icon: em[1], title: em[2].replace(/^#+\s*/, ''), body: '' };
        continue;
      }
      if (t.endsWith('：') && t.length < 50 && !t.startsWith('>') && !t.startsWith('-')) {
        if (current) { current.body += '\n**' + t + '**\n'; continue; }
      }
      if (current) {
        current.body += line + '\n';
      } else {
        current = { icon: '📋', title: '概述', body: line + '\n' };
      }
    }
    if (current) sections.push(current);
    return sections.filter(s => s.body.trim()).map(s => ({
      ...s, icon: s.icon || iconForTitle(s.title), body: s.body.trim()
    }));
  }

  function parseTranscriptBlocks(text) {
    const blocks = [];
    const lines = text.split('\n');
    let i = 0;
    while (i < lines.length) {
      const t = lines[i].trim();
      if (/^SPEAKER_\d+$/.test(t) || /^说话人\d+$/.test(t)) break;
      i++;
    }
    let currentSpeaker = '', currentTime = '', currentText = [];
    while (i < lines.length) {
      const t = lines[i].trim();
      if (/^(?:SPEAKER_\d+|说话人\d+)$/.test(t)) {
        if (currentSpeaker && currentText.length) {
          blocks.push({ speaker: currentSpeaker, time: currentTime, text: fixASR(currentText.join(' ').trim()) });
        }
        currentSpeaker = t; currentText = []; currentTime = '';
        i++;
        if (i < lines.length && lines[i].trim() === '|') i++;
        if (i < lines.length && /^\d{1,3}:\d{2}(:\d{2})?$/.test(lines[i].trim())) { currentTime = lines[i].trim(); i++; }
        continue;
      }
      if (t === '|') { i++; continue; }
      if (t === '内容由 Shadow 生成，仅供参考' || t === '内容由 Shadow 生成') break;
      if (t) currentText.push(t);
      i++;
    }
    if (currentSpeaker && currentText.length) {
      blocks.push({ speaker: currentSpeaker, time: currentTime, text: fixASR(currentText.join(' ').trim()) });
    }
    const merged = [];
    for (const b of blocks) {
      if (merged.length && merged[merged.length-1].speaker === b.speaker && b.text.length < 10) {
        merged[merged.length-1].text += ' ' + b.text;
      } else {
        merged.push({...b});
      }
    }
    return merged;
  }

  function inferSpeakers(blocks, filename) {
    const blockSpeakers = [...new Set(blocks.map(b => b.speaker))];
    for (const [key, map] of Object.entries(KNOWN_SPEAKER_MAPS)) {
      if (filename.includes(key)) {
        const result = { ...map };
        for (const sp of blockSpeakers) { if (!(sp in result)) result[sp] = sp; }
        return result;
      }
    }
    const map = {};
    const scores = {};
    for (const sp of blockSpeakers) {
      scores[sp] = {};
      const allText = blocks.filter(b => b.speaker === sp).map(b => b.text).join(' ');
      for (const [pat, name] of SPEAKER_HINTS) {
        const matches = (allText.match(new RegExp(pat.source, 'g')) || []).length;
        if (matches > 0) scores[sp][name] = (scores[sp][name] || 0) + matches;
      }
    }
    const assigned = new Set();
    const entries = [];
    for (const sp of blockSpeakers) {
      for (const [name, score] of Object.entries(scores[sp] || {})) { entries.push({ sp, name, score }); }
    }
    entries.sort((a, b) => b.score - a.score);
    for (const { sp, name, score } of entries) {
      if (map[sp] || assigned.has(name)) continue;
      if (score >= 2) { map[sp] = name; assigned.add(name); }
    }
    for (const sp of blockSpeakers) {
      if (!map[sp]) {
        const total = blocks.filter(b => b.speaker === sp).reduce((s, b) => s + b.text.length, 0);
        map[sp] = total < 50 ? '（旁听）' : sp;
      }
    }
    return map;
  }

  function applySpeakerMap(blocks, map) {
    return blocks.map(b => ({
      ...b, speakerRaw: b.speakerRaw || b.speaker,
      speaker: map[b.speakerRaw || b.speaker] || map[b.speaker] || b.speaker,
    }));
  }

  function generateInsights(meta, sections, blocks) {
    const insights = { overview: '', keySignals: [], actionItems: [], consensus: [], risks: [], speakerStats: [] };
    const topicCount = sections.length;
    const blockCount = blocks.length;
    const speakers = [...new Set(blocks.map(b => b.speaker))];
    const duration = meta.duration || '未知';
    insights.overview = `本次会议时长 ${duration}，共 ${speakers.length} 位参与者，讨论涵盖 ${topicCount} 个议题。转录共 ${blockCount} 段发言。`;
    const speakerWords = {};
    for (const b of blocks) { speakerWords[b.speaker] = (speakerWords[b.speaker]||0) + b.text.length; }
    const totalWords = Object.values(speakerWords).reduce((a,b)=>a+b,0) || 1;
    insights.speakerStats = Object.entries(speakerWords)
      .sort((a,b) => b[1]-a[1])
      .map(([speaker,words]) => {
        const rawKey = blocks.find(b => b.speaker === speaker)?.speakerRaw || speaker;
        const idx = parseInt(rawKey.replace(/\D/g, '')) || 0;
        return { speaker, speakerRaw: rawKey, words, pct: Math.round(words/totalWords*100), color: SPEAKER_COLORS[idx % SPEAKER_COLORS.length] };
      });
    for (const s of sections) {
      if (/共识|一致|确定|明确/.test(s.title)) {
        insights.consensus.push({ icon: '🤝', text: s.body.split('\n').filter(l=>l.trim()).slice(0,5).join('\n') });
      }
      if (/未达成|分歧|风险|挑战/.test(s.title)) {
        insights.risks.push({ icon: '⚠️', text: s.body.split('\n').filter(l=>l.trim()).slice(0,5).join('\n') });
      }
      if (/行动|后续|下一步/.test(s.title)) {
        s.body.split('\n').filter(l => l.trim().startsWith('') || /^\d+[\.\、]/.test(l.trim()) || l.trim().startsWith('-')).forEach(l => {
          insights.actionItems.push(l.trim().replace(/^[\s\d\.\、\-]+/, '').trim());
        });
      }
    }
    for (const s of sections.slice(0, 8)) {
      if (/概述|引用|建议|AI建议/.test(s.title)) continue;
      const firstLine = s.body.split('\n').find(l => l.trim() && l.trim().length > 20);
      if (firstLine) insights.keySignals.push({ title: s.title, icon: s.icon, text: firstLine.trim().substring(0, 120) });
    }
    return insights;
  }

  // ── Full document processing pipeline ──
  function processDocument(raw, filename) {
    const parts = raw.split(/^## /m);
    let rawSummary = '', rawTranscript = '';
    const meta = {};
    const header = parts[0] || '';
    const urlM = header.match(/URL:\s*(https?:\/\/\S+)/);
    if (urlM) meta.url = urlM[1];

    // Parse frontmatter
    const lines = raw.split('\n');
    if (lines[0] && lines[0].trim() === '---') {
      for (let li = 1; li < lines.length; li++) {
        if (lines[li].trim() === '---') break;
        const m = lines[li].match(/^(\w+):\s*(.+)$/);
        if (m) meta[m[1]] = m[2].trim();
      }
    }

    for (let i = 1; i < parts.length; i++) {
      const nl = parts[i].indexOf('\n');
      const name = parts[i].substring(0, nl).trim();
      const body = parts[i].substring(nl + 1).trim();
      if (name === '总结') rawSummary = body;
      else if (name === '转录') rawTranscript = body;
    }

    for (const line of rawSummary.split('\n').slice(0, 40)) {
      const m = line.match(/^(\d{4}-\d{2}-\d{2}\s[\d:]+)\|(.+?)\|(.+)$/);
      if (m) { meta.date = m[1]; meta.duration = m[2].trim(); meta.author = m[3].trim(); break; }
    }

    const cleanSummary = fixASR(stripJunk(rawSummary));
    const sumSections = parseSummarySections(cleanSummary);
    const rawTransBlocks = parseTranscriptBlocks(rawTranscript);
    const speakerMap = inferSpeakers(rawTransBlocks, filename || '');
    const transBlocks = applySpeakerMap(rawTransBlocks, speakerMap);
    const insights = generateInsights(meta, sumSections, transBlocks);

    return { meta, sumSections, transBlocks, insights, speakerMap };
  }

  // ── Render markdown (requires marked.js loaded) ──
  function renderMd(s) {
    if (!s) return '';
    if (typeof marked !== 'undefined') {
      return marked.parse(s, { gfm: true, breaks: true });
    }
    return s.replace(/\n/g, '<br>');
  }

  return {
    SPEAKER_COLORS,
    get KNOWN_SPEAKER_MAPS() { return KNOWN_SPEAKER_MAPS; },
    get ASR_FIXES() { return ASR_FIXES; },
    get SPEAKER_HINTS() { return SPEAKER_HINTS; },
    init,
    fixASR,
    stripJunk,
    parseSummarySections,
    parseTranscriptBlocks,
    inferSpeakers,
    applySpeakerMap,
    generateInsights,
    processDocument,
    renderMd,
    iconForTitle,
  };
})();

if (typeof module !== 'undefined') module.exports = TicNoteRenderer;
