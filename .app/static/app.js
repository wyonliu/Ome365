const { createApp, ref, reactive, computed, onMounted, nextTick, watch } = Vue;

const app = createApp({
  setup() {
    const view = ref('dashboard');
    const dash = ref(null);
    const todayData = ref(null);
    const weekData = ref(null);
    const planData = ref(null);
    const decisions = ref([]);
    const notes = ref([]);
    const fileTree = ref([]);
    const interviewGroups = ref([]);
    const interviewCount = computed(() => interviewGroups.value.reduce((s,g) => s + g.count, 0));
    const interviewCatFilter = ref('全部');
    const selectedInterview = ref(null);
    const interviewContent = ref('');
    // Hiring (面试)
    const hiringList = ref([]);
    const selectedCandidate = ref(null);
    const candidateData = ref(null);
    const candidateTab = ref('resume');
    const candidateRoundSubTab = ref('focus');
    const candidateTranscript = ref('');
    const candidateTransBlocks = ref([]);
    const candidateSumSections = ref([]);
    const candidateSpeakerMap = ref({});
    const reportsList = ref([]);
    const selectedReport = ref(null);
    const reportContent = ref('');
    const reportEditing = ref(false);
    const reportEditText = ref('');
    const tocMode = ref('full'); // 'full' | 'slim' | 'hidden'
    function cycleTocMode() {
      const order = ['full', 'slim', 'hidden'];
      tocMode.value = order[(order.indexOf(tocMode.value) + 1) % order.length];
    }
    const activeReportSection = ref('01-diagnosis');
    // Drill-down state: when set, show person-level detail (L2) instead of section gallery (L1)
    // shape: { sectionKey, entityKey, personKey, personLabel }
    const reportDrillPerson = ref(null);
    // Section-based taxonomy: mirrors reports/ folder layout, each section has optional entity sub-groups
    // tier: 'primary' | 'secondary' | 'tertiary' | 'personal' | 'archive'
    const SECTION_TAXONOMY = reactive([]);  // loaded at init from /api/cockpit/config
    function getReportEntityKey(r) {
      // Prefer server-provided entity field (folder-derived); fallback to path parse
      if (r.entity) return r.entity;
      const parts = (r.path || '').split('/');
      const ri = parts.indexOf('reports');
      if (ri < 0) return '';
      if (parts.length <= ri + 3) return ''; // flat file at section root
      return parts[ri + 2] || '';
    }
    // Map person keys → org-oriented display labels for cockpit cards
    // Keys come from filename prefix before first · (e.g. "<org>-<team>-<person>")
    const PERSON_DISPLAY_MAP = reactive({});  // loaded at init from /api/cockpit/config
    function getReportPersonKey(r) {
      // Server now provides `person` field; fallback to eyebrow / name
      let raw = (r.person && r.person.trim()) || (r.eyebrow || '').split('·').pop().trim() || (r.name || '').split('·')[0] || '';
      // Normalize: strip parenthetical suffix —(小林总) → —
      raw = raw.replace(/[(（][^)）]*[)）]\s*$/g, '').trim();
      // Strip leading 航道码 "N2 —" / "C3 —" → — / —
      raw = raw.replace(/^[CN]\d[·・\-\s]+/, '').trim();
      // Strip role suffix after dash if before matches pure chinese name
      // e.g. "—-CHO" → "—" (already done earlier), keep simple
      return raw;
    }
    function getPersonDisplayLabel(personKey) {
      return PERSON_DISPLAY_MAP[personKey] || personKey;
    }
    function isMasterDoc(r) {
      const nm = (r.name || '');
      // 00·xxx 总报告 (dot/middle-dot/space-separated) — section master entry
      return /^00[·∙•・\s-]/.test(nm);
    }
    const PRIO_RANK = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3, '': 4 };
    function sortReports(a, b) {
      const pa = PRIO_RANK[a.priority || ''] ?? 4;
      const pb = PRIO_RANK[b.priority || ''] ?? 4;
      if (pa !== pb) return pa - pb;
      // Same priority: sort by eyebrow (Track 2 < Track 3A < Track 3B)
      const ea = a.eyebrow || '', eb = b.eyebrow || '';
      if (ea && eb && ea !== eb) return ea.localeCompare(eb);
      return (b.mtime || 0) - (a.mtime || 0);
    }
    const reportsBySection = computed(() => {
      // Build section groups from taxonomy with masters / entity sub-groups / flat items
      // Each entity sub-group additionally groups its items by PERSON (for L2 drill-down)
      const groups = SECTION_TAXONOMY.map(sec => ({
        ...sec,
        masters: [],
        subGroupMap: {},
        flat: [],
        count: 0,
      }));
      const byKey = {};
      groups.forEach(g => { byKey[g.key] = g; });
      reportsList.value.forEach(r => {
        const secKey = r.section || '其他';
        const g = byKey[secKey];
        if (!g) return;
        if (isMasterDoc(r)) {
          g.masters.push(r);
          return;
        }
        if (g.entities && g.entities.length) {
          const entKey = getReportEntityKey(r);
          const ent = g.entities.find(e => e.key === entKey);
          if (ent) {
            if (!g.subGroupMap[entKey]) {
              g.subGroupMap[entKey] = { ...ent, items: [], personMap: {} };
            }
            g.subGroupMap[entKey].items.push(r);
            const pk = getReportPersonKey(r) || '·';
            if (!g.subGroupMap[entKey].personMap[pk]) {
              g.subGroupMap[entKey].personMap[pk] = { key: pk, label: getPersonDisplayLabel(pk), items: [] };
            }
            g.subGroupMap[entKey].personMap[pk].items.push(r);
            return;
          }
        }
        g.flat.push(r);
      });
      groups.forEach(g => {
        g.masters.sort(sortReports);
        g.flat.sort(sortReports);
        g.subGroups = (g.entities || [])
          .map(e => g.subGroupMap[e.key])
          .filter(Boolean);
        g.subGroups.forEach(sg => {
          sg.items.sort(sortReports);
          // Build persons array ordered by best priority of their docs
          sg.persons = Object.values(sg.personMap).map(pg => {
            pg.items.sort(sortReports);
            // best priority of the group for sorting
            const bestPrio = Math.min(...pg.items.map(it => PRIO_RANK[it.priority || ''] ?? 4));
            const latestMtime = Math.max(...pg.items.map(it => it.mtime || 0));
            return { ...pg, bestPrio, latestMtime };
          }).sort((a, b) => {
            if (a.bestPrio !== b.bestPrio) return a.bestPrio - b.bestPrio;
            return b.latestMtime - a.latestMtime;
          });
        });
        g.count = g.masters.length + g.flat.length +
          g.subGroups.reduce((s, sg) => s + sg.items.length, 0);
      });
      return groups;
    });
    // Primary tier (内部诊断 + 外部研究) — always top
    const primarySections = computed(() =>
      visibleReportSections.value.filter(s => s.tier === 'primary')
    );
    const secondarySections = computed(() =>
      visibleReportSections.value.filter(s => s.tier === 'secondary')
    );
    const tertiarySections = computed(() =>
      visibleReportSections.value.filter(s => s.tier === 'tertiary' || s.tier === 'personal' || s.tier === 'archive')
    );
    // Drill-down: when reportDrillPerson is set, compute the person's doc bundle
    const currentDrillPerson = computed(() => {
      const d = reportDrillPerson.value;
      if (!d) return null;
      const sec = currentReportSection.value;
      if (!sec) return null;
      const sg = sec.subGroups.find(s => s.key === d.entityKey);
      if (!sg) return null;
      const p = (sg.persons || []).find(pp => pp.key === d.personKey);
      if (!p) return null;
      return {
        section: sec,
        entity: sg,
        person: p,
        breadcrumb: [
          { key: '__home', label: '驾舱', type: 'home' },
          { key: sec.key, label: sec.label, type: 'section' },
          { key: sg.key, label: sg.label, type: 'entity' },
          { key: p.key, label: p.label, type: 'person' },
        ]
      };
    });
    // Breadcrumb for doc-level (when selectedReport is set)
    const currentDocBreadcrumb = computed(() => {
      const r = selectedReport.value;
      if (!r) return [];
      const secKey = r.section || '';
      const sec = SECTION_TAXONOMY.find(s => s.key === secKey);
      if (!sec) return [{ key: '__home', label: '驾舱', type: 'home' }];
      const crumbs = [
        { key: '__home', label: '驾舱', type: 'home' },
        { key: sec.key, label: sec.label, type: 'section' },
      ];
      const entKey = getReportEntityKey(r);
      const ent = (sec.entities || []).find(e => e.key === entKey);
      if (ent) {
        crumbs.push({ key: ent.key, label: ent.label, type: 'entity' });
        const pk = getReportPersonKey(r);
        if (pk && pk !== '·') {
          crumbs.push({ key: pk, label: pk, type: 'person' });
        }
      }
      crumbs.push({ key: r.path, label: r.title || r.name, type: 'doc', isCurrent: true });
      return crumbs;
    });
    function navigateToBreadcrumb(crumb) {
      if (!crumb) return;
      if (crumb.type === 'home') {
        selectedReport.value = null;
        reportDrillPerson.value = null;
        return;
      }
      if (crumb.type === 'section') {
        activeReportSection.value = crumb.key;
        selectedReport.value = null;
        reportDrillPerson.value = null;
        return;
      }
      if (crumb.type === 'entity') {
        selectedReport.value = null;
        reportDrillPerson.value = null;
        // Scroll to entity anchor could be added later
        return;
      }
      if (crumb.type === 'person') {
        // Find the section/entity for this person and drill in
        const sec = currentReportSection.value;
        if (!sec) return;
        for (const sg of sec.subGroups) {
          const p = (sg.persons || []).find(pp => pp.key === crumb.key);
          if (p) {
            selectedReport.value = null;
            reportDrillPerson.value = { sectionKey: sec.key, entityKey: sg.key, personKey: p.key, personLabel: p.label };
            return;
          }
        }
      }
    }
    function openPersonDrill(sec, sg, p) {
      reportDrillPerson.value = { sectionKey: sec.key, entityKey: sg.key, personKey: p.key, personLabel: p.label };
      selectedReport.value = null;
    }
    function clearPersonDrill() {
      reportDrillPerson.value = null;
    }
    const visibleReportSections = computed(() =>
      reportsBySection.value.filter(g => g.count > 0)
    );
    const currentReportSection = computed(() => {
      const secs = visibleReportSections.value;
      if (!secs.length) return null;
      return secs.find(s => s.key === activeReportSection.value) || secs[0];
    });
    // Auto-switch when selected section becomes empty
    watch(visibleReportSections, (secs) => {
      if (!secs.length) return;
      if (!secs.find(s => s.key === activeReportSection.value)) {
        activeReportSection.value = secs[0].key;
      }
    });
    // ── Reports browser: grouping + search ──
    const reportsGroupBy = ref('section'); // 'section' | 'date' | 'type'
    const reportsSearch = ref('');
    const reportsExpandedGroups = reactive(new Set());
    function toggleReportsGroup(key) {
      if (reportsExpandedGroups.has(key)) reportsExpandedGroups.delete(key);
      else reportsExpandedGroups.add(key);
    }
    // Flat list of all reports with metadata
    const reportsFlatAll = computed(() => {
      const all = [];
      for (const sec of reportsBySection.value) {
        for (const m of (sec.masters || [])) {
          all.push({ ...m, _secKey: sec.key, _secLabel: sec.label, _secIcon: sec.icon, _entityLabel: '总纲', _type: 'master' });
        }
        for (const sg of (sec.subGroups || [])) {
          for (const item of sg.items) {
            all.push({ ...item, _secKey: sec.key, _secLabel: sec.label, _secIcon: sec.icon, _entityLabel: sg.label, _type: 'entity' });
          }
        }
        for (const f of (sec.flat || [])) {
          all.push({ ...f, _secKey: sec.key, _secLabel: sec.label, _secIcon: sec.icon, _entityLabel: '', _type: 'flat' });
        }
      }
      return all;
    });
    // Filtered + grouped
    const reportsFiltered = computed(() => {
      const q = (reportsSearch.value || '').trim().toLowerCase();
      if (!q) return reportsFlatAll.value;
      return reportsFlatAll.value.filter(r => {
        const haystack = [r.title, r.subtitle, r._secLabel, r._entityLabel, ...(r.tags || [])].join(' ').toLowerCase();
        return q.split(/\s+/).every(w => haystack.includes(w));
      });
    });
    const reportsGrouped = computed(() => {
      const items = reportsFiltered.value;
      const mode = reportsGroupBy.value;
      const map = new Map();
      for (const r of items) {
        let gKey, gLabel, gIcon;
        if (mode === 'section') {
          gKey = r._secKey; gLabel = r._secLabel; gIcon = r._secIcon;
        } else if (mode === 'date') {
          const d = r.date || '';
          if (d >= new Date().toISOString().slice(0,10)) { gKey = '今日'; gLabel = '今日'; gIcon = '📅'; }
          else {
            const daysAgo = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
            if (daysAgo <= 7) { gKey = '本周'; gLabel = '本周'; gIcon = '🗓️'; }
            else if (daysAgo <= 14) { gKey = '上周'; gLabel = '上周'; gIcon = '📆'; }
            else if (daysAgo <= 30) { gKey = '本月'; gLabel = '本月'; gIcon = '📋'; }
            else { gKey = '更早'; gLabel = '更早'; gIcon = '🗃️'; }
          }
        } else {
          gKey = r._entityLabel || r._secLabel; gLabel = r._entityLabel || r._secLabel; gIcon = r._secIcon;
        }
        if (!map.has(gKey)) map.set(gKey, { key: gKey, label: gLabel, icon: gIcon, items: [] });
        map.get(gKey).items.push(r);
      }
      return Array.from(map.values());
    });
    // Reset expanded groups when groupBy or search changes; auto-expand first group
    watch([reportsGroupBy, reportsSearch], () => {
      reportsExpandedGroups.clear();
    });
    watch(reportsGrouped, (groups) => {
      if (groups.length && reportsExpandedGroups.size === 0) {
        reportsExpandedGroups.add(groups[0].key);
      }
    }, { immediate: true });

    const interviewTab = ref('summary');
    const interviewSummary = ref('');
    const interviewTranscript = ref('');
    const interviewMeta = ref({});
    const interviewSummarySections = ref([]);
    const interviewTranscriptBlocks = ref([]);
    const interviewInsights = ref({});
    const interviewSpeakers = ref([]);
    const interviewSpeakerMap = ref({});  // { SPEAKER_00: '—', ... } — editable
    const interviewTags = ref([]);
    const shareToast = ref('');
    const shareDialog = reactive({ show: false, slug: '', user: 'wyon', docTitle: '', docPath: '', available: false, conflict: false, conflictTitle: '', url: '', copied: false, autoSlug: true, existing: false, pos: {}, message: '' });
    const currentFile = ref(null);
    const currentFilePath = ref('');
    const noteText = ref('');
    const noteSuccess = ref(false);
    const noteTime = ref('');
    const sidebarCollapsed = ref(localStorage.getItem('ome365_sidebar')==='1');
    const mobileNavOpen = ref(false);
    const editingToday = ref(false);
    const todayEditRaw = ref('');
    const showDecisionForm = ref(false);
    const newDecision = ref({title:'',scope:'架构',impact:'中',background:''});
    const isMac = ref(navigator.platform.includes('Mac'));
    const heatmapData = ref(null);
    const planQuarter = ref(1);
    const msFilter = ref('all'); // all | week | important | past

    // Loading
    const loading = ref(true);

    // Task add
    const newTodayTask = ref('');
    const newWeekTask = ref('');
    const addingTodayTask = ref(false);
    const addingWeekTask = ref(false);
    const newTaskCategory = ref('');
    const newTaskTime = ref('');
    const newTaskTimeEnd = ref('');
    const newTaskTimeRange = ref(false);
    const newTaskRepeat = ref('none');
    const newTaskTargetDate = ref(''); // YYYY-MM-DD for week task day selection

    // Unified tasks view
    const tasksTab = ref('today'); // today|tomorrow|week|month|days
    const unifiedTasksData = ref(null);

    // Reminders
    const reminders = ref([]); // custom + auto merged
    const showReminderForm = ref(false);
    const newReminder = ref({time:'', title:''});

    // Task editing
    const editingTask = ref(null); // {text, description, type:'today'|'week'}
    const editTaskText = ref('');
    const editTaskDesc = ref('');
    const editTaskTime = ref('');
    const editTaskTimeEnd = ref('');
    const editTaskTimeRange = ref(false);

    // Time blocks
    const timeBlocks = ref([]);
    const showTimeBlockForm = ref(false);
    const editingBlockIdx = ref(-1);
    const blockForm = ref({time:'', item:'', dim:''});

    // Categories
    const categories = ref([]);
    const noteCategory = ref('');
    const noteCategoryFilter = ref('all');
    const showCategoryForm = ref(false);
    const newCategory = ref({name:'',color:'#888',icon:'📌'});

    // Decision detail (legacy, still used by backend)
    const decisionDetail = ref(null);

    // ═══ Insights (洞察 · flagship) ═══
    const insightsOverview = ref(null);
    const insightsTab = ref('synthesis'); // synthesis | projects | diagnosis | ask | saved
    const insightsDays = ref(90);
    const insightsFocus = ref('');
    const insightsLatest = ref(null);
    const insightsCards = ref([]);
    const insightsLoading = ref(false);
    const insightsError = ref('');
    const insightsAskQ = ref('');
    const insightsAskReply = ref(null);
    const insightsAskLoading = ref(false);
    const insightsAskHistory = ref([]);

    // ═══ Life (生活 · 家庭 / 健康 / 仪式 / 时刻) ═══
    const lifeOverview = ref(null);
    const lifeTab = ref('daughter'); // daughter | health | rituals | moments
    const lifeLoading = ref(false);
    const lifeEditDaughter = ref(false);
    const lifeDaughterEdit = ref({name:'', birth_date:'', college_age:18});
    const lifeNewWeekend = ref({date:'', title:'', theme:'', activities:'', notes:''});
    const lifeShowWeekendForm = ref(false);
    const lifeIdeasLoading = ref(false);
    const lifeIdeasVibe = ref('');
    const lifeHealthDraft = ref({sleep:0, exercise:0, meditate:0, diet:0});
    const lifeHealthNote = ref('');
    const lifeNewRitual = ref({slot:'morning', text:''});
    const lifeNewMoment = ref({category:'高光', text:''});
    const lifeShowMomentForm = ref(false);

    // ═══ Cockpit (strategy dashboard) ═══
    const cockpitData = ref(null);
    const cockpitLoading = ref(false);
    const cockpitError = ref('');
    const cockpitActiveSection = ref(''); // for scrollspy / nav highlight
    const expandedTrack = ref('track1'); // default expand first track
    // ── Cockpit in-page navigation state (W4.2 · replaces drawer) ──
    // Block selection drives the bloom area beneath the nav tiles. All drill-down
    // happens in-page (no overlay/drawer), mirroring reports-view's pattern.
    const cockpitActiveBlockKey = ref('');          // '01-diagnosis' | '02-research' | ... | ''
    const cockpitDrillPerson = ref(null);           // { entityKey, personKey, personLabel } | null
    const cockpitOpenReport = ref(null);            // selected report doc (in-page reader) | null
    const cockpitBloomLoading = ref(false);         // loading master doc for bloom sections
    const forecastSelectedTrack = ref(null);        // clicked track key in forecast chart, e.g. 't1'
    function toggleForecastTrack(trackKey) {
      forecastSelectedTrack.value = forecastSelectedTrack.value === trackKey ? null : trackKey;
    }
    async function cockpitSelectBlock(key, opts={}) {
      // Toggle off if already active
      if (cockpitActiveBlockKey.value === key && !opts.skipNav) {
        cockpitActiveBlockKey.value = '';
        cockpitDrillPerson.value = null;
        cockpitOpenReport.value = null;
        if(!opts.skipNav) pushNav({view:'cockpit'});
        return;
      }
      cockpitActiveBlockKey.value = key;
      cockpitDrillPerson.value = null;
      cockpitOpenReport.value = null;
      if(!opts.skipNav) pushNav({view:'cockpit', detail:'block:'+key});
      // For bloom-flagged sections (A4S / 北极星), preload the master doc
      // content so we can parse it into chapter tiles.
      const sec = (reportsBySection.value || []).find(s => s.key === key);
      if (sec && sec.bloom && (sec.masters || []).length) {
        const master = sec.masters[0];
        cockpitBloomLoading.value = true;
        try {
          const res = await api('/reports/file?path=' + encodeURIComponent(master.path));
          // Temporarily stash master doc in reportContent so reportParsed computes
          // chapter structure. We do NOT set selectedReport/cockpitOpenReport, so
          // the reader does not open — only chapter tiles render.
          reportContent.value = res?.raw || '';
          selectedReport.value = master; // needed for reportParsed title fallback
        } catch (e) {
          console.error('load bloom master', e);
        } finally {
          cockpitBloomLoading.value = false;
        }
      } else {
        reportContent.value = '';
        selectedReport.value = null;
      }
      // Flagship sections: show finale visualization as area controller, no auto-open
      nextTick(() => {
        const el = document.querySelector('.cp-bloom, .rv-sec-content.cp-bloom');
        if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
    function cockpitGoHome(opts={}) {
      cockpitActiveBlockKey.value = '';
      cockpitDrillPerson.value = null;
      cockpitOpenReport.value = null;
      selectedReport.value = null;
      reportContent.value = '';
      if(!opts.skipNav) pushNav({view:'cockpit'});
    }
    function cockpitDrillTo(sg, p) {
      cockpitDrillPerson.value = { entityKey: sg.key, personKey: p.key, personLabel: p.label };
      cockpitOpenReport.value = null;
    }
    function cockpitClearDrill() {
      cockpitDrillPerson.value = null;
    }
    async function cockpitOpenDoc(r, opts={}) {
      if (!r) return;
      cockpitOpenReport.value = r;
      selectedReport.value = r;
      reportEditing.value = false;
      if(!opts.skipNav) pushNav({view:'cockpit', detail:'doc:'+shortId(r.path), _path:r.path});
      try {
        const res = await api('/reports/file?path=' + encodeURIComponent(r.path));
        reportContent.value = res?.raw || '';
      } catch (e) { console.error('load report', e); }
      nextTick(() => { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    }
    function cockpitCloseReport(opts={}) {
      cockpitOpenReport.value = null;
      // Push nav back to block level (or cockpit home)
      if(!opts.skipNav) {
        if(cockpitActiveBlockKey.value) pushNav({view:'cockpit', detail:'block:'+cockpitActiveBlockKey.value});
        else pushNav({view:'cockpit'});
      }
      // If we are inside a bloom section, reload the bloom master doc content
      // so chapter tiles render again.
      const sec = cockpitActiveBlockData.value;
      if (sec && sec.bloom && (sec.masters || []).length) {
        cockpitSelectBlockReload(sec.key);
      } else {
        selectedReport.value = null;
        reportContent.value = '';
      }
      nextTick(() => { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    }
    async function cockpitSelectBlockReload(key) {
      const sec = (reportsBySection.value || []).find(s => s.key === key);
      if (!sec || !sec.bloom || !(sec.masters || []).length) return;
      const master = sec.masters[0];
      try {
        const res = await api('/reports/file?path=' + encodeURIComponent(master.path));
        reportContent.value = res?.raw || '';
        selectedReport.value = master;
      } catch (e) { console.error('reload bloom', e); }
    }
    async function cockpitOpenChapter(ch) {
      // The master doc is already in reportContent (loaded by cockpitSelectBlock).
      // We just need to set cockpitOpenReport and scroll to the anchor after render.
      const sec = cockpitActiveBlockData.value;
      if (!sec || !(sec.masters || []).length) return;
      const master = sec.masters[0];
      cockpitOpenReport.value = master;
      selectedReport.value = master;
      reportEditing.value = false;
      nextTick(() => {
        // Small delay to let reportParsed render sections
        setTimeout(() => {
          const el = document.getElementById(ch.id);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          else window.scrollTo({ top: 0, behavior: 'smooth' });
        }, 120);
      });
    }
    // All block groups (primary/secondary/tertiary) from reportsBySection
    const cockpitBlocks = computed(() => {
      const all = reportsBySection.value || [];
      const order = ['01-diagnosis','02-research','03-a4s','04-longscale','05-metrics','04-trident','99-roadmap','99-archive','00-personal'];
      const wanted = new Set(['01-diagnosis','02-research','03-a4s','04-longscale','04-trident','05-metrics']);
      return order
        .filter(k => wanted.has(k))
        .map(k => all.find(s => s.key === k))
        .filter(Boolean);
    });
    const cockpitPrimaryBlocks = computed(() =>
      cockpitBlocks.value.filter(b => b.tier === 'primary')
    );
    const cockpitSecondaryBlocks = computed(() =>
      cockpitBlocks.value.filter(b => b.tier === 'secondary')
    );
    const cockpitFlagshipBlocks = computed(() =>
      cockpitBlocks.value.filter(b => b.tier === 'flagship')
    );
    const cockpitTertiaryBlocks = computed(() =>
      cockpitBlocks.value.filter(b => b.tier === 'tertiary' || b.tier === 'personal' || b.tier === 'archive')
    );
    const cockpitActiveBlockData = computed(() => {
      const k = cockpitActiveBlockKey.value;
      if (!k) return null;
      return (reportsBySection.value || []).find(s => s.key === k) || null;
    });
    const cockpitCurrentDrill = computed(() => {
      const d = cockpitDrillPerson.value;
      const sec = cockpitActiveBlockData.value;
      if (!d || !sec) return null;
      const sg = (sec.subGroups || []).find(s => s.key === d.entityKey);
      if (!sg) return null;
      const p = (sg.persons || []).find(pp => pp.key === d.personKey);
      if (!p) return null;
      return { section: sec, entity: sg, person: p };
    });
    // Bloom master doc (for A4S / 北极星)
    const cockpitBloomMaster = computed(() => {
      const sec = cockpitActiveBlockData.value;
      if (!sec || !sec.bloom) return null;
      return (sec.masters || [])[0] || null;
    });
    // Bloom chapter tiles: parse master doc into h2 chapters
    // Uses reportParsed (which reads reportContent) — cockpitSelectBlock loads
    // the master doc into reportContent so this computed fires automatically.
    const cockpitBloomChapters = computed(() => {
      const sec = cockpitActiveBlockData.value;
      if (!sec || !sec.bloom) return [];
      const parsed = reportParsed.value;
      if (!parsed || !(parsed.sections || []).length) return [];
      const narrative = sec.narrative || [];
      function matchStage(title) {
        const t = (title || '').toLowerCase();
        for (let i = 0; i < narrative.length; i++) {
          const matchers = narrative[i].stageMatcher || [];
          for (const m of matchers) {
            if (t.includes(String(m).toLowerCase())) return i;
          }
        }
        return -1;
      }
      // Only pick top-level sections, drop the trailing meta/version section
      const chapters = parsed.sections
        .filter(s => s.title && !/^版本$|^Version/.test(s.title))
        .map(s => {
          // Strip HTML tags from body for preview, collapse whitespace
          const text = (s.body || []).join('\n').replace(/[#*>`|\-\[\]()]/g, '').replace(/\s+/g, ' ').trim();
          const preview = text.slice(0, 68) + (text.length > 68 ? '…' : '');
          const words = text.length;
          const stageIdx = matchStage(s.title);
          const stage = stageIdx >= 0 ? narrative[stageIdx] : null;
          return {
            id: s.id, num: s.num, title: s.title, preview, words,
            stageIdx,
            stageTag: stage ? stage.stage : '',
            stageLabel: stage ? stage.label : '',
            stageColor: stage ? stage.color : 99,
          };
        });
      // Sort by stageIdx (asc, -1 = unmatched to end), then by original order (use parsed.sections order)
      return chapters.slice().sort((a, b) => {
        const ax = a.stageIdx < 0 ? 999 : a.stageIdx;
        const bx = b.stageIdx < 0 ? 999 : b.stageIdx;
        if (ax !== bx) return ax - bx;
        return 0;
      });
    });
    // W5.3 · Extract "key insights" from the master doc's TL;DR/preface/first-strong-chapter
    // Returns up to 9 short bolded insight strings tagged by source chapter, for the "关键观点墙"
    const cockpitBloomKeyInsights = computed(() => {
      const sec = cockpitActiveBlockData.value;
      if (!sec || !sec.bloom) return [];
      const parsed = reportParsed.value;
      if (!parsed) return [];
      const insights = [];
      const seen = new Set();
      function pushInsight(text, source, stageColor) {
        const t = (text || '').replace(/\s+/g, ' ').trim();
        if (!t || t.length < 4 || t.length > 64) return;
        const key = t.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        insights.push({ text: t, source: source || '', color: stageColor == null ? 99 : stageColor });
      }
      // 1) Pull from preface bold phrases (often contains strongest thesis)
      const prefaceRaw = (parsed.prefaceHtml || '').replace(/<[^>]+>/g, ' ');
      const prefaceBolds = prefaceRaw.match(/\*\*([^*]{4,60})\*\*/g) || [];
      // We can't easily get raw preface markdown; instead mine each chapter body
      // 2) For each section matched to a narrative stage, extract 1-2 strongest bolded phrases
      const narrative = sec.narrative || [];
      function matchStage(title) {
        const t = (title || '').toLowerCase();
        for (let i = 0; i < narrative.length; i++) {
          const matchers = narrative[i].stageMatcher || [];
          for (const m of matchers) {
            if (t.includes(String(m).toLowerCase())) return i;
          }
        }
        return -1;
      }
      const sections = (parsed.sections || []).filter(s => s.title && !/^版本$|^Version/.test(s.title));
      for (const s of sections) {
        if (insights.length >= 9) break;
        const body = (s.body || []).join('\n');
        // Strategy A: look for lines that start with "- **xxx**" or "- xxx，yyy" (short bolded list items)
        const bulletBolds = [];
        const lines = body.split('\n');
        for (const ln of lines) {
          // Strip list marker & bold markers, pick leading statement ≤ 40 chars
          const bm = ln.match(/^\s*[-*]\s+(?:\*\*)?([^*：:。，,.\n]{4,40})(?:\*\*)?[：:，,。.]/);
          if (bm) bulletBolds.push(bm[1].trim());
        }
        // Strategy B: fallback — first **bolded** phrase in a paragraph
        const boldInline = [];
        const boldRe = /\*\*([^*\n]{4,42})\*\*/g;
        let bm;
        while ((bm = boldRe.exec(body)) !== null && boldInline.length < 3) {
          const t = bm[1].trim();
          if (/[一-龥A-Za-z0-9]/.test(t)) boldInline.push(t);
        }
        const stageIdx = matchStage(s.title);
        const stage = stageIdx >= 0 ? narrative[stageIdx] : null;
        const stageColor = stage ? stage.color : 99;
        // Pick up to 2 from this section (prefer bulletBolds over boldInline)
        const picks = bulletBolds.slice(0, 2);
        if (picks.length < 2) {
          for (const b of boldInline) {
            if (picks.length >= 2) break;
            if (!picks.includes(b)) picks.push(b);
          }
        }
        for (const p of picks) {
          if (insights.length >= 9) break;
          pushInsight(p, s.title, stageColor);
        }
      }
      return insights.slice(0, 9);
    });

    // Wave 5: group bloom chapters by narrative stage for visual "stage → chapters" layout
    const cockpitBloomStageGroups = computed(() => {
      const sec = cockpitActiveBlockData.value;
      if (!sec || !sec.bloom) return [];
      const narrative = sec.narrative || [];
      const chapters = cockpitBloomChapters.value || [];
      if (!narrative.length || !chapters.length) return [];
      const groups = narrative.map((stg, i) => ({
        stageIdx: i,
        stage: stg.stage,
        label: stg.label,
        desc: stg.desc,
        color: stg.color,
        chapters: [],
      }));
      const appendix = { stageIdx: -1, stage: '附录', label: '附录 / 其他', desc: '母文档中未被叙事弧覆盖的内容', color: 99, chapters: [] };
      for (const ch of chapters) {
        if (ch.stageIdx >= 0 && groups[ch.stageIdx]) groups[ch.stageIdx].chapters.push(ch);
        else appendix.chapters.push(ch);
      }
      const out = groups.filter(g => g.chapters.length > 0);
      if (appendix.chapters.length > 0) out.push(appendix);
      return out;
    });

    // Markdown editor
    const showCockpitEditor = ref(false);
    const mdEditorContent = ref('');
    const mdEditorDirty = ref(false);
    const mdEditorSaving = ref(false);

    async function loadCockpit() {
      cockpitLoading.value = true;
      cockpitError.value = '';
      try {
        const r = await fetch('/api/cockpit');
        const d = await r.json();
        if (d.ok) {
          cockpitData.value = d;
          if (d.sections?.length && !cockpitActiveSection.value) {
            cockpitActiveSection.value = d.sections[0].id;
          }
          nextTick(() => setupCockpitScrollspy());
        } else {
          cockpitError.value = d.error || '加载失败';
        }
      } catch(e) { cockpitError.value = String(e); }
      finally { cockpitLoading.value = false; }
    }

    // ── Scrollspy & sticky-nav effect ──
    let _cockpitObserver = null;
    let _cockpitScrollHandler = null;
    let _cockpitSpyProgrammatic = false;  // suppress observer during click-scroll
    function setupCockpitScrollspy() {
      teardownCockpitScrollspy();
      const secs = Array.from(document.querySelectorAll('.cockpit-view [data-cockpit-sec]'));
      if (!secs.length) return;

      // IntersectionObserver picks a section "in viewport band" 20% from top
      _cockpitObserver = new IntersectionObserver((entries) => {
        if (_cockpitSpyProgrammatic) return;
        // Find the entry closest to the top-of-band that is intersecting
        let best = null;
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          if (!best || e.boundingClientRect.top < best.boundingClientRect.top) best = e;
        }
        if (best) {
          const sid = best.target.getAttribute('data-cockpit-sec');
          if (sid && cockpitActiveSection.value !== sid) {
            cockpitActiveSection.value = sid;
            // Ensure active chip is visible inside the horizontal nav.
            // Must wait for the DOM to reflect the new .active class before
            // measuring, otherwise we read the PREVIOUS active button.
            nextTick(() => {
              const nav = document.querySelector('.cockpit-view .cockpit-nav');
              if (!nav) return;
              const btns = Array.from(nav.querySelectorAll('button'));
              const idx = (cockpitData.value?.sections || []).findIndex(s => s.id === sid);
              const btn = idx >= 0 ? btns[idx] : nav.querySelector('button.active');
              if (!btn) return;
              const bL = btn.offsetLeft, bW = btn.offsetWidth;
              const nL = nav.scrollLeft, nW = nav.clientWidth;
              const pad = 24;
              if (bL < nL + pad) {
                nav.scrollTo({left: Math.max(0, bL - pad), behavior: 'smooth'});
              } else if (bL + bW > nL + nW - pad) {
                nav.scrollTo({left: bL + bW - nW + pad, behavior: 'smooth'});
              }
            });
          }
        }
      }, {
        root: null,
        rootMargin: '-18% 0px -72% 0px',
        threshold: [0, 0.1, 0.25, 0.5, 0.75, 1],
      });
      for (const s of secs) _cockpitObserver.observe(s);

      // Stuck detection: toggles .is-stuck on the nav when sticky
      const nav = document.querySelector('.cockpit-view .cockpit-nav');
      if (nav) {
        let lastStuck = null;
        _cockpitScrollHandler = () => {
          const rect = nav.getBoundingClientRect();
          const stuck = rect.top <= 0.5;
          if (stuck !== lastStuck) {
            nav.classList.toggle('is-stuck', stuck);
            lastStuck = stuck;
          }
        };
        window.addEventListener('scroll', _cockpitScrollHandler, { passive: true });
        _cockpitScrollHandler();
      }
    }
    function teardownCockpitScrollspy() {
      if (_cockpitObserver) { _cockpitObserver.disconnect(); _cockpitObserver = null; }
      if (_cockpitScrollHandler) {
        window.removeEventListener('scroll', _cockpitScrollHandler);
        _cockpitScrollHandler = null;
      }
    }
    // Teardown when user leaves cockpit view
    watch(() => cockpitData.value && view.value === 'cockpit', (isActive) => {
      if (isActive) nextTick(() => setupCockpitScrollspy());
      else teardownCockpitScrollspy();
    });

    function scrollCockpitTo(sid) {
      cockpitActiveSection.value = sid;
      const el = document.querySelector(`[data-cockpit-sec="${sid}"]`);
      if (el) {
        _cockpitSpyProgrammatic = true;
        el.scrollIntoView({behavior:'smooth', block:'start'});
        setTimeout(() => { _cockpitSpyProgrammatic = false; }, 650);
      }
    }

    function openCockpitExport() {
      window.open('/api/cockpit/export', '_blank');
    }

    async function downloadCockpitHtml() {
      try {
        const r = await fetch('/api/cockpit/export');
        if (!r.ok) throw new Error('导出失败');
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const now = new Date();
        const stamp = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}`;
        a.href = url;
        a.download = `cockpit-${stamp}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('已下载静态 HTML，可直接发邮件/企微附件分享');
      } catch(e) {
        showToast('下载失败：' + e.message, 'error');
      }
    }

    function toggleTrack(tid) {
      expandedTrack.value = expandedTrack.value === tid ? '' : tid;
    }

    function financeTotal(rows, key) {
      if (!rows || !rows.length) return '—';
      let sum = 0;
      for (const r of rows) {
        const v = Number(r[key]);
        if (!isNaN(v)) sum += v;
      }
      return sum.toFixed(1);
    }

    // Channel card expand/collapse state (Set of channel codes)
    const expandedChannels = ref(new Set());
    function isChannelExpanded(code){ return expandedChannels.value.has(code); }
    function toggleChannelExpand(code){
      const s = new Set(expandedChannels.value);
      if (s.has(code)) s.delete(code); else s.add(code);
      expandedChannels.value = s;
    }

    // Split one_liner on "·" into parallel commitments for breathing-room layout
    const oneLinerParts = computed(() => {
      const raw = cockpitData.value?.meta?.one_liner || '';
      if (!raw) return [];
      return raw.split(/[·]/).map(s => s.trim()).filter(Boolean);
    });

    // Split north_star into year tiers for visual layout
    // Input: "一年成为X·三年成为Y·五年成为Z" → [{year:"1yr",text:"成为X"},...]
    const northStarTiers = computed(() => {
      const raw = cockpitData.value?.meta?.north_star || '';
      if (!raw) return [];
      // Split on "·" (middle dot)
      const parts = raw.split(/[·]/).map(s => s.trim()).filter(Boolean);
      // Map each part: extract leading 一年/三年/五年/etc, keep rest as text
      const yrMap = {
        '一年': '1Y', '二年': '2Y', '三年': '3Y', '四年': '4Y', '五年': '5Y',
        '六年': '6Y', '七年': '7Y', '八年': '8Y', '九年': '9Y', '十年': '10Y',
      };
      return parts.map(p => {
        const m = p.match(/^([一二三四五六七八九十]+年)(.*)$/);
        if (m) {
          return { year: yrMap[m[1]] || m[1], text: m[2].trim() };
        }
        return { year: '', text: p };
      });
    });

    // ══ Smart chunker · split a section body into structured chunks for card-based rendering ══
    // Problem: one H2 section can contain 800-word bolded paragraphs ("**判断一：...**xxx") which
    // render as a single wall of text. We detect block boundaries, classify each block, and
    // further split long prose by sentence (。！？) into 180-220 char groups.
    function splitLongText(txt) {
      if (!txt || txt.length <= 220) return [txt || ''];
      // Chinese + Latin sentence split; keep the trailing punctuation with its sentence.
      const sentences = txt.match(/[^。！？!?]+[。！？!?]+|[^。！？!?]+$/g) || [txt];
      const groups = [];
      let cur = '';
      for (const s of sentences) {
        if ((cur + s).length > 240 && cur.length >= 120) {
          groups.push(cur);
          cur = s;
        } else {
          cur += s;
        }
      }
      if (cur) groups.push(cur);
      return groups;
    }
    function classifySmartBlock(b) {
      const t = b.trim();
      if (/^```/.test(t)) return 'code';
      if (/^#{3,6}\s/.test(t)) return 'heading';
      if (/^>/.test(t)) return 'quote';
      if (/^\|/.test(t)) return 'table';
      if (/^([-*+]|\d+\.)\s/m.test(t.split('\n')[0])) return 'list';
      if (/^(?:---+|\*\*\*+|___+)$/.test(t)) return 'hr';
      return 'para';
    }
    const BOLD_HEADLINE_RE = /^\*\*([^*\n]{2,40}?)\*\*\s*[：:、]?\s*([\s\S]*)$/;
    function buildSmartChunks(bodyText) {
      if (!bodyText || !bodyText.trim()) return [];
      const lines = bodyText.split('\n');
      // Group lines into raw blocks separated by blank lines; preserve fenced code as one block.
      const rawBlocks = [];
      let buf = [];
      let inFence = false;
      for (const ln of lines) {
        if (/^```/.test(ln.trim())) {
          buf.push(ln);
          if (inFence) { rawBlocks.push(buf.join('\n')); buf = []; inFence = false; }
          else { inFence = true; }
          continue;
        }
        if (inFence) { buf.push(ln); continue; }
        if (!ln.trim()) {
          if (buf.length) { rawBlocks.push(buf.join('\n')); buf = []; }
        } else {
          buf.push(ln);
        }
      }
      if (buf.length) rawBlocks.push(buf.join('\n'));

      // Merge adjacent list-type blocks into one list block (so `- a\n\n- b` still renders as one list)
      const blocks = [];
      for (const rb of rawBlocks) {
        const t = classifySmartBlock(rb);
        const prev = blocks[blocks.length - 1];
        if (prev && t === 'list' && prev.type === 'list') {
          prev.raw += '\n' + rb;
        } else if (prev && t === 'table' && prev.type === 'table') {
          prev.raw += '\n' + rb;
        } else if (prev && t === 'quote' && prev.type === 'quote') {
          prev.raw += '\n\n' + rb;
        } else {
          blocks.push({ type: t, raw: rb });
        }
      }

      const chunks = [];
      let pendingProse = [];
      let accentCounter = 0;
      const flushProse = () => {
        if (!pendingProse.length) return;
        chunks.push({ kind: 'prose', md: pendingProse.join('\n\n') });
        pendingProse = [];
      };
      const ACCENTS = ['indigo', 'amber', 'teal', 'rose', 'violet'];

      for (const b of blocks) {
        if (b.type === 'heading') {
          flushProse();
          const firstLine = b.raw.split('\n')[0];
          const m = firstLine.match(/^(#{3,6})\s+(.*)$/);
          if (m) {
            chunks.push({ kind: 'h-sub', level: m[1].length, title: m[2].trim() });
            // If heading block had trailing lines, keep them as prose
            const rest = b.raw.split('\n').slice(1).join('\n').trim();
            if (rest) pendingProse.push(rest);
          } else {
            pendingProse.push(b.raw);
          }
          continue;
        }
        if (b.type === 'hr') { flushProse(); chunks.push({ kind: 'hr' }); continue; }
        if (b.type === 'code') { flushProse(); chunks.push({ kind: 'code-card', md: b.raw }); continue; }
        if (b.type === 'list') { flushProse(); chunks.push({ kind: 'list-card', md: b.raw }); continue; }
        if (b.type === 'table') { flushProse(); chunks.push({ kind: 'table-card', md: b.raw }); continue; }
        if (b.type === 'quote') { flushProse(); chunks.push({ kind: 'quote-card', md: b.raw }); continue; }
        // para
        const para = b.raw.replace(/\n/g, ' ').trim();
        const m = para.match(BOLD_HEADLINE_RE);
        if (m && para.length > 140) {
          flushProse();
          const title = m[1].trim();
          const rest = m[2].trim();
          const accent = ACCENTS[accentCounter % ACCENTS.length];
          accentCounter++;
          chunks.push({
            kind: 'headline-card',
            title,
            bodyParas: splitLongText(rest),
            accent,
          });
        } else if (para.length > 380) {
          flushProse();
          chunks.push({ kind: 'long-prose', bodyParas: splitLongText(para) });
        } else {
          pendingProse.push(b.raw);
        }
      }
      flushProse();
      return chunks;
    }

    // Render a chunk list into hydrated HTML (each chunk gets a .html property or .bodyHtml).
    function hydrateChunks(chunks) {
      if (typeof marked === 'undefined') return chunks;
      const md = (s) => marked.parse(s || '', { gfm: true, breaks: true });
      const mdi = (s) => {
        try { return marked.parseInline(s || '', { gfm: true, breaks: false }); }
        catch(e) { return s || ''; }
      };
      return chunks.map(c => {
        if (c.kind === 'prose') return { ...c, html: md(c.md) };
        if (c.kind === 'list-card') return { ...c, html: md(c.md) };
        if (c.kind === 'table-card') return { ...c, html: md(c.md) };
        if (c.kind === 'quote-card') return { ...c, html: md(c.md) };
        if (c.kind === 'code-card') return { ...c, html: md(c.md) };
        if (c.kind === 'headline-card') {
          const bodyHtml = c.bodyParas.map(p => `<p>${mdi(p)}</p>`).join('');
          return { ...c, bodyHtml };
        }
        if (c.kind === 'long-prose') {
          const html = c.bodyParas.map(p => `<p>${mdi(p)}</p>`).join('');
          return { ...c, html };
        }
        return c;
      });
    }

    // ══ Report parser · split markdown into hero + sections for cockpit-grade rendering ══
    const reportParsed = computed(() => {
      let raw = reportContent.value || '';
      if (!raw) return null;
      // ── Strip YAML frontmatter, capturing title/subtitle/eyebrow ──
      let fmTitle = '', fmSubtitle = '', fmEyebrow = '';
      if (/^---\s*\n/.test(raw)) {
        const m = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n?/);
        if (m) {
          const block = m[1];
          for (const ln of block.split('\n')) {
            const kv = ln.match(/^(\w+)\s*:\s*(.*)$/);
            if (!kv) continue;
            const k = kv[1], v = kv[2].replace(/^["']|["']$/g, '').trim();
            if (k === 'title') fmTitle = v;
            else if (k === 'subtitle') fmSubtitle = v;
            else if (k === 'eyebrow') fmEyebrow = v;
          }
          raw = raw.slice(m[0].length);
        }
      }
      const lines = raw.split('\n');
      let title = fmTitle;
      let eyebrow = fmEyebrow;
      const metaPills = [];
      const preface = [];
      let i = 0;
      // First h1 → title (only if not set by frontmatter)
      while (i < lines.length && !lines[i].trim()) i++;
      if (!title && i < lines.length && /^#\s+/.test(lines[i])) {
        title = lines[i].replace(/^#\s+/, '').trim();
        i++;
      }
      // If frontmatter had subtitle, inject as first meta pill
      if (fmSubtitle) {
        metaPills.push({ key: '副标题', val: fmSubtitle });
      }
      // Skip blank lines between title and blockquote
      while (i < lines.length && !lines[i].trim()) i++;
      // Capture blockquote lines as meta pills (allow blank lines within)
      const quoteLines = [];
      while (i < lines.length) {
        const l = lines[i];
        if (/^>\s?/.test(l)) {
          quoteLines.push(l.replace(/^>\s?/, '').trim());
          i++;
        } else if (!l.trim() && quoteLines.length && i+1 < lines.length && /^>\s?/.test(lines[i+1])) {
          i++;
        } else {
          break;
        }
      }
      // Skip blank lines after the blockquote
      while (i < lines.length && !lines[i].trim()) i++;
      if (quoteLines.length) {
        // Parse `**key**：value · **key**：value` pattern from any line
        const pillRe = /\*\*([^*]+)\*\*[：:]\s*([^·\n]+)/g;
        for (const q of quoteLines) {
          let m;
          while ((m = pillRe.exec(q)) !== null) {
            metaPills.push({ key: m[1].trim(), val: m[2].trim().replace(/\s*[（(].*$/,'') });
          }
        }
        // Eyebrow: use quoteLines[0] but strip markdown bold syntax
        // If pills were extracted, use a shorter eyebrow (2nd line if present, else skip)
        if (metaPills.length) {
          eyebrow = quoteLines.length > 1 ? quoteLines[1].replace(/\*\*/g, '').trim() : '';
        } else {
          eyebrow = quoteLines[0].replace(/\*\*/g, '').trim();
        }
      }
      // Everything until first h2 → preface
      while (i < lines.length && !/^##\s+/.test(lines[i])) {
        preface.push(lines[i]);
        i++;
      }
      // Now split into h2 sections
      const sections = [];
      let cur = null;
      while (i < lines.length) {
        const l = lines[i];
        if (/^##\s+/.test(l)) {
          if (cur) sections.push(cur);
          const rawTitle = l.replace(/^##\s+/, '').trim();
          // Try to extract leading number (01, 02, ...) or Roman numeral (I, II, III, ...)
          const romanMap = {I:1,II:2,III:3,IV:4,V:5,VI:6,VII:7,VIII:8,IX:9,X:10,XI:11,XII:12,XIII:13,XIV:14,XV:15,XVI:16,XVII:17,XVIII:18,XIX:19,XX:20};
          const m = rawTitle.match(/^(\d{1,2})[\s·.、）)]+(.*)$/)
                 || rawTitle.match(/^((?:X{0,2}(?:IX|IV|V?I{1,3}|V)))[\s·.、）)]+(.*)$/);
          let numStr = '';
          if (m && m[1]) {
            const raw = m[1];
            numStr = romanMap[raw] !== undefined ? String(romanMap[raw]).padStart(2, '0') : raw.padStart(2, '0');
          }
          cur = {
            id: 'rv-sec-' + sections.length,
            num: numStr,
            hasExplicitNum: !!m,
            title: m ? m[2].trim() : rawTitle,
            body: [],
          };
        } else if (cur) {
          cur.body.push(l);
        } else {
          preface.push(l);
        }
        i++;
      }
      if (cur) sections.push(cur);
      // Render each section body via marked (legacy) + smart chunking (new)
      const md = (txt) => (typeof marked !== 'undefined' && txt) ? badgifyDoc(marked.parse(txt, {gfm:true, breaks:true})) : '';
      return {
        title,
        eyebrow,
        metaPills,
        prefaceHtml: md(preface.join('\n').trim()),
        sections: sections.map(s => {
          const bodyText = s.body.join('\n').trim();
          const rawChunks = buildSmartChunks(bodyText);
          const chunks = hydrateChunks(rawChunks);
          return { ...s, html: md(bodyText), chunks };
        }),
      };
    });

    function scrollToReportSection(id) {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // W5.3: click a narrative-arc stage → scroll the matching bloom stage group into view
    function scrollCockpitToStage(stageIdx) {
      nextTick(() => {
        const el = document.querySelector(`.cp-bloom-stage-group[data-stage-idx="${stageIdx}"]`);
        if (!el) return;
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Brief highlight pulse
        el.classList.add('is-pulse');
        setTimeout(() => el.classList.remove('is-pulse'), 1400);
      });
    }

    async function openCockpitEditor() {
      try {
        const r = await fetch('/api/cockpit/raw');
        const d = await r.json();
        if (!d.ok) throw new Error(d.error || '读取失败');
        mdEditorContent.value = d.content;
        mdEditorDirty.value = false;
        showCockpitEditor.value = true;
        setTimeout(() => {
          const ta = document.querySelector('.cockpit-editor .ce-textarea');
          if (ta) ta.focus();
        }, 50);
      } catch(e) {
        showToast('打开编辑器失败：' + e.message, 'error');
      }
    }

    async function reloadCockpitRaw() {
      if (mdEditorDirty.value && !confirm('有未保存的修改，确定要重新读取并放弃吗？')) return;
      try {
        const r = await fetch('/api/cockpit/raw');
        const d = await r.json();
        if (!d.ok) throw new Error(d.error || '读取失败');
        mdEditorContent.value = d.content;
        mdEditorDirty.value = false;
      } catch(e) {
        showToast('重新读取失败：' + e.message, 'error');
      }
    }

    async function saveCockpitRaw() {
      if (!mdEditorDirty.value || mdEditorSaving.value) return;
      mdEditorSaving.value = true;
      try {
        const r = await fetch('/api/cockpit/save', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({content: mdEditorContent.value}),
        });
        const d = await r.json();
        if (!d.ok) throw new Error(d.error || '保存失败');
        mdEditorDirty.value = false;
        showToast(`已保存 · ${d.bytes} 字节 · 已备份`);
        await loadCockpit();
      } catch(e) {
        showToast('保存失败：' + e.message, 'error');
      } finally {
        mdEditorSaving.value = false;
      }
    }

    function closeCockpitEditor() {
      if (mdEditorDirty.value && !confirm('有未保存的修改，确定关闭吗？')) return;
      showCockpitEditor.value = false;
    }

    // Contacts
    const contacts = ref([]);
    const contactGraph = ref(null);
    const coldContacts = ref([]);
    const selectedContact = ref(null);
    const showContactForm = ref(false);
    const contactFilter = ref({category:'',tier:''});
    const contactView = ref('org');
    // 默认只展开 root；分组节点 id 由 tenant 的 cockpit_config.orgTree 决定，不在代码里写死业务 id
    const orgExpandedNodes = ref(new Set(['root']));
    const orgPersonExpanded = ref(new Set());
    function toggleOrgNode(key) {
      const s = orgExpandedNodes.value;
      if (s.has(key)) s.delete(key); else s.add(key);
      orgExpandedNodes.value = new Set(s);
    }
    function toggleOrgPersons(key) {
      const s = orgPersonExpanded.value;
      if (s.has(key)) s.delete(key); else s.add(key);
      orgPersonExpanded.value = new Set(s);
    }
    const orgTree = reactive([]);  // loaded at init from /api/cockpit/config

    // 动态从联系人按 matchKeys 挂载成员：返回 [...pinned(原 persons), ...matched(联系人 tags/title/company 命中)]
    function orgPersonsFor(node) {
      const pinned = (node.persons || []).filter(p => p && p.name && p.name !== '—').map(p => ({ ...p, pinned: true }));
      const pinnedNames = new Set(pinned.map(p => p.name));
      const keys = node.matchKeys || [];
      if (!keys.length || !contacts.value || !contacts.value.length) return pinned.length ? pinned : (node.persons || []);
      const matched = [];
      for (const c of contacts.value) {
        if (pinnedNames.has(c.name)) continue;
        const tagStr = Array.isArray(c.tags) ? c.tags.join(' | ') : (c.tags || '');
        const hay = [c.title||'', c.company||'', tagStr].join(' | ');
        if (keys.some(k => hay.includes(k))) {
          matched.push({ name: c.name, title: c.title || '', slug: c.slug, _contact: true });
        }
      }
      matched.sort((a,b) => (a.name||'').localeCompare(b.name||'', 'zh'));
      const result = [...pinned, ...matched];
      // 节点没有 matchKeys 命中又没有真实负责人时，保留原 persons（含占位"—"）以便 UI 有提示
      return result.length ? result : (node.persons || []);
    }
    const showInteractionForm = ref(false);
    const newContact = ref({name:'',company:'',title:'',category:'industry',tier:'B',met_context:'',background:'',location:'',wechat:'',phone:'',email:''});
    const newInteraction = ref({method:'微信',summary:''});

    // Contact editing
    const editingContact = ref(false);
    const editContactData = ref({});
    const showMergeSelect = ref(false);

    // Contact categories
    const contactCategories = ref([]);
    const showContactCatForm = ref(false);
    const newContactCat = ref({name:'',color:'#888',icon:'🏷'});

    // Special Days (日子)
    const specialDays = ref([]);
    const showDayForm = ref(false);
    const newDay = ref({name:'',date:'',type:'birthday',repeat:'yearly',icon:'🎂',note:''});
    const calendarMonth = ref(new Date().getMonth());
    const calendarYear = ref(new Date().getFullYear());
    const editingDay = ref(null);

    // Note delete
    const noteDeleteConfirm = ref(null); // {date, idx, preview}

    // Smart Input
    const showSmartInput = ref(false);
    const smartInputText = ref('');
    const smartInputResult = ref(null);
    const smartInputLoading = ref(false);
    const smartInputApplying = ref(false);
    const smartInputSec = ref(0);
    let _smartInputTimer = null;

    // Plan edit popup
    const showGoalEdit = ref(false);
    const goalEditText = ref('');
    const goalEditStart = ref('');
    const goalEditDays = ref(365);
    function openGoalEdit() {
      goalEditText.value = settings.value.main_goal || '';
      goalEditStart.value = settings.value.start_date || new Date().toISOString().slice(0,10);
      // Calculate days from start_date to end (default 365)
      goalEditDays.value = settings.value.plan_days || 365;
      showGoalEdit.value = true;
    }
    async function saveGoalEdit() {
      settings.value.main_goal = goalEditText.value.trim();
      if(goalEditStart.value) settings.value.start_date = goalEditStart.value;
      settings.value.plan_days = goalEditDays.value || 365;
      await api('/settings', {method:'PUT', body:JSON.stringify(settings.value)});
      showGoalEdit.value = false;
      showToast('计划已更新');
      await loadDashboard();
    }

    // Toast
    const toastMsg = ref('');
    const toastType = ref('');
    let toastTimer = null;
    function showToast(msg, type='success') {
      toastMsg.value = msg; toastType.value = type;
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => { toastMsg.value = ''; }, 2000);
    }

    // Voice recording
    const isRecording = ref(false);
    const recordingTime = ref(0);
    let mediaRecorder = null;
    let recordingChunks = [];
    let recordingTimer = null;

    // Speech-to-text
    const isTranscribing = ref(false);

    // Memory
    const memories = ref([]);
    const memoryIndex = ref('');
    const showMemoryForm = ref(false);
    const editingMemory = ref(null);
    const memoryForm = ref({name:'', type:'identity', description:'', content:'', filename:''});
    const memoryTypes = [
      {id:'identity', label:'身份', icon:'👤', desc:'我是谁、角色、价值观'},
      {id:'preference', label:'偏好', icon:'⚙️', desc:'习惯、工作方式'},
      {id:'goal', label:'目标', icon:'🎯', desc:'长期愿景、阶段目标'},
      {id:'skill', label:'技能', icon:'🛠', desc:'擅长什么、在学什么'},
      {id:'insight', label:'洞察', icon:'💡', desc:'AI反思生成的认知'},
      {id:'general', label:'通用', icon:'📝', desc:'其他记忆'},
    ];

    // Search
    const searchQuery = ref('');
    const searchResults = ref([]);
    const searchTotal = ref(0);
    const searchLoading = ref(false);
    const showSearchPanel = ref(false);

    // Streaks
    const streakData = ref({current_streak:0, best_streak:0, total_active_days:0});

    // Mood/Energy/Focus
    const todayMood = ref('');
    const todayEnergy = ref('');
    const todayFocus = ref('');
    const moodOptions = [
      {val:'1',label:'😫',tip:'很差'},{val:'2',label:'😟',tip:'不好'},
      {val:'3',label:'😐',tip:'一般'},{val:'4',label:'🙂',tip:'不错'},
      {val:'5',label:'😊',tip:'很好'},{val:'6',label:'🔥',tip:'爆棚'},
    ];

    // Reflection
    const reflectResult = ref('');
    const reflectLoadingType = ref(''); // 'daily' | 'weekly' | ''

    // Reflections list view
    const reflectionsList = ref([]);
    const reflectionsLoading = ref(false);

    // On This Day
    const onThisDayEntries = ref([]);

    // Growth / 养成
    const growthData = ref(null);
    const editingOmeProfile = ref(false);
    const omeNameEdit = ref('');
    const omePersonalityEdit = ref('');
    const growthTimeline = ref([]);
    const emotionHistory = ref([]);
    const omeMemoryStats = ref(null);

    // Notifications & Reminders
    const notifEnabled = ref(localStorage.getItem('ome365_notif') !== '0');
    const notifSound = ref(localStorage.getItem('ome365_notif_sound') || 'chime');
    const firedReminders = ref(new Set());
    const proactiveMsg = ref('');
    const showProactive = ref(false);
    let reminderInterval = null;
    let proactiveInterval = null;
    let audioCtx = null;

    function getAudioCtx() {
      if(!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      return audioCtx;
    }
    function playSound(type) {
      if(!notifEnabled.value || notifSound.value === 'none') return;
      try {
        const ctx = getAudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        if(type === 'chime') {
          osc.type = 'sine'; osc.frequency.setValueAtTime(880, ctx.currentTime);
          osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
          osc.frequency.setValueAtTime(1320, ctx.currentTime + 0.2);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
          osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.5);
        } else if(type === 'bell') {
          osc.type = 'sine'; osc.frequency.setValueAtTime(660, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.8);
          osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.8);
        } else if(type === 'pop') {
          osc.type = 'sine'; osc.frequency.setValueAtTime(600, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(200, ctx.currentTime + 0.15);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
          osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.2);
        }
      } catch(e) { /* ignore audio errors */ }
    }
    function sendBrowserNotif(title, body) {
      if(!notifEnabled.value) return;
      if(Notification.permission === 'granted') {
        new Notification(title, {body, icon:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="80">🔔</text></svg>'});
      }
    }
    async function checkReminders() {
      const now = new Date();
      const hhmm = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
      try {
        const res = await api('/reminders');
        if(!res?.ok) return;
        const all = [...(res.reminders||[]), ...(res.auto_reminders||[])];
        for(const r of all) {
          if(!r.time || firedReminders.value.has(r.id)) continue;
          if(r.time === hhmm) {
            firedReminders.value.add(r.id);
            playSound(notifSound.value);
            sendBrowserNotif('Ome365 提醒', r.title);
            showToast(`⏰ ${r.title}`, 'info');
          }
        }
      } catch(e) {}
    }
    let lastUserActivity = Date.now();
    let proactiveDismissCount = parseInt(localStorage.getItem('ome365_proactive_dismiss')||'0');
    document.addEventListener('click', () => lastUserActivity = Date.now());
    document.addEventListener('keydown', () => lastUserActivity = Date.now());

    async function checkProactive() {
      if(!notifEnabled.value) return;
      // Don't interrupt if user was active in the last 5 minutes
      if(Date.now() - lastUserActivity < 300000) return;
      // Reduce frequency if user keeps dismissing (back off)
      if(proactiveDismissCount >= 5) return;
      try {
        const res = await api('/proactive');
        if(res?.ok && res.message) {
          proactiveMsg.value = res.message;
          showProactive.value = true;
          playSound('pop');
          setTimeout(() => { if(showProactive.value) { showProactive.value = false; proactiveDismissCount++; localStorage.setItem('ome365_proactive_dismiss', String(proactiveDismissCount)); } }, 15000);
        }
      } catch(e) {}
    }
    function dismissProactive() {
      showProactive.value = false;
      proactiveDismissCount++;
      localStorage.setItem('ome365_proactive_dismiss', String(proactiveDismissCount));
    }
    function acknowledgeProactive() {
      showProactive.value = false;
      proactiveDismissCount = Math.max(0, proactiveDismissCount - 1);
      localStorage.setItem('ome365_proactive_dismiss', String(proactiveDismissCount));
    }
    function requestNotifPermission() {
      if('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
      }
    }
    function toggleNotif(val) {
      notifEnabled.value = val;
      localStorage.setItem('ome365_notif', val ? '1' : '0');
      if(val) requestNotifPermission();
    }
    function setNotifSound(s) {
      notifSound.value = s;
      localStorage.setItem('ome365_notif_sound', s);
      playSound(s);
    }

    // AI
    const aiResponse = ref('');
    const aiLoading = ref(false);
    const aiError = ref('');
    const aiFollowUps = ref([]);
    const aiMemoryImpact = ref(null);

    // Settings
    const settings = ref({user_name:'', main_goal:'365天个人执行计划', start_date:'2026-04-08', ai_mode:'none', api_base_url:'', api_key:'', api_model:'', ollama_url:'http://localhost:11434', ollama_model:'llama3.1', use_proxy:true});
    const apiPresets = [
      {name:'DeepSeek', base_url:'https://api.deepseek.com/v1', model:'deepseek-chat'},
      {name:'OpenRouter', base_url:'https://openrouter.ai/api/v1', model:'deepseek/deepseek-chat'},
      {name:'OpenAI', base_url:'https://api.openai.com/v1', model:'gpt-4o'},
      {name:'Anthropic', base_url:'https://api.anthropic.com/v1', model:'claude-sonnet-4-20250514'},
      {name:'自定义', base_url:'', model:''},
    ];
    function applyPreset(preset) {
      settings.value.api_base_url = preset.base_url;
      settings.value.api_model = preset.model;
    }
    const settingsSaved = ref(false);
    const aiTestResult = ref('');
    const aiTestLoading = ref(false);

    // Sidebar persistence
    watch(sidebarCollapsed, v => localStorage.setItem('ome365_sidebar', v ? '1' : '0'));

    // Tenant config — loaded from /api/tenant/config on app init (brand / cockpit defaults)
    const tenantConfig = ref({brand:{}, cockpit:{}, prompts:{}, categories:{}, entities:{}});
    async function loadTenantConfig() {
      try {
        const r = await fetch('/api/tenant/config');
        if (r.ok) tenantConfig.value = await r.json();
      } catch (e) { /* keep defaults */ }
    }

    // Theme (dark / light) — default variant id comes from tenant, stored in localStorage
    const theme = ref(localStorage.getItem('ome365_theme') || 'dark');
    function applyTheme(name) {
      document.documentElement.setAttribute('data-theme', name);
      localStorage.setItem('ome365_theme', name);
    }
    function setTheme(name) {
      theme.value = name;
      applyTheme(name);
    }
    applyTheme(theme.value);

    // File browser state
    const fileBrowserMode = ref('tree'); // tree | split
    const selectedFolder = ref(null);

    // Nav
    const growthBadge = computed(() => {
      if(!growthData.value) return '';
      const phase = growthData.value.phase;
      if(phase?.icon && phase?.name) return phase.icon + phase.name;
      return '';
    });
    const fileCount = computed(() => fileTree.value.reduce((s,g)=>s+g.count,0));
    const navItems = computed(() => [
      {key:'dashboard',icon:'🔭',label:'全景',badge:todayStats.value.total?todayStats.value.pct+'%':'',badgeColor:'#c8a96e'},
      {key:'tasks',icon:'✅',label:'清单',badge:todayStats.value.total||'',badgeColor:'#f59e0b'},
      {key:'plan',icon:'🗺️',label:'地图',badge:dash.value?.plan_pct!=null?dash.value.plan_pct+'%':'',badgeColor:'#c8a96e'},
      {key:'notes',icon:'📝',label:'速记',badge:dash.value?.notes_count||'',badgeColor:'#38bdf8'},
      {key:'interviews',icon:'🎙️',label:'访谈',badge:interviewCount.value||'',badgeColor:'#06b6d4'},
      {key:'cockpit',icon:'🧭',label:'驾舱',badge:cockpitData.value?.sections?.length||'',badgeColor:'#60a5fa'},
      {key:'reports',icon:'🏛️',label:'汇报',badge:reportsList.value.length||'',badgeColor:'#d4a574'},
      {key:'reflections',icon:'🔮',label:'反思',badge:reflectionsList.value.length||'',badgeColor:'#e879f9'},
      {key:'insights',icon:'💡',label:'洞察',badge:insightsOverview.value?.stats?.notes_count||'',badgeColor:'#fbbf24'},
      {key:'contacts',icon:'🏢',label:'组织',badge:dash.value?.contact_count||'',badgeColor:'#4ade80'},
      {key:'memory',icon:'💎',label:'记忆',badge:omeMemoryStats.value?.total||dash.value?.memory_count||'',badgeColor:'#a78bfa'},
      {key:'growth',icon:'🌿',label:'养成',badge:growthBadge.value,badgeColor:'#34d399'},
      {key:'life',icon:'❤️',label:'生活',badge:lifeOverview.value?.weekend_info?.weekends_left||'',badgeColor:'#f472b6'},
      {key:'files',icon:'📂',label:'文件',badge:fileCount.value||'',badgeColor:'#94a3b8'},
      {key:'settings',icon:'⚙️',label:'设置'},
    ]);
    const mobileNavItems = [
      {key:'dashboard',icon:'🔭',label:'全景'},
      {key:'tasks',icon:'📋',label:'清单'},
      {key:'notes',icon:'✏️',label:'速记'},
      {key:'contacts',icon:'🏢',label:'组织'},
      {key:'files',icon:'📁',label:'更多'},
    ];
    const titles = {dashboard:'全景',tasks:'清单',plan:'365天作战地图',insights:'洞察 · 从你的碎片里看见未来',life:'生活 · 与家人和自己好好相处',notes:'速记',reflections:'反思',contacts:'组织架构',memory:'记忆',growth:'养成',interviews:'访谈',reports:'汇报',files:'文件',settings:'设置'};
    const currentTitle = computed(() => {
      if (view.value === 'cockpit') return tenantConfig.value?.brand?.cockpit_page_title || 'Strategy Cockpit';
      return titles[view.value] || '';
    });
    const notePlaceholder = computed(() => isRecording.value ? '录音中...' : isTranscribing.value ? '语音识别中...' : '写下想法、灵感、待办...');

    // Dashboard computed
    const dateDisplay = computed(() => {
      const d = dash.value?.date;
      if(!d) return '';
      const [y,m,dd] = d.split('-');
      return `${parseInt(m)}月${parseInt(dd)}日`;
    });
    const weekday = computed(() => dash.value?.weekday||'');
    const dayNumber = computed(() => dash.value?.day_number||0);
    const week = computed(() => dash.value?.week_number||0);
    const quarter = computed(() => dash.value?.quarter||1);
    const quarterTheme = computed(() => dash.value?.quarter_theme||'');
    const daysToStart = computed(() => dash.value?.days_to_start||0);
    const planDays = computed(() => settings.value?.plan_days || 365);
    const yearPct = computed(() => Math.min(100,Math.round(dayNumber.value/planDays.value*100)));

    const todayTasks = computed(() => {
      const src = view.value==='today' ? todayData.value?.tasks : dash.value?.today?.tasks;
      return (src||[]).filter(t=>t.text.trim());
    });
    const todayStats = computed(() => {
      const t=todayTasks.value; const d=t.filter(x=>x.done).length;
      return {total:t.length,done:d,pct:t.length?Math.round(d/t.length*100):0};
    });
    const weekTasks = computed(() => {
      const src = view.value==='week' ? weekData.value?.tasks : dash.value?.week?.tasks;
      return (src||[]).filter(t=>t.text.trim());
    });
    const weekStats = computed(() => {
      const t=weekTasks.value; const d=t.filter(x=>x.done).length;
      return {total:t.length,done:d,pct:t.length?Math.round(d/t.length*100):0};
    });
    const weekDayOptions = computed(() => {
      const days = ['周一','周二','周三','周四','周五','周六','周日'];
      const today = new Date();
      const todayStr = today.toISOString().slice(0,10);
      const dow = (today.getDay()+6)%7; // Monday=0
      const result = [];
      for(let i=0; i<7; i++){
        const d = new Date(today);
        d.setDate(d.getDate() - dow + i);
        const ds = d.toISOString().slice(0,10);
        result.push({ date:ds, label: ds===todayStr ? '今天' : days[i], isToday: ds===todayStr });
      }
      return result;
    });

    // Unified tasks computed
    const taskTabs = computed(() => {
      const ut = unifiedTasksData.value;
      return [
        {key:'today', label:'今日', count: todayStats.value.total||''},
        {key:'tomorrow', label:'明日', count: ''},
        {key:'week', label:'本周', count: weekStats.value.total||''},
        {key:'month', label:'本月', count: ''},
        {key:'days', label:'日子', count: specialDays.value.length||''},
      ];
    });
    const tasksTabTitle = computed(() => {
      const m = {today:'今日任务', tomorrow:'明日任务', week:`W${week.value} 本周任务`, month:'本月任务'};
      return m[tasksTab.value]||'';
    });
    const unifiedTasks = computed(() => {
      const ut = unifiedTasksData.value;
      if (!ut) {
        // Fall back to existing data
        if(tasksTab.value==='today') return todayTasks.value;
        if(tasksTab.value==='week') return weekTasks.value;
        return [];
      }
      return (ut.tasks||[]).filter(t=>t.text.trim());
    });
    const unifiedTasksDone = computed(() => unifiedTasks.value.filter(t=>t.done).length);
    const unifiedTasksPct = computed(() => {
      const t = unifiedTasks.value.length;
      return t ? Math.round(unifiedTasksDone.value/t*100) : 0;
    });
    const unifiedSchedule = computed(() => {
      if(unifiedTasksData.value) return unifiedTasksData.value.schedule||[];
      return timeBlocks.value;
    });
    const unifiedTaskGroups = computed(() => {
      const tasks = unifiedTasks.value;
      if(!tasks.length) return [];
      const groups = {};
      const weekdays = ['周一','周二','周三','周四','周五','周六','周日'];
      const todayStr = new Date().toISOString().slice(0,10);
      for(const t of tasks) {
        let label = t.date || '整周';
        if(t.date) {
          const d = new Date(t.date);
          if(t.date === todayStr) label = '今天 · ' + t.date;
          else label = weekdays[d.getDay()===0?6:d.getDay()-1] + ' · ' + t.date;
        }
        if(!groups[label]) groups[label] = {label, date:t.date||'', tasks:[], sortKey:t.date||'9999'};
        groups[label].tasks.push(t);
      }
      const sorted = Object.values(groups).sort((a,b)=>a.sortKey.localeCompare(b.sortKey));
      // Enrich each group with timeline state
      for(const g of sorted) {
        g.done = g.tasks.filter(t=>t.done).length;
        g.total = g.tasks.length;
        g.pct = g.total ? Math.round(g.done/g.total*100) : 0;
        g.isToday = g.date === todayStr;
        g.isPast = g.date && g.date < todayStr;
        g.isFuture = !g.date || g.date > todayStr;
        g.allDone = g.done === g.total && g.total > 0;
      }
      return sorted;
    });

    // Unified agenda: merge tasks + schedule + reminders into one timeline
    const agendaItems = computed(() => {
      if (tasksTab.value === 'week' || tasksTab.value === 'month' || tasksTab.value === 'days') return [];
      const items = [];
      // Collect task titles (normalized) to dedup auto-reminders
      const taskTitles = new Set();
      for (const t of unifiedTasks.value) {
        // Extract time from [HH:MM] prefix if present
        const tm = t.text.match(/^\[(\d{2}:\d{2})(?:-(\d{2}:\d{2}))?\]\s*(.+)/);
        const time = tm ? tm[1] : (t.time||'');
        const timeEnd = tm ? (tm[2]||'') : (t.timeEnd||'');
        const title = tm ? tm[3] : t.text;
        taskTitles.add(title.trim().toLowerCase());
        items.push({ type:'task', time, timeEnd, title, done:t.done, repeat:t.repeat, data:t, badge:'任务', cls:'ag-task' });
      }
      for (const b of unifiedSchedule.value) {
        // Skip empty time-block placeholders (scaffolding rows like "09-12 | |" from the daily template)
        const schedTitle = (b.item||'').trim();
        if(!schedTitle) continue;
        // Dedup: skip schedule items that match a task title
        if(taskTitles.has(schedTitle.toLowerCase())) continue;
        items.push({ type:'schedule', time:b.time||'', title:schedTitle, dim:b.dim, badge:'日程', cls:'ag-schedule' });
      }
      for (const r of reminders.value) {
        // Skip auto-reminders that duplicate a timed task
        if(!r.custom) {
          const rTitle = (r.title||'').trim().toLowerCase();
          if(taskTitles.has(rTitle)) continue;
        }
        items.push({ type:'reminder', time:r.time||'', title:r.title, data:r, badge:r.custom?'提醒':'自动', cls:r.custom?'ag-reminder':'ag-auto', custom:r.custom });
      }
      items.sort((a,b) => {
        if(a.time && !b.time) return -1;
        if(!a.time && b.time) return 1;
        if(a.time && b.time) return a.time.localeCompare(b.time);
        const order = {task:0, schedule:1, reminder:2};
        return (order[a.type]||9) - (order[b.type]||9);
      });
      return items;
    });
    const agendaTimed = computed(() => agendaItems.value.filter(a => a.time));
    const agendaUntimed = computed(() => agendaItems.value.filter(a => !a.time));

    // Ome memory search
    const omeMemoryQuery = ref('');
    const omeMemories = ref([]);
    const omeMemoryLoading = ref(false);
    const omeMemTypeFilter = ref('');
    const editingOmeMemId = ref(null);
    const editingOmeMemContent = ref('');
    const confirmingDeleteId = ref(null);
    let _confirmDeleteTimer = null;
    async function searchOmeMemories(q, types) {
      omeMemoryLoading.value = true;
      let url = '/memories?q=' + encodeURIComponent(q || '最近的事') + '&limit=20';
      if(types) url += '&types=' + encodeURIComponent(types);
      const res = await api(url);
      if (res?.memories) omeMemories.value = res.memories;
      omeMemoryLoading.value = false;
    }
    function startEditOmeMem(m) {
      confirmingDeleteId.value = null;
      editingOmeMemId.value = m.id;
      editingOmeMemContent.value = m.content;
    }
    async function saveOmeMemEdit(m) {
      if (!editingOmeMemContent.value.trim()) return;
      const res = await api(`/memories/${encodeURIComponent(m.id)}`, { method: 'PUT', body: JSON.stringify({ content: editingOmeMemContent.value.trim() }) });
      if (res?.ok) {
        m.content = editingOmeMemContent.value.trim();
        editingOmeMemId.value = null;
        showToast('记忆已更新');
      } else { showToast(res?.error || '更新失败', 'error'); }
    }
    function askDeleteOmeMem(m) {
      editingOmeMemId.value = null;
      confirmingDeleteId.value = m.id;
      clearTimeout(_confirmDeleteTimer);
      _confirmDeleteTimer = setTimeout(() => { confirmingDeleteId.value = null; }, 4000);
    }
    async function confirmDeleteOmeMem(m) {
      clearTimeout(_confirmDeleteTimer);
      const res = await api(`/memories/${encodeURIComponent(m.id)}`, { method: 'DELETE' });
      if (res?.ok) {
        omeMemories.value = omeMemories.value.filter(x => x.id !== m.id);
        showToast('记忆已删除');
      } else { showToast(res?.error || '删除失败', 'error'); }
      confirmingDeleteId.value = null;
    }
    async function loadMemoryStats() {
      const res = await api('/memory-stats');
      if(res?.stats) omeMemoryStats.value = res.stats;
    }

    async function loadUnifiedTasks(tab) {
      const res = await api(`/tasks/unified?tab=${tab||tasksTab.value}`);
      if(res) unifiedTasksData.value = res;
    }
    // Reminders
    async function loadReminders() {
      const res = await api('/reminders');
      if(res?.ok) {
        reminders.value = [
          ...(res.reminders||[]).map(r=>({...r, custom:true})),
          ...(res.auto_reminders||[]).map(r=>({...r, custom:false}))
        ].sort((a,b)=>(a.time||'').localeCompare(b.time||''));
      }
    }
    async function addReminder() {
      if(!newReminder.value.time || !newReminder.value.title) return;
      await api('/reminders',{method:'POST',body:JSON.stringify(newReminder.value)});
      newReminder.value = {time:'', title:''};
      showReminderForm.value = false;
      await loadReminders();
      showToast('提醒已添加');
      recordInteraction();
    }
    async function deleteReminder(rid) {
      await api(`/reminders/${rid}`,{method:'DELETE'});
      await loadReminders();
      showToast('提醒已删除');
    }
    async function switchTasksTab(tab) {
      tasksTab.value = tab;
      addingTodayTask.value = false;
      editingTask.value = null;
      if(tab === 'today') {
        await Promise.all([loadToday(), loadTimeBlocks(), loadReminders()]);
        todayMood.value = dash.value?.today_mood||'';
        todayEnergy.value = dash.value?.today_energy||'';
        todayFocus.value = dash.value?.today_focus||'';
        unifiedTasksData.value = null; // use existing today data
      } else if(tab === 'week') {
        await loadWeek();
        await loadUnifiedTasks('week');
      } else if(tab === 'tomorrow' || tab === 'month') {
        await loadUnifiedTasks(tab);
      } else if(tab === 'days') {
        await loadSpecialDays();
      }
    }
    async function toggleUnifiedTask(t) {
      t.done = !t.done;
      if(t.source === 'weekly') {
        await api('/week/toggle',{method:'POST',body:JSON.stringify({text:t.text})});
      } else {
        // Toggle in the specific daily file
        const targetDate = t.date || '';
        await api('/today/toggle',{method:'POST',body:JSON.stringify({text:t.text, date:targetDate})});
      }
      if(t.done) recordInteraction();
      showToast(t.done ? '已完成' : '已取消完成');
      // Refresh
      if(tasksTab.value === 'today') await loadToday();
      else if(tasksTab.value === 'week') await loadUnifiedTasks('week');
      else if(tasksTab.value === 'tomorrow' || tasksTab.value === 'month') await loadUnifiedTasks(tasksTab.value);
    }
    async function addUnifiedTask() {
      const text = newTodayTask.value.trim();
      if(!text) return;
      const payload = {text, category:newTaskCategory.value, time:buildTaskTime(), repeat:newTaskRepeat.value};
      if(tasksTab.value === 'week') {
        if(newTaskTargetDate.value) payload.target_date = newTaskTargetDate.value;
        const res = await api('/week/add',{method:'POST',body:JSON.stringify(payload)});
        if(res?.ok) {
          newTodayTask.value=''; addingTodayTask.value=false; newTaskTargetDate.value=''; resetTaskForm();
          await loadWeek();
          await loadUnifiedTasks('week');
          showToast(res.date ? `已添加到 ${res.date}` : '任务已添加');
        }
      } else if(tasksTab.value === 'tomorrow') {
        const tmr = new Date(Date.now()+86400000).toISOString().slice(0,10);
        payload.target_date = tmr;
        const res = await api('/week/add',{method:'POST',body:JSON.stringify(payload)});
        if(res?.ok) {
          newTodayTask.value=''; addingTodayTask.value=false; resetTaskForm();
          await loadUnifiedTasks('tomorrow');
          showToast('已添加到明日');
        }
      } else {
        const res = await api('/today/add',{method:'POST',body:JSON.stringify(payload)});
        if(res?.ok) {
          newTodayTask.value=''; addingTodayTask.value=false; resetTaskForm();
          await loadToday();
          await loadUnifiedTasks('today');
          showToast('任务已添加');
        }
      }
    }
    const milestones = computed(() => {
      const all = dash.value?.milestones||[];
      const future = all.filter(m=>!m.past);
      const past = all.filter(m=>m.past);
      return [...past.slice(-1), ...future.slice(0,6)];
    });
    const filteredMilestones = computed(() => {
      const all = planData.value?.milestones||[];
      if(msFilter.value==='past') return all.filter(m=>m.past);
      if(msFilter.value==='important') return all.filter(m=>m.category && m.category!=='其他');
      if(msFilter.value==='week'){
        const now = new Date(); const end = new Date(now); end.setDate(end.getDate()+7);
        const nowStr = now.toISOString().slice(0,10); const endStr = end.toISOString().slice(0,10);
        return all.filter(m=>m.date>=nowStr && m.date<=endStr);
      }
      return all;
    });
    function renderMd(s) { return s ? badgifyDoc(marked.parse(s, {gfm:true, breaks:true})) : ''; }
    // Auto-badge Track/Layer/Zone/Curve/底盘 tokens in rendered HTML
    function badgifyDoc(html) {
      if (!html) return html;
      return html.replace(/(?<![a-zA-Z])(Track\s*[1-3][A-B]?|Layer\s*[0-5]|L[0-5](?=[^a-z])|Zone\s*[1-5]|Curve\s*[1-7]|B[1-7]底盘|C[1-5]航道)(?![a-zA-Z])/gi, (m) => {
        let cls = 'track';
        if (/layer|^L\d/i.test(m)) cls = 'layer';
        else if (/zone/i.test(m)) cls = 'zone';
        else if (/curve/i.test(m)) cls = 'curve';
        else if (/底盘|^B\d/i.test(m)) cls = 'bottom';
        return `<span class="doc-badge doc-badge--${cls}">${m}</span>`;
      });
    }
    const todayHtml = computed(() => marked.parse(todayData.value?.content||dash.value?.today?.content||'',{gfm:true,breaks:true}));
    const weekHtml = computed(() => marked.parse(weekData.value?.content||'',{gfm:true,breaks:true}));
    const currentFileHtml = computed(() => {
      if (!currentFile.value) return '';
      let html = marked.parse(currentFile.value.content||'',{gfm:true,breaks:true});
      // Constrain images
      html = html.replace(/<img /g, '<img style="max-width:300px;max-height:200px;border-radius:8px;" ');
      // Make audio inline
      html = html.replace(/<a href="(\/media\/[^"]+\.(webm|mp3|wav|ogg|m4a))"[^>]*>[^<]*<\/a>/gi,
        '<audio controls src="$1" style="height:36px;margin:4px 0;display:block;"></audio>');
      return badgifyDoc(html);
    });
    const aiResponseHtml = computed(() => aiResponse.value ? marked.parse(aiResponse.value,{gfm:true,breaks:true}) : '');

    // Note date formatting
    function formatNoteDate(isoDate) {
      const today = new Date(); const d = new Date(isoDate + 'T00:00:00');
      const todayStr = today.toISOString().slice(0,10);
      const yest = new Date(today); yest.setDate(yest.getDate()-1);
      const yestStr = yest.toISOString().slice(0,10);
      if(isoDate === todayStr) return '今天';
      if(isoDate === yestStr) return '昨天';
      const [y,m,dd] = isoDate.split('-');
      const wd = ['日','一','二','三','四','五','六'][d.getDay()];
      return `${parseInt(m)}月${parseInt(dd)}日 周${wd}`;
    }
    // Ensure today always shows in notes list
    const notesDisplay = computed(() => {
      const raw = notes.value || [];
      const todayStr = new Date().toISOString().slice(0,10);
      const hasToday = raw.some(g => g.date === todayStr);
      if(hasToday) return raw;
      return [{date:todayStr, items:[], path:`Notes/${todayStr}.md`}, ...raw];
    });
    const decisionDetailHtml = computed(() => decisionDetail.value ? marked.parse(decisionDetail.value.content||'',{gfm:true,breaks:true}) : '');
    const contactDetailHtml = computed(() => selectedContact.value ? marked.parse(selectedContact.value.content||'',{gfm:true,breaks:true}) : '');

    // Plan computed
    const currentPlanQ = computed(() => planData.value?.quarters?.find(q=>q.id===planQuarter.value));

    // Heatmap
    const heatmapActive = computed(() => heatmapData.value ? heatmapData.value.days.filter(d=>d.level>0).length : 0);
    const heatmapMonths = computed(() => {
      if (!heatmapData.value) return [];
      const ms=[]; const names=['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
      let last=-1;
      for (let i=0;i<heatmapData.value.days.length;i++){
        const d=new Date(heatmapData.value.days[i].date);
        if(d.getMonth()!==last){ms.push({label:names[d.getMonth()],col:Math.floor(i/7)+1});last=d.getMonth();}
      }
      return ms;
    });

    // Decision columns
    const decisionColumns = computed(() => {
      const cols=[
        {status:'待验证',class:'col-pending',items:[]},
        {status:'已验证',class:'col-verified',items:[]},
        {status:'需修正',class:'col-revise',items:[]},
      ];
      for(const d of decisions.value){(cols.find(c=>c.status===d.status)||cols[0]).items.push(d);}
      return cols;
    });

    // Contact category helpers (dynamic from server)
    const contactCatLabels = computed(() => {
      const m = {};
      for (const c of contactCategories.value) m[c.id] = c.name;
      return m;
    });
    const contactCatColors = computed(() => {
      const m = {};
      for (const c of contactCategories.value) m[c.id] = c.color;
      return m;
    });

    // Selected folder files (for split mode)
    const selectedFolderFiles = computed(() => {
      if (!selectedFolder.value) return [];
      const group = fileTree.value.find(g => g.folder === selectedFolder.value);
      return group ? group.files : [];
    });

    // API
    async function api(url, opts={}) {
      try {
        const res = await fetch('/api'+url, {headers:{'Content-Type':'application/json'},...opts});
        if (!res.ok) return null;
        return await res.json();
      } catch(e){console.error('API:',e);return null;}
    }

    // Loaders
    async function loadDashboard(){
      dash.value = await api('/dashboard');
      if(!heatmapData.value) heatmapData.value = await api('/heatmap');
    }
    async function loadToday(){todayData.value = await api('/today');}
    async function loadWeek(){weekData.value = await api('/week');}
    async function loadPlan(){
      planData.value = await api('/plan');
      if(planData.value) planQuarter.value = Math.min(4, Math.max(1, (dash.value?.quarter||1)));
    }
    async function loadDecisions(){decisions.value = await api('/decisions')||[];}
    async function loadNotes(){
      const cat = noteCategoryFilter.value;
      const url = cat && cat !== 'all' ? `/notes?category=${cat}` : '/notes';
      notes.value = await api(url)||[];
    }
    async function loadFileTree(){fileTree.value = await api('/tree')||[];}

    // ── Interviews (TicNote) ──
    async function loadInterviews(){
      const data = await api('/interviews')||[];
      // Preserve _open state from previous groups
      const prevOpen = {};
      for(const g of interviewGroups.value) if(g._open) prevOpen[g.date] = true;
      interviewGroups.value = data.map((g,i) => ({...g, _open: prevOpen[g.date] || (Object.keys(prevOpen).length === 0 && i===0)}));
      // Also load hiring candidates
      hiringList.value = await api('/hiring')||[];
    }
    // Interview category list (derived from data)
    const interviewCats = computed(() => {
      const cats = new Set(['全部']);
      for(const g of interviewGroups.value)
        for(const f of g.files)
          if(f.cat) cats.add(f.cat);
      if(hiringList.value.length) cats.add('面试');
      return [...cats];
    });
    // ── Interview stats (overall + per-category) ──
    function fmtMin(sec){ return sec ? Math.round(sec/60).toLocaleString('en-US') : '0'; }
    function fmtWan(n){
      if(!n) return '0';
      if(n < 10000) return (n/1000).toFixed(1) + 'k';
      const w = n/10000;
      return w >= 10 ? w.toFixed(1) : w.toFixed(2);
    }
    const interviewStats = computed(() => {
      let files = 0, sec = 0, chars = 0;
      const byCat = {};
      for(const g of interviewGroups.value){
        for(const f of g.files){
          files++; sec += (f.duration_sec||0); chars += (f.chars||0);
          const c = f.cat || '未分类';
          if(!byCat[c]) byCat[c] = { files: 0, sec: 0, chars: 0 };
          byCat[c].files++; byCat[c].sec += (f.duration_sec||0); byCat[c].chars += (f.chars||0);
        }
      }
      byCat['全部'] = { files, sec, chars };
      if(hiringList.value.length){
        byCat['面试'] = byCat['面试'] || { files: 0, sec: 0, chars: 0 };
        byCat['面试'].files += hiringList.value.length;
      }
      // Diagnosis reports count (excluding master "00·" docs)
      let diagN = 0;
      for(const r of reportsList.value){
        if((r.section||'') === '01-diagnosis' && !/^00[·∙•・\s-]/.test(r.name||'')) diagN++;
      }
      return { files, sec, chars, mins: fmtMin(sec), wan: fmtWan(chars), diagN, byCat };
    });
    // Filtered groups — return original objects so _open stays reactive
    const filteredInterviewGroups = computed(() => {
      const cat = interviewCatFilter.value;
      if(cat === '全部' || cat === '面试') return interviewGroups.value;
      return interviewGroups.value.filter(g => g.files.some(f => f.cat === cat));
    });
    function filteredFiles(g) {
      const cat = interviewCatFilter.value;
      if(cat === '全部' || cat === '面试') return g.files;
      return g.files.filter(f => f.cat === cat);
    }
    // Hiring
    async function openCandidate(c, opts={}){
      selectedCandidate.value = c;
      selectedInterview.value = null; interviewContent.value = '';
      candidateTab.value = 'resume';
      candidateRoundSubTab.value = 'focus';
      candidateTranscript.value = '';
      candidateTransBlocks.value = [];
      candidateSumSections.value = [];
      candidateSpeakerMap.value = {};
      if(!opts.skipNav) pushNav({view:'interviews', detail:'hiring:'+c.id});
      candidateData.value = await api('/hiring/candidate?id='+encodeURIComponent(c.id));
    }
    async function loadRoundTranscript(round){
      if(!round.transcript_source){ candidateTranscript.value='转录来源未配置'; return; }
      candidateTranscript.value='加载中...';
      candidateTransBlocks.value = [];
      candidateSumSections.value = [];
      candidateSpeakerMap.value = {};
      try{
        const src = round.transcript_source;
        const ticIdx = src.indexOf('TicNote/');
        const rel = ticIdx>=0 ? src.substring(ticIdx) : src;
        const r = await api('/interviews/file?path='+encodeURIComponent(rel));
        if(r&&r.raw){
          const parts = r.raw.split(/^## /m);
          let rawTranscript = '', rawSummary = '';
          for(const p of parts){
            if(p.startsWith('转录')) rawTranscript = p.replace(/^转录\s*\n+/,'');
            else if(p.startsWith('总结')) rawSummary = p.replace(/^总结\s*\n+/,'');
          }
          candidateTranscript.value = rawTranscript || r.raw;
          // Parse transcript into speaker blocks (reuse existing parser)
          if(rawTranscript){
            const rawBlocks = parseTranscriptBlocks(rawTranscript);
            const fname = (r.name||'');
            const smap = inferSpeakers(rawBlocks, fname);
            candidateSpeakerMap.value = smap;
            candidateTransBlocks.value = applySpeakerMap(rawBlocks, smap);
          }
          // Parse summary into sections (reuse existing parser)
          if(rawSummary){
            const cleanSum = fixASR(stripJunk(rawSummary));
            candidateSumSections.value = parseSummarySections(cleanSum);
          }
        } else { candidateTranscript.value='无法加载转录内容'; }
      }catch(e){ candidateTranscript.value='加载失败: '+e.message; }
    }
    function loadRoundSummary(round){
      // If we already loaded from transcript_source, candidateSumSections is populated
      // Otherwise parse round.summary markdown into sections
      if(candidateSumSections.value.length) return;
      if(round.summary){
        candidateSumSections.value = parseSummarySections(round.summary);
      }
    }
    // ── ASR 修正词典（硬编码兜底 + EEG 热加载） ──
    // EEG 见 docs/EEG.md。启动时从 /api/entities/asr 热加载，失败则回落到下方硬编码清单。
    const ASR_FIXES = reactive([]);  // loaded at init from /api/cockpit/config
    function fixASR(text) {
      for (const [pat, rep] of ASR_FIXES) text = text.replace(pat, rep);
      return text;
    }
    // EEG 启动热加载：把 /api/entities/asr 的 alias→canonical 规则追加到 ASR_FIXES。
    // 设计为"追加"而非"替换"——硬编码的非实体修正（话术/CAD解析/造价咨询等）仍然保留。
    async function loadASRFromEEG(tenant) {
      // tenant default: fetch without param → server uses TENANT.entities.default_tenant
      const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : '';
      try {
        const r = await fetch(`/api/entities/asr${qs}`);
        if (!r.ok) return;
        const data = await r.json();
        const rules = data.rules || [];
        let added = 0;
        for (const rule of rules) {
          const from = rule.from || '';
          const to = rule.to || '';
          if (!from || !to || from === to) continue;
          // 转义正则元字符，保守匹配字面量
          const pat = new RegExp(from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
          ASR_FIXES.push([pat, to]);
          added++;
        }
        console.log(`[EEG] loaded ${added} ASR rules from /api/entities/asr (tenant=${tenant})`);
      } catch (e) {
        console.warn('[EEG] ASR hot-load failed, using hardcoded fallback:', e.message);
      }
    }
    loadASRFromEEG();  // 异步启动，不阻塞渲染

    // ── TicNote junk strip ──
    const JUNK_LINES = ['新功能','TicNote Cloud','编辑','总结','转录','思维导图','顿悟','深度研究','播客','1.0X','内容由 Shadow 生成','Shadow 2.0'];
    function stripJunk(text) {
      const lines = text.split('\n');
      const clean = [];
      let seenContent = false;
      for (const line of lines) {
        const t = line.trim();
        if (!seenContent) {
          // Skip junk header lines
          if (!t) continue;
          if (JUNK_LINES.some(j => t.includes(j))) continue;
          if (/^\d+:\d+$/.test(t)) continue;  // "0:00" or "64:46"
          if (t === '/') continue;
          if (/^\d{4}年\d{2}月\d{2}日/.test(t) && !t.includes('|')) continue;  // filename repeat
          // tenant-specific junk-title filter (e.g. workspace banner that TicNote prepends)
          {
            const _jt = tenantConfig.value?.brand?.junk_title_prefix;
            if (_jt && t.startsWith(_jt)) continue;
          }
          if (/\.m4a$|\.record$/.test(t)) continue;
          // Meta line with "|" → extract and mark content start
          if (/^\d{4}-\d{2}-\d{2}\s[\d:]+\|/.test(t)) { clean.push(t); seenContent = true; continue; }
          // Tags (short lines before speakers) → keep as tags
          if (t.startsWith('出席人员')) { clean.push(t); seenContent = true; continue; }
          // Short tag-like lines before content starts
          if (t.length < 20 && !t.startsWith('#') && !t.startsWith('📋') && !t.startsWith('🎯')) { continue; }
          seenContent = true;
        }
        // After "内容由 Shadow 生成" → stop (avoid duplicate section)
        if (t === '内容由 Shadow 生成，仅供参考') break;
        clean.push(line);
      }
      return clean.join('\n');
    }

    // ── Parse summary into structured sections ──
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
      // Check if title starts with emoji already
      if (/^[\u{1F000}-\u{1FFFF}]/u.test(title)) return '';
      return '📄';
    }

    function parseSummarySections(text) {
      const sections = [];
      // Split by emoji headings or bold headings
      const lines = text.split('\n');
      let current = null;
      const emojiHeadRe = /^([\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}]+)\s*(.+)$/u;
      const boldHeadRe = /^(?:#{1,3}\s+)?([\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}]*)\s*(.+)$/u;

      for (const line of lines) {
        const t = line.trim();
        if (!t) { if (current) current.body += '\n'; continue; }
        // Emoji-prefixed heading
        const em = t.match(emojiHeadRe);
        if (em && t.length < 80) {
          if (current) sections.push(current);
          current = { icon: em[1], title: em[2].replace(/^#+\s*/, ''), body: '' };
          continue;
        }
        // Bold-prefixed or colon-ended heading pattern (like "产品核心功能与现状：")
        if (t.endsWith('：') && t.length < 50 && !t.startsWith('>') && !t.startsWith('-')) {
          if (current) {
            // Sub-heading within section
            current.body += '\n**' + t + '**\n';
            continue;
          }
        }
        if (current) {
          current.body += line + '\n';
        } else {
          // Content before first heading → intro section
          current = { icon: '📋', title: '概述', body: line + '\n' };
        }
      }
      if (current) sections.push(current);
      // Clean up empty sections, trim bodies
      return sections.filter(s => s.body.trim()).map(s => ({
        ...s,
        icon: s.icon || iconForTitle(s.title),
        body: s.body.trim()
      }));
    }

    // ── Parse transcript into speaker blocks ──
    const SPEAKER_COLORS = ['#60a5fa','#f59e0b','#a78bfa','#34d399','#f472b6','#38bdf8','#ff9e7a','#e879f9'];
    function parseTranscriptBlocks(text) {
      const blocks = [];
      const lines = text.split('\n');
      let i = 0;
      // Skip junk header
      while (i < lines.length) {
        const t = lines[i].trim();
        if (/^SPEAKER_\d+$/.test(t) || /^说话人\d+$/.test(t)) break;
        i++;
      }
      let currentSpeaker = '', currentTime = '', currentText = [];
      while (i < lines.length) {
        const t = lines[i].trim();
        if (/^(?:SPEAKER_\d+|说话人\d+)$/.test(t)) {
          // Flush previous
          if (currentSpeaker && currentText.length) {
            blocks.push({ speaker: currentSpeaker, time: currentTime, text: fixASR(currentText.join(' ').trim()) });
          }
          currentSpeaker = t;
          currentText = [];
          currentTime = '';
          i++;
          // Next line is "|"
          if (i < lines.length && lines[i].trim() === '|') i++;
          // Next line is timestamp
          if (i < lines.length && /^\d{1,3}:\d{2}(:\d{2})?$/.test(lines[i].trim())) {
            currentTime = lines[i].trim();
            i++;
          }
          continue;
        }
        if (t === '|') { i++; continue; }
        // Stop at Shadow summary repeat
        if (t === '内容由 Shadow 生成，仅供参考' || t === '内容由 Shadow 生成') break;
        if (t) currentText.push(t);
        i++;
      }
      if (currentSpeaker && currentText.length) {
        blocks.push({ speaker: currentSpeaker, time: currentTime, text: fixASR(currentText.join(' ').trim()) });
      }
      // Merge consecutive same-speaker blocks
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

    // ── Auto-generate insights ──
    function generateInsights(meta, sections, blocks) {
      const insights = { overview: '', keySignals: [], actionItems: [], consensus: [], risks: [], speakerStats: [] };
      // Overview
      const topicCount = sections.length;
      const blockCount = blocks.length;
      const speakers = [...new Set(blocks.map(b => b.speaker))];
      const duration = meta.duration || '未知';
      insights.overview = `本次会议时长 ${duration}，共 ${speakers.length} 位参与者，讨论涵盖 ${topicCount} 个议题。转录共 ${blockCount} 段发言。`;

      // Speaker stats
      const speakerWords = {};
      for (const b of blocks) {
        speakerWords[b.speaker] = (speakerWords[b.speaker]||0) + b.text.length;
      }
      const totalWords = Object.values(speakerWords).reduce((a,b)=>a+b,0) || 1;
      insights.speakerStats = Object.entries(speakerWords)
        .sort((a,b) => b[1]-a[1])
        .map(([speaker,words]) => {
          // Use raw speaker index for consistent color
          const rawKey = blocks.find(b => b.speaker === speaker)?.speakerRaw || speaker;
          const idx = parseInt(rawKey.replace(/\D/g, '')) || 0;
          return {
            speaker, speakerRaw: rawKey, words, pct: Math.round(words/totalWords*100),
            color: SPEAKER_COLORS[idx % SPEAKER_COLORS.length]
          };
        });

      // Extract from sections
      for (const s of sections) {
        const t = s.title + ' ' + s.body;
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

      // Key signals: pick first sentence of each major section
      for (const s of sections.slice(0, 8)) {
        if (/概述|引用|建议|AI建议/.test(s.title)) continue;
        const firstLine = s.body.split('\n').find(l => l.trim() && l.trim().length > 20);
        if (firstLine) insights.keySignals.push({ title: s.title, icon: s.icon, text: firstLine.trim().substring(0, 120) });
      }

      return insights;
    }

    // ── Curated insights for key meetings ──
    const KNOWN_INSIGHTS = reactive({});  // loaded at init from /api/cockpit/config

    // ── Speaker identification ──
    // Hard-coded mappings for known files (key = substring of filename)
    const KNOWN_SPEAKER_MAPS = reactive({});  // loaded at init from /api/cockpit/config

    // ─────────────────────────────────────────────────────────────
    // Cockpit config loader (data separation: code vs user-data)
    // Real data in .app/cockpit_config.json (gitignored);
    // fallback to .app/cockpit_config.sample.json in git repo.
    // ─────────────────────────────────────────────────────────────
    async function loadCockpitConfig() {
      try {
        const r = await fetch("/api/cockpit/config");
        if (!r.ok) return;
        const cfg = await r.json();
        if (Array.isArray(cfg.SECTION_TAXONOMY))   SECTION_TAXONOMY.splice(0, SECTION_TAXONOMY.length, ...cfg.SECTION_TAXONOMY);
        if (cfg.PERSON_DISPLAY_MAP && typeof cfg.PERSON_DISPLAY_MAP === "object") Object.assign(PERSON_DISPLAY_MAP, cfg.PERSON_DISPLAY_MAP);
        if (Array.isArray(cfg.orgTree))            orgTree.splice(0, orgTree.length, ...cfg.orgTree);
        if (Array.isArray(cfg.ASR_FIXES)) {
          const fixes = cfg.ASR_FIXES.map(f => [new RegExp(f.pattern, f.flags || "g"), f.replacement]);
          ASR_FIXES.splice(0, ASR_FIXES.length, ...fixes);
        }
        if (cfg.KNOWN_SPEAKER_MAPS && typeof cfg.KNOWN_SPEAKER_MAPS === "object") Object.assign(KNOWN_SPEAKER_MAPS, cfg.KNOWN_SPEAKER_MAPS);
        if (cfg.KNOWN_INSIGHTS && typeof cfg.KNOWN_INSIGHTS === "object") Object.assign(KNOWN_INSIGHTS, cfg.KNOWN_INSIGHTS);
        if (Array.isArray(cfg.SPEAKER_HINTS)) {
          const hints = cfg.SPEAKER_HINTS.map(h => [new RegExp(h.pattern, h.flags || ""), h.replacement]);
          SPEAKER_HINTS.splice(0, SPEAKER_HINTS.length, ...hints);
        }
        console.log("[cockpit-config] loaded from", cfg._source || "inline");
      } catch (err) { console.warn("[cockpit-config] load failed:", err); }
    }
    // Kick off loader (fire-and-forget; reactive configs repopulate when ready)
    loadCockpitConfig();

    // Fallback heuristic hints: [pattern, name]
    const SPEAKER_HINTS = reactive([]);  // loaded at init from /api/cockpit/config

    function inferSpeakers(blocks, filename) {
      const blockSpeakers = [...new Set(blocks.map(b => b.speaker))];
      // 1. Check known mappings first
      for (const [key, map] of Object.entries(KNOWN_SPEAKER_MAPS)) {
        if (filename.includes(key)) {
          const result = { ...map };
          for (const sp of blockSpeakers) {
            if (!(sp in result)) result[sp] = sp;
          }
          return result;
        }
      }

      // 2. Fallback: heuristic scoring
      const map = {};
      const speakers = blockSpeakers;
      const scores = {};
      for (const sp of speakers) {
        scores[sp] = {};
        const allText = blocks.filter(b => b.speaker === sp).map(b => b.text).join(' ');
        for (const [pat, name] of SPEAKER_HINTS) {
          const matches = (allText.match(new RegExp(pat.source, 'g')) || []).length;
          if (matches > 0) scores[sp][name] = (scores[sp][name] || 0) + matches;
        }
      }
      const assigned = new Set();
      const entries = [];
      for (const sp of speakers) {
        for (const [name, score] of Object.entries(scores[sp] || {})) {
          entries.push({ sp, name, score });
        }
      }
      entries.sort((a, b) => b.score - a.score);
      for (const { sp, name, score } of entries) {
        if (map[sp] || assigned.has(name)) continue;
        if (score >= 2) { map[sp] = name; assigned.add(name); }
      }
      for (const sp of speakers) {
        if (!map[sp]) {
          const total = blocks.filter(b => b.speaker === sp).reduce((s, b) => s + b.text.length, 0);
          map[sp] = total < 50 ? '（旁听）' : sp;
        }
      }
      return map;
    }

    function applySpeakerMap(blocks, map) {
      return blocks.map(b => ({
        ...b,
        speakerRaw: b.speakerRaw || b.speaker,
        speaker: map[b.speakerRaw || b.speaker] || map[b.speaker] || b.speaker,
      }));
    }

    function updateSpeakerName(rawKey, newName) {
      const map = { ...interviewSpeakerMap.value };
      map[rawKey] = newName;
      interviewSpeakerMap.value = map;
      // Re-apply to blocks
      const rawBlocks = interviewTranscriptBlocks.value.map(b => ({
        ...b, speaker: b.speakerRaw || b.speaker
      }));
      interviewTranscriptBlocks.value = applySpeakerMap(rawBlocks, map);
      // Update insights speaker stats
      const ins = { ...interviewInsights.value };
      if (ins.speakerStats) {
        ins.speakerStats = ins.speakerStats.map(s => ({
          ...s,
          speaker: map[s.speakerRaw || s.speaker] || s.speaker,
          speakerRaw: s.speakerRaw || s.speaker,
        }));
      }
      interviewInsights.value = ins;
    }

    async function openInterview(file, opts={}){
      selectedInterview.value = file;
      interviewTab.value = 'summary';
      if(!opts.skipNav) pushNav({view:'interviews', detail:shortId(file.path), _path:file.path});
      const res = await api('/interviews/file?path='+encodeURIComponent(file.path));
      const raw = res?.raw || '';
      interviewContent.value = raw;

      // Parse sections
      const parts = raw.split(/^## /m);
      let rawSummary = '', rawTranscript = '';
      const meta = {};
      // Header: extract URL
      const header = parts[0] || '';
      const urlM = header.match(/URL:\s*(https?:\/\/\S+)/);
      if(urlM) meta.url = urlM[1];
      for(let i=1;i<parts.length;i++){
        const nl = parts[i].indexOf('\n');
        const name = parts[i].substring(0,nl).trim();
        const body = parts[i].substring(nl+1).trim();
        if(name==='总结') rawSummary = body;
        else if(name==='转录') rawTranscript = body;
      }

      // Extract meta
      for(const line of rawSummary.split('\n').slice(0,40)){
        const m = line.match(/^(\d{4}-\d{2}-\d{2}\s[\d:]+)\|(.+?)\|(.+)$/);
        if(m){ meta.date=m[1]; meta.duration=m[2].trim(); meta.author=m[3].trim(); break; }
      }
      // Extract tags
      const tagLines = rawSummary.split('\n').filter(l => {
        const t = l.trim();
        return t.length > 0 && t.length < 15 && !/^\d|^[|\/]|Shadow|TicNote|新功能|编辑|总结|转录|思维导图|顿悟|深度研究|播客|\.m4a|出席/.test(t) && !/^[\u{1F000}-\u{1FFFF}]/u.test(t);
      });
      // Extract speakers
      const speakerM = rawSummary.match(/出席人员:\s*(.+)/);
      const speakerList = speakerM ? speakerM[1].match(/\[([^\]]+)\]/g)?.map(s => s.replace(/[\[\]]/g,'')) || [] : [];

      // Strip junk & fix ASR
      const cleanSummary = fixASR(stripJunk(rawSummary));
      const cleanTranscript = rawTranscript; // transcript parsed separately

      // Parse into structured data
      const sumSections = parseSummarySections(cleanSummary);
      const rawTransBlocks = parseTranscriptBlocks(rawTranscript);

      // Infer speaker names
      const fname = file.name || file.path?.split('/').pop() || '';
      const speakerMap = inferSpeakers(rawTransBlocks, fname);
      interviewSpeakerMap.value = speakerMap;

      // Apply speaker names to blocks
      const transBlocks = applySpeakerMap(rawTransBlocks, speakerMap);
      let insights = generateInsights(meta, sumSections, transBlocks);

      // Override with curated insights if available
      for (const [key, curated] of Object.entries(KNOWN_INSIGHTS)) {
        if (fname.includes(key)) {
          insights = { ...insights, ...curated };
          // Keep auto-generated speakerStats
          break;
        }
      }

      // Also keep legacy markdown for fallback
      let summaryMd = cleanSummary
        .replace(/^([\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}]+)\s*(.+)$/gmu, '\n### $1 $2\n')
        .replace(/^"(.+)"$/gm, '> $1')
        .replace(/\n{3,}/g, '\n\n');

      interviewSummary.value = summaryMd;
      interviewTranscript.value = rawTranscript;
      interviewMeta.value = meta;
      interviewSummarySections.value = sumSections;
      interviewTranscriptBlocks.value = transBlocks;
      interviewInsights.value = insights;
      interviewSpeakers.value = speakerList;
      interviewTags.value = tagLines.slice(0,5).map(l => l.trim());
    }

    async function shareInterview(file) {
      if (!file || !file.path) return;
      try {
        const res = await api('/share/code?path=' + encodeURIComponent(file.path));
        if (res && res.url) {
          await navigator.clipboard.writeText(res.url);
          shareToast.value = '✓ 已复制';
          setTimeout(() => { shareToast.value = ''; }, 2000);
        }
      } catch (e) {
        shareToast.value = '✗ 失败';
        setTimeout(() => { shareToast.value = ''; }, 2000);
      }
    }

    function autoSlugFromPath(path) {
      return shortId(path);
    }
    let _slugCheckTimer = null;
    let _shareClickAway = null;
    async function openShareDialog(e) {
      if (shareDialog.show) { shareDialog.show = false; return; }
      const rpt = cockpitOpenReport.value || selectedReport.value;
      if (!rpt) return;
      const btn = e?.target?.closest('.share-btn-anchor');
      if (btn) {
        const r = btn.getBoundingClientRect();
        shareDialog.pos = { position: 'fixed', top: (r.bottom + 6) + 'px', right: (window.innerWidth - r.right) + 'px' };
      }
      const title = reportParsed.value?.title || rpt.title || rpt.name || '';
      shareDialog.show = true;
      shareDialog.docTitle = title;
      shareDialog.docPath = rpt.path;
      shareDialog.available = false;
      shareDialog.conflict = false;
      shareDialog.conflictTitle = '';
      shareDialog.url = '';
      shareDialog.copied = false;
      shareDialog.existing = false;
      shareDialog.message = '';
      // Query by path first — detect existing share with any slug (including custom)
      try {
        const res = await api('/share/by-path?path=' + encodeURIComponent(rpt.path) + '&user=' + encodeURIComponent(shareDialog.user));
        if (res && res.found) {
          shareDialog.slug = res.slug;
          shareDialog.autoSlug = false;
          shareDialog.existing = true;
          shareDialog.available = true;
          shareDialog.url = res.url;
        } else {
          shareDialog.autoSlug = true;
          shareDialog.slug = autoSlugFromPath(rpt.path);
          checkShareSlug();
        }
      } catch(e) {
        shareDialog.autoSlug = true;
        shareDialog.slug = autoSlugFromPath(rpt.path);
        checkShareSlug();
      }
      if (_shareClickAway) document.removeEventListener('click', _shareClickAway);
      setTimeout(() => {
        _shareClickAway = (ev) => {
          if (!ev.target.closest('.share-btn-anchor') && !ev.target.closest('.share-pop')) { shareDialog.show = false; document.removeEventListener('click', _shareClickAway); }
        };
        document.addEventListener('click', _shareClickAway);
      }, 0);
    }
    function toggleSlugMode() {
      shareDialog.autoSlug = !shareDialog.autoSlug;
      if (shareDialog.autoSlug) {
        shareDialog.slug = autoSlugFromPath(shareDialog.docPath);
        checkShareSlug();
      }
    }
    async function checkShareSlug() {
      shareDialog.available = false;
      shareDialog.conflict = false;
      shareDialog.conflictTitle = '';
      shareDialog.existing = false;
      const slug = shareDialog.slug.trim();
      if (!slug || !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(slug)) return;
      clearTimeout(_slugCheckTimer);
      _slugCheckTimer = setTimeout(async () => {
        try {
          const res = await api('/share/check-slug?slug=' + encodeURIComponent(slug) + '&user=' + encodeURIComponent(shareDialog.user));
          if (shareDialog.slug.trim() !== slug) return;
          if (res.available) {
            shareDialog.available = true;
          } else if (res.existing?.path === shareDialog.docPath) {
            shareDialog.existing = true;
            shareDialog.available = true;
            shareDialog.url = `${location.protocol}//${location.hostname}:3651/${shareDialog.user}/${slug}`;
          } else {
            shareDialog.conflict = true;
            shareDialog.conflictTitle = res.existing?.title || '';
          }
        } catch(e) {}
      }, 300);
    }
    async function registerShareSlug() {
      const slug = shareDialog.slug.trim();
      if (!slug || !shareDialog.available) return;
      try {
        const res = await api('/share/register?slug=' + encodeURIComponent(slug) + '&path=' + encodeURIComponent(shareDialog.docPath) + '&title=' + encodeURIComponent(shareDialog.docTitle) + '&user=' + encodeURIComponent(shareDialog.user), { method: 'POST' });
        if (res && res.url) {
          shareDialog.url = res.url;
        }
      } catch(e) { showToast('注册失败: ' + (e.message||''), 'error'); }
    }
    async function copyShareUrl() {
      try {
        await navigator.clipboard.writeText(shareDialog.url);
        shareDialog.copied = true;
        setTimeout(() => { shareDialog.copied = false; }, 2000);
      } catch(e) {}
    }
    async function updateShare() {
      const slug = shareDialog.slug.trim();
      if (!slug) return;
      try {
        const res = await api('/share/register?slug=' + encodeURIComponent(slug) + '&path=' + encodeURIComponent(shareDialog.docPath) + '&title=' + encodeURIComponent(shareDialog.docTitle) + '&user=' + encodeURIComponent(shareDialog.user), { method: 'POST' });
        if (res && res.url) { shareDialog.url = res.url; shareDialog.message = '✓ 已更新'; setTimeout(() => { shareDialog.message = ''; }, 2000); }
      } catch(e) { shareDialog.message = '✗ 更新失败'; setTimeout(() => { shareDialog.message = ''; }, 3000); }
    }
    async function unregisterShare() {
      const slug = shareDialog.slug.trim();
      if (!slug) return;
      try {
        await api('/share/register?slug=' + encodeURIComponent(slug) + '&user=' + encodeURIComponent(shareDialog.user), { method: 'DELETE' });
        shareDialog.url = '';
        shareDialog.existing = false;
        shareDialog.available = true;
        shareDialog.autoSlug = true;
        shareDialog.slug = autoSlugFromPath(shareDialog.docPath);
        shareDialog.message = '✓ 已取消分享';
        setTimeout(() => { shareDialog.message = ''; }, 2000);
        checkShareSlug();
      } catch(e) { shareDialog.message = '✗ 取消失败'; setTimeout(() => { shareDialog.message = ''; }, 3000); }
    }

    // ── Reports ──
    async function loadReports(){ reportsList.value = await api('/reports')||[]; }
    async function openReport(rpt, opts={}){
      selectedReport.value = rpt;
      reportEditing.value = false;
      if(!opts.skipNav) pushNav({view:'reports', detail:shortId(rpt.path), _path:rpt.path});
      const res = await api('/reports/file?path='+encodeURIComponent(rpt.path));
      reportContent.value = res?.raw || '';
    }
    function startEditReport(){
      reportEditing.value = true;
      reportEditText.value = reportContent.value;
    }
    async function saveReport(){
      const res = await api('/reports/file', {
        method:'PUT',
        body: JSON.stringify({path: selectedReport.value.path, content: reportEditText.value})
      });
      if(res?.ok){
        reportContent.value = reportEditText.value;
        reportEditing.value = false;
        showToast('已保存');
        await loadReports();
      }
    }
    async function loadCategories(){categories.value = await api('/categories')||[];}
    async function loadContactCategories(){contactCategories.value = await api('/contact-categories')||[];}
    async function loadContacts(){
      const params = new URLSearchParams();
      if(contactFilter.value.category) params.set('category',contactFilter.value.category);
      if(contactFilter.value.tier) params.set('tier',contactFilter.value.tier);
      const q = params.toString();
      contacts.value = await api('/contacts'+(q?'?'+q:''))||[];
    }
    async function loadContactGraph(){contactGraph.value = await api('/contacts/graph');}
    async function loadColdContacts(){coldContacts.value = await api('/contacts/cold')||[];}

    // Memory
    async function loadMemories() {
      const res = await api('/memory');
      if(res) { memories.value = res.memories||[]; memoryIndex.value = res.index||''; }
    }
    async function saveMemory() {
      const f = memoryForm.value;
      if(!f.name.trim()) return;
      const payload = {...f};
      if(editingMemory.value) payload.filename = editingMemory.value;
      const res = await api('/memory',{method:'POST',body:JSON.stringify(payload)});
      if(res?.ok){ showMemoryForm.value=false; editingMemory.value=null; memoryForm.value={name:'',type:'identity',description:'',content:'',filename:''}; await loadMemories(); showToast('记忆已保存'); }
    }
    async function editMemoryFile(m) {
      const res = await api('/memory/'+encodeURIComponent(m.filename));
      if(res){ editingMemory.value=m.filename; memoryForm.value={name:res.name,type:res.type,description:res.description,content:res.content,filename:m.filename}; showMemoryForm.value=true; }
    }
    async function deleteMemory(filename) {
      await api('/memory/'+encodeURIComponent(filename),{method:'DELETE'});
      await loadMemories(); showToast('记忆已删除');
    }

    // Search
    let searchTimer = null;
    async function doSearch() {
      const q = searchQuery.value.trim();
      if(!q) { searchResults.value=[]; searchTotal.value=0; return; }
      searchLoading.value = true;
      const res = await api('/search?q='+encodeURIComponent(q));
      searchLoading.value = false;
      if(res){ searchResults.value=res.results||[]; searchTotal.value=res.total||0; }
    }
    function onSearchInput() {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(doSearch, 300);
    }
    function openSearchResult(r) {
      showSearchPanel.value = false;
      switchView('files');
      nextTick(() => openFile(r.path));
    }

    // Streaks
    async function loadStreaks() {
      const res = await api('/streaks');
      if(res) streakData.value = res;
    }

    // Mood/Energy/Focus
    async function setMood(val) {
      todayMood.value = val;
      if(dash.value) dash.value.today_mood = val; // 同步更新总览
      await api('/today/meta',{method:'PUT',body:JSON.stringify({mood:val})});
      showToast('心情已记录');
    }
    async function setEnergy(val) {
      todayEnergy.value = val;
      await api('/today/meta',{method:'PUT',body:JSON.stringify({energy:val})});
      showToast('能量已记录');
    }
    async function setFocus(val) {
      todayFocus.value = val;
      await api('/today/meta',{method:'PUT',body:JSON.stringify({focus:val})});
      showToast('专注度已记录');
    }

    // Time blocks
    async function loadTimeBlocks() {
      const res = await api('/today/timeblocks');
      if(res?.ok) timeBlocks.value = res.blocks||[];
    }
    async function saveTimeBlocks() {
      const res = await api('/today/timeblocks',{method:'PUT',body:JSON.stringify({blocks:timeBlocks.value})});
      if(res?.ok) { timeBlocks.value = res.blocks||[]; showToast('时间块已保存'); }
    }
    function addTimeBlock() {
      editingBlockIdx.value = -1;
      blockForm.value = {time:'', item:'', dim:''};
      showTimeBlockForm.value = true;
    }
    function editTimeBlock(idx) {
      const b = timeBlocks.value[idx];
      editingBlockIdx.value = idx;
      blockForm.value = {time:b.time, item:b.item, dim:b.dim};
      showTimeBlockForm.value = true;
    }
    function saveBlockForm() {
      const b = {...blockForm.value};
      if(!b.time.trim()) return;
      if(editingBlockIdx.value >= 0) {
        timeBlocks.value[editingBlockIdx.value] = b;
      } else {
        timeBlocks.value.push(b);
      }
      showTimeBlockForm.value = false;
      saveTimeBlocks();
    }
    function deleteTimeBlock(idx) {
      timeBlocks.value.splice(idx, 1);
      saveTimeBlocks();
    }

    // Go to notes with focus (called from floating AI bar)
    async function goSmartNotes() {
      await switchView('notes');
      await nextTick();
      const el = document.querySelector('.notes-editor');
      if (el) { el.focus(); el.scrollIntoView({behavior:'smooth', block:'center'}); }
    }

    // AI Reflection
    async function doReflect(type) {
      reflectLoadingType.value = type; reflectResult.value = '';
      const res = await api('/reflect',{method:'POST',body:JSON.stringify({type})});
      reflectLoadingType.value = '';
      if(res?.ok) {
        reflectResult.value = res.response;
        // Refresh reflections list if on that view
        if (view.value === 'reflections') await loadReflections();
      }
      else reflectResult.value = '反思失败: ' + (res?.error||'');
    }
    const reflectHtml = computed(() => reflectResult.value ? marked.parse(reflectResult.value,{gfm:true,breaks:true}) : '');

    // Reflections list
    async function loadReflections() {
      reflectionsLoading.value = true;
      const res = await api('/reflections');
      if (res?.ok) reflectionsList.value = res.items || [];
      reflectionsLoading.value = false;
    }

    // On This Day
    async function loadOnThisDay() {
      const res = await api('/on-this-day');
      if(res) onThisDayEntries.value = res.entries||[];
    }

    // Growth / 养成
    async function loadGrowth() {
      const [res, tl, eh] = await Promise.all([
        api('/growth'),
        api('/growth/timeline?limit=20'),
        api('/growth/emotion-history?days=30'),
      ]);
      if(res) growthData.value = res;
      if(tl?.timeline) growthTimeline.value = tl.timeline;
      if(eh?.history) emotionHistory.value = eh.history;
    }
    async function recordInteraction(count=1) {
      const res = await api('/growth/interact',{method:'POST',body:JSON.stringify({count})});
      // Auto-trigger AI evolution every 20 interactions
      if(res && res.evolution_pending) {
        triggerEvolve();
      }
      // Refresh growth data if on growth page
      if(view.value === 'growth') await loadGrowth();
    }
    function startEditOmeProfile() {
      editingOmeProfile.value = true;
      omeNameEdit.value = growthData.value?.ome_name || 'Ome';
      omePersonalityEdit.value = growthData.value?.ome_personality || '';
    }
    const growthPhases = [
      {id:'newborn',name:'初生',icon:'🌱'},{id:'forming',name:'成长',icon:'🌿'},
      {id:'distinct',name:'独立',icon:'🌳'},{id:'soulmate',name:'知己',icon:'🌟'},
    ];
    function phaseClass(phaseId) {
      if(!growthData.value || !growthData.value.phase) return '';
      const order = ['newborn','forming','distinct','soulmate'];
      const cur = order.indexOf(growthData.value.phase.id || 'newborn');
      const idx = order.indexOf(phaseId);
      if(idx===cur) return 'phase-active';
      if(idx<cur) return 'phase-done';
      return '';
    }
    const evolving = ref(false);
    const evolveError = ref('');
    async function triggerEvolve() {
      evolving.value = true;
      evolveError.value = '';
      try {
        const res = await api('/growth/evolve',{method:'POST'});
        evolving.value = false;
        if(res?.ok) {
          await loadGrowth(); // refresh timeline — new entry will show with "最新" badge
        } else {
          evolveError.value = res?.error||'进化失败，请稍后再试';
        }
      } catch(e) {
        evolving.value = false;
        evolveError.value = '网络错误，请稍后再试';
      }
    }
    // ═══ Growth Page v2 — Computed & Methods ═══
    const achFilter = ref('all');

    // Soul Orb
    const orbColor = computed(() => {
      const mood = growthData.value?.emotion?.mood || 'neutral';
      const map = {happy:'#d4b07a',curious:'#8b7ad4',excited:'#e8a87c',focused:'#7ad4c8',anxious:'#d47a7a',sad:'#7a9ad4',calm:'#7abf7a',neutral:'#a0a0b8'};
      return map[mood] || map.neutral;
    });
    const orbWarmth = computed(() => growthData.value?.emotion?.warmth || 0.3);
    const orbEnergy = computed(() => growthData.value?.emotion?.energy || 0.5);
    const maturityPct = computed(() => growthData.value?.maturity?.score || 0);

    // Maturity Radar — equilateral triangle, 3 axes at 90°/210°/330°
    const radarVals = computed(() => {
      const m = growthData.value?.maturity || {};
      return [m.reflection_depth||0, m.memory_complexity||0, m.behavioral_consistency||0];
    });
    const radarAngles = [-Math.PI/2, -Math.PI/2+2*Math.PI/3, -Math.PI/2+4*Math.PI/3];
    const radarCx = 120, radarCy = 105, radarR = 80;
    function radarPt(axis, val) {
      const a = radarAngles[axis];
      return { x: radarCx + radarR * val * Math.cos(a), y: radarCy + radarR * val * Math.sin(a) };
    }
    function radarTri(scale) {
      return [0,1,2].map(i => { const p = radarPt(i, scale); return p.x+','+p.y; }).join(' ');
    }
    const radarDataPts = computed(() => radarVals.value.map((v,i) => { const p = radarPt(i, v); return p.x+','+p.y; }).join(' '));
    function radarLbl(i) {
      const offset = [{x:0,y:-12},{x:-50,y:18},{x:50,y:18}];
      const p = radarPt(i, 1.0);
      return { x: p.x + offset[i].x, y: p.y + offset[i].y };
    }

    // Mood Chinese name
    const moodCn = computed(() => {
      const mood = growthData.value?.emotion?.mood || 'neutral';
      const map = {happy:'愉悦',curious:'好奇',excited:'兴奋',focused:'专注',anxious:'焦虑',sad:'低落',calm:'平静',neutral:'平和'};
      return map[mood] || mood;
    });
    function signalCn(s) {
      const map = {gratitude:'感恩',curiosity:'好奇',excitement:'兴奋',frustration:'沮丧',nostalgia:'怀旧',determination:'坚定',vulnerability:'脆弱',joy:'喜悦',worry:'担忧',pride:'自豪',loneliness:'孤独',hope:'希望',confusion:'困惑',love:'爱',anger:'愤怒',peace:'平和',surprise:'惊喜',fear:'恐惧',trust:'信任',awe:'敬畏'};
      return map[s] || s;
    }

    // Valence line chart
    const valencePoints = computed(() => {
      const h = emotionHistory.value;
      if (!h || h.length < 2) return [];
      const n = h.length;
      return h.map((e, i) => ({
        x: (i / (n - 1)) * 400,
        y: 35 - (e.valence || 0) * 30
      }));
    });
    const valenceLine = computed(() => valencePoints.value.map(p => p.x+','+p.y).join(' '));
    const valenceArea = computed(() => {
      const pts = valencePoints.value;
      if (pts.length < 2) return '';
      return 'M' + pts[0].x + ',35 L' + pts.map(p => p.x+','+p.y).join(' L') + ' L' + pts[pts.length-1].x + ',35 Z';
    });

    // Capability unlock tree
    const capabilityMeta = [
      {id:'CHAT',name:'对话',icon:'💬',phase:'newborn'},
      {id:'RECALL',name:'回忆',icon:'🧠',phase:'newborn'},
      {id:'REMEMBER',name:'记忆',icon:'💾',phase:'newborn'},
      {id:'WRITE',name:'写作',icon:'✍️',phase:'newborn'},
      {id:'RESEARCH',name:'研究',icon:'🔬',phase:'forming'},
      {id:'PROACTIVE_GREET',name:'主动问候',icon:'👋',phase:'forming'},
      {id:'FOLLOW_UPS',name:'追问',icon:'🔄',phase:'forming'},
      {id:'SCHEDULE',name:'日程',icon:'📅',phase:'distinct'},
      {id:'EVOLVE',name:'进化',icon:'🧬',phase:'distinct'},
      {id:'SOCIAL',name:'社交',icon:'🤝',phase:'distinct'},
      {id:'SMART_EXTRACT',name:'智能提取',icon:'✨',phase:'distinct'},
      {id:'SPATIAL',name:'空间感知',icon:'🗺️',phase:'soulmate'},
      {id:'MIRROR',name:'镜像对话',icon:'🪞',phase:'soulmate'},
    ];
    const phaseLabels = {newborn:'初生',forming:'成长',distinct:'独立',soulmate:'知己'};
    const currentPhaseId = computed(() => {
      const order = ['newborn','forming','distinct','soulmate'];
      return order.indexOf(growthData.value?.phase?.id || 'newborn');
    });
    const capPhases = computed(() => {
      const unlocked = new Set((growthData.value?.capabilities?.unlocked || []).map(c => c.toUpperCase().replace(/ /g,'_')));
      const phases = ['newborn','forming','distinct','soulmate'];
      return phases.map(ph => ({
        label: phaseLabels[ph],
        caps: capabilityMeta.filter(c => c.phase === ph).map(c => ({
          id: c.id, name: c.name, icon: c.icon,
          on: unlocked.has(c.id)
        }))
      }));
    });

    // Skills
    const skillNames = {chat:'对话',recall:'检索',write:'写作',research:'研究',schedule:'日程',social:'社交',spatial:'空间'};
    function skillNm(key) { return skillNames[key] || key; }
    const skillArr = computed(() => {
      const skills = growthData.value?.skills || {};
      const bondLevel = growthData.value?.bond?.level || 0;
      const minBondMap = {chat:0,recall:0,write:0,research:0,schedule:2,social:4,spatial:4};
      return Object.entries(skills).map(([key, s]) => ({
        key, ...s,
        locked: bondLevel < (minBondMap[key] || 0),
        min_bond_level: minBondMap[key] || 0,
      }));
    });

    // Achievements
    const achMeta = {
      first_chat:{name:'初次对话',icon:'💬',desc:'完成第一次对话',tier:'basic'},
      first_recall:{name:'初次回忆',icon:'🧠',desc:'第一次调用记忆',tier:'basic'},
      streak_3:{name:'三日之约',icon:'🔥',desc:'连续3天互动',tier:'basic'},
      streak_7:{name:'一周不离',icon:'⚡',desc:'连续7天互动',tier:'basic'},
      streak_30:{name:'月度挚友',icon:'🌟',desc:'连续30天互动',tier:'deep'},
      memories_50:{name:'记忆满溢',icon:'💎',desc:'积累50条记忆',tier:'deep'},
      memories_200:{name:'记忆宝库',icon:'🏛️',desc:'积累200条记忆',tier:'deep'},
      evolve_first:{name:'首次进化',icon:'🧬',desc:'触发第一次人格进化',tier:'deep'},
      bond_companion:{name:'同行者',icon:'🤝',desc:'达到同行者羁绊',tier:'basic'},
      bond_confidant:{name:'知心人',icon:'💝',desc:'达到知心人羁绊',tier:'deep'},
      bond_soulmate:{name:'灵魂伴侣',icon:'🌌',desc:'达到灵魂伴侣羁绊',tier:'hidden'},
      skill_master:{name:'技能大师',icon:'🏆',desc:'任一技能熟练度满级',tier:'hidden'},
      night_owl:{name:'夜猫子',icon:'🦉',desc:'凌晨互动',tier:'hidden'},
      early_bird:{name:'早起鸟',icon:'🐦',desc:'清晨6点前互动',tier:'hidden'},
      mood_swing:{name:'情绪过山车',icon:'🎢',desc:'一天内经历3种情绪',tier:'hidden'},
      deep_reflect:{name:'深度反思',icon:'🔮',desc:'L4反思发现新特征',tier:'deep'},
      wordsmith:{name:'文字匠人',icon:'📝',desc:'累计10万字对话',tier:'deep'},
      explorer:{name:'探索者',icon:'🗺️',desc:'使用全部5种技能',tier:'basic'},
      growth_spurt:{name:'成长突增',icon:'📈',desc:'一周互动50次',tier:'deep'},
      century:{name:'百日陪伴',icon:'💯',desc:'相识满100天',tier:'hidden'},
    };
    const filteredAch = computed(() => {
      const achs = growthData.value?.achievements || [];
      // Use SDK achievements directly — they already have name, icon, desc, tier, unlocked
      const all = achs.map(a => ({
        id: a.id, name: a.name || achMeta[a.id]?.name || a.id,
        icon: a.icon || achMeta[a.id]?.icon || '🏅',
        desc: a.desc || a.description || achMeta[a.id]?.desc || '',
        tier: a.tier || achMeta[a.id]?.tier || 'basic',
        unlocked: a.unlocked !== false,
        unlocked_at: a.unlocked_at || null,
      }));
      if (achFilter.value === 'all') return all;
      return all.filter(a => a.tier === achFilter.value);
    });
    const achUnlocked = computed(() => (growthData.value?.achievements || []).filter(a => a.unlocked !== false).length);
    const achTotal = computed(() => (growthData.value?.achievements || []).length);
    function achClass(a) { return a.unlocked ? 'ach-unlocked' : 'ach-locked'; }
    function achIcon(a) { return a.unlocked ? a.icon : '🔒'; }
    function achName(a) { return a.name; }
    function achDesc(a) { return a.desc; }

    // Stats chips
    const statsChips = computed(() => {
      const s = growthData.value?.stats || {};
      return [
        {v: s.total_chats || growthData.value?.total_interactions || 0, l:'对话', c:'#c8a96e'},
        {v: s.total_memories || 0, l:'记忆', c:'#a78bfa'},
        {v: s.total_reflections || 0, l:'反思', c:'#38bdf8'},
        {v: s.streak || 0, l:'连续', c:'#f59e0b'},
        {v: s.total_extractions || 0, l:'提取', c:'#4ade80'},
        {v: growthData.value?.days_since_first || 0, l:'天数', c:'#f472b6'},
      ];
    });

    async function saveOmeProfile() {
      await api('/growth/profile',{method:'PUT',body:JSON.stringify({ome_name:omeNameEdit.value.trim()||'Ome',ome_personality:omePersonalityEdit.value.trim()})});
      editingOmeProfile.value = false;
      await loadGrowth();
      showToast('档案已更新');
    }

    // Settings
    async function loadSettings() { const res = await api('/settings'); if(res) settings.value = res; }
    async function saveSettings() {
      const res = await api('/settings', {method:'PUT', body:JSON.stringify(settings.value)});
      if(res?.ok) { settingsSaved.value = true; setTimeout(()=>settingsSaved.value=false, 2000); showToast('设置已保存'); await loadDashboard(); }
    }
    async function toggleProxy() {
      settings.value.use_proxy = !settings.value.use_proxy;
      await api('/settings', {method:'PUT', body:JSON.stringify(settings.value)});
      showToast(settings.value.use_proxy ? '代理已开启' : '代理已关闭');
    }
    async function testAI() {
      aiTestLoading.value = true; aiTestResult.value = '';
      // Auto-save settings before testing
      await api('/settings', {method:'PUT', body:JSON.stringify(settings.value)});
      const res = await api('/settings/test-ai', {method:'POST'});
      aiTestLoading.value = false;
      if(res?.ok) aiTestResult.value = '✅ 连接成功: ' + (res.response||'').slice(0,100);
      else aiTestResult.value = '❌ 连接失败: ' + (res?.error||'未知错误');
    }


    // Special Days
    async function loadSpecialDays(){ specialDays.value = await api('/days')||[]; }

    // Calendar
    const calendarDays = computed(() => {
      const y = calendarYear.value, m = calendarMonth.value;
      const firstDay = new Date(y, m, 1).getDay(); // 0=Sun
      const daysInMonth = new Date(y, m+1, 0).getDate();
      const cells = [];
      // padding
      for(let i=0; i<(firstDay||7)-1; i++) cells.push({day:0,date:''});
      // actual days
      for(let d=1; d<=daysInMonth; d++){
        const ds = `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const isToday = ds === new Date().toISOString().slice(0,10);
        // Check if any special day falls on this date
        const events = (specialDays.value||[]).filter(sd => {
          if(sd.repeat==='yearly') return sd.date === `${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
          if(sd.repeat==='monthly') return parseInt(sd.date) === d;
          return sd.date === ds;
        });
        cells.push({day:d, date:ds, isToday, events, hasDays: events.length > 0});
      }
      return cells;
    });
    const calendarMonthLabel = computed(() => {
      const names=['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
      return `${calendarYear.value}年 ${names[calendarMonth.value]}`;
    });
    function prevMonth(){ if(calendarMonth.value===0){calendarMonth.value=11;calendarYear.value--;}else calendarMonth.value--; }
    function nextMonth(){ if(calendarMonth.value===11){calendarMonth.value=0;calendarYear.value++;}else calendarMonth.value++; }

    function openDayFormForDate(cell) {
      if(!cell.day) return;
      showDayForm.value = true;
      newDay.value = {name:'',date:cell.date,type:'birthday',repeat:'yearly',icon:'🎂',note:''};
    }

    async function createSpecialDay(){
      if(!newDay.value.name.trim()||!newDay.value.date) return;
      // For yearly repeat, store as MM-DD
      let dateVal = newDay.value.date;
      if(newDay.value.repeat==='yearly' && dateVal.length===10) dateVal = dateVal.slice(5); // YYYY-MM-DD -> MM-DD
      if(newDay.value.repeat==='monthly' && dateVal.length>=2) dateVal = String(parseInt(dateVal.slice(-2))); // extract day
      const payload = {...newDay.value, date: dateVal};
      const res = await api('/days',{method:'POST',body:JSON.stringify(payload)});
      if(res?.ok){ showDayForm.value=false; newDay.value={name:'',date:'',type:'birthday',repeat:'yearly',icon:'🎂',note:''}; await loadSpecialDays(); showToast('已添加'); }
    }
    async function deleteSpecialDay(id){
      await api('/days/'+id,{method:'DELETE'});
      await loadSpecialDays(); showToast('已删除');
    }

    const dayTypeIcons = {'birthday':'🎂','anniversary':'💍','memorial':'🕯','custom':'📌'};
    function onDayTypeChange() {
      newDay.value.icon = dayTypeIcons[newDay.value.type] || '📌';
    }

    // ═══ Insights 数据加载 + 操作 ═══
    async function loadInsights(){
      const r = await api('/insights/overview');
      if(r){
        insightsOverview.value = r;
        insightsLatest.value = r.latest;
        insightsCards.value = r.cards || [];
      }
    }
    async function runSynthesize(){
      insightsLoading.value = true; insightsError.value='';
      try{
        const r = await api('/insights/synthesize', {method:'POST', body: JSON.stringify({
          days: insightsDays.value, focus: insightsFocus.value
        })});
        if(r?.ok){
          insightsLatest.value = r.insight;
          showToast('洞察已生成');
        } else {
          insightsError.value = r?.error || '生成失败';
        }
      } catch(e){ insightsError.value = String(e); }
      finally { insightsLoading.value = false; }
    }
    async function saveInsightCard(){
      if(!insightsLatest.value) return;
      const r = await api('/insights/save', {method:'POST', body: JSON.stringify({
        insight: insightsLatest.value, note: ''
      })});
      if(r?.ok){ showToast('已保存到洞察档案'); await loadInsights(); }
    }
    async function deleteInsightCard(card){
      if(!confirm('删除这张洞察卡片？')) return;
      await api('/insights/card/'+card.id, {method:'DELETE'});
      await loadInsights();
    }
    async function askInsight(){
      const q = insightsAskQ.value.trim();
      if(!q) return;
      insightsAskLoading.value = true;
      try{
        const r = await api('/insights/ask', {method:'POST', body: JSON.stringify({
          question: q, days: insightsDays.value
        })});
        if(r?.ok){
          insightsAskReply.value = r.reply;
          insightsAskHistory.value.unshift({q, reply: r.reply, at: new Date().toLocaleTimeString()});
          insightsAskQ.value='';
        } else {
          insightsError.value = r?.error || '提问失败';
        }
      } finally { insightsAskLoading.value = false; }
    }
    function setInsightFollowup(q){ insightsAskQ.value = q; insightsTab.value='ask'; }

    // ═══ Life 数据加载 + 操作 ═══
    async function loadLife(){
      const r = await api('/life/overview');
      if(r){
        lifeOverview.value = r;
        // Sync health draft from current rings
        const rings = r.health?.rings || {sleep:0,exercise:0,meditate:0,diet:0};
        lifeHealthDraft.value = {...rings};
        // Sync daughter edit form
        lifeDaughterEdit.value = {...(r.daughter || {name:'', birth_date:'', college_age:18})};
      }
    }
    async function saveDaughter(){
      const r = await api('/life/daughter', {method:'POST', body: JSON.stringify(lifeDaughterEdit.value)});
      if(r?.ok){ lifeEditDaughter.value=false; await loadLife(); showToast('已更新'); }
    }
    async function createWeekend(){
      const p = lifeNewWeekend.value;
      if(!p.title.trim() || !p.date){ showToast('请填写标题和日期','error'); return; }
      const acts = (typeof p.activities==='string'? p.activities.split('\n').map(s=>s.trim()).filter(Boolean):p.activities);
      const r = await api('/life/weekend', {method:'POST', body: JSON.stringify({...p, activities: acts})});
      if(r?.ok){
        lifeShowWeekendForm.value=false;
        lifeNewWeekend.value={date:'', title:'', theme:'', activities:'', notes:''};
        await loadLife();
        showToast('周末计划已创建');
      }
    }
    async function toggleWeekendDone(wk){
      await api('/life/weekend/toggle', {method:'POST', body: JSON.stringify({id: wk.id})});
      await loadLife();
    }
    async function deleteWeekend(wk){
      if(!confirm('删除这个周末计划？')) return;
      await api('/life/weekend/'+wk.id, {method:'DELETE'});
      await loadLife();
    }
    async function generateWeekendIdeas(){
      lifeIdeasLoading.value = true;
      try{
        const month = new Date().getMonth()+1;
        const season = month<=2||month===12?'冬季':month<=5?'春季':month<=8?'夏季':'秋季';
        const r = await api('/life/weekend/ideas', {method:'POST', body: JSON.stringify({
          vibe: lifeIdeasVibe.value, season
        })});
        if(r?.ok){ await loadLife(); showToast('已生成 '+r.ideas.length+' 个点子'); }
        else showToast(r?.error||'生成失败','error');
      } finally { lifeIdeasLoading.value=false; }
    }
    function ideaToWeekend(idea){
      const [sat] = (lifeOverview.value?.next_weekend?.saturday)||[''];
      lifeNewWeekend.value = {
        date: lifeOverview.value?.next_weekend?.saturday||'',
        title: idea.title||'',
        theme: idea.vibe||'',
        activities: (Array.isArray(idea.supplies)?idea.supplies.join('\n'):'')+'\n'+(idea.what||''),
        notes: idea.why||'',
      };
      lifeShowWeekendForm.value=true;
    }
    async function saveHealth(){
      const r = await api('/life/health/log', {method:'POST', body: JSON.stringify({
        ...lifeHealthDraft.value, note: lifeHealthNote.value
      })});
      if(r?.ok){ lifeHealthNote.value=''; await loadLife(); showToast('健康已打卡'); }
    }
    function setHealthRing(key, v){
      lifeHealthDraft.value[key] = Math.max(0, Math.min(100, v));
    }
    async function addRitual(){
      const p = lifeNewRitual.value;
      if(!p.text.trim()) return;
      const r = await api('/life/ritual', {method:'POST', body: JSON.stringify(p)});
      if(r?.ok){ lifeNewRitual.value={slot:p.slot, text:''}; await loadLife(); }
    }
    async function toggleRitual(slot, r){
      await api('/life/ritual/toggle', {method:'POST', body: JSON.stringify({slot, id:r.id})});
      await loadLife();
    }
    async function deleteRitual(slot, r){
      await api('/life/ritual/'+slot+'/'+r.id, {method:'DELETE'});
      await loadLife();
    }
    async function addMoment(){
      const p = lifeNewMoment.value;
      if(!p.text.trim()) return;
      const r = await api('/life/moment', {method:'POST', body: JSON.stringify(p)});
      if(r?.ok){
        lifeNewMoment.value={category:p.category, text:''};
        lifeShowMomentForm.value=false;
        await loadLife();
        showToast('时刻已记录');
      }
    }
    async function deleteMoment(m){
      if(!confirm('删除这个时刻？')) return;
      await api('/life/moment/'+m.id, {method:'DELETE'});
      await loadLife();
    }

    // ── Browser history navigation ─────────────────────────────
    history.scrollRestoration = 'manual';
    let navRestoring = false;
    function shortId(str){
      let h = 0x811c9dc5;
      for(let i = 0; i < str.length; i++){ h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193); }
      return (h >>> 0).toString(16).padStart(8, '0');
    }
    function buildNavHash(state){
      if(!state || !state.view) return '#/dashboard';
      let h = '#/' + state.view;
      if(state.detail) h += '/' + state.detail;
      return h;
    }
    function pushNav(state, replace=false){
      if(navRestoring) return;
      const curHash = location.hash;
      if(curHash) sessionStorage.setItem('ome365_sy_'+curHash, String(window.scrollY));
      const cur = history.state || {};
      if(cur.view === state.view && (cur.detail||'') === (state.detail||'')){
        if(replace) history.replaceState(state, '', buildNavHash(state));
        return;
      }
      const method = replace ? 'replaceState' : 'pushState';
      history[method](state, '', buildNavHash(state));
    }
    function navBack(){
      // If history is trivial (length 1), we can't go back through the browser;
      // manually clear detail selections as a safe fallback.
      if(history.length <= 1){
        const cur = history.state || {};
        if(cur.detail){
          const parent = { view: cur.view };
          history.replaceState(parent, '', buildNavHash(parent));
          restoreFromState(parent);
          return;
        }
      }
      history.back();
    }

    async function switchView(key, opts={}){
      view.value=key; currentFile.value=null; editingToday.value=false; showDecisionForm.value=false; decisionDetail.value=null; selectedContact.value=null; editingContact.value=false;
      // Normalize virtual sub-keys (today/week/days) to their actual view for history
      const canonKey = (key==='today'||key==='week'||key==='days') ? 'tasks' : key;
      localStorage.setItem('ome365_view', canonKey);
      loading.value = true;
      if(!opts.skipNav) pushNav({view: canonKey, sub: (key!==canonKey?key:undefined)}, opts.replaceNav);
      switch(key){
        case 'dashboard': if(!dash.value) await loadDashboard(); loadStreaks(); loadOnThisDay(); loadGrowth(); break;
        case 'tasks': await switchTasksTab(tasksTab.value); break;
        case 'today': view.value='tasks'; tasksTab.value='today'; await switchTasksTab('today'); break;
        case 'week': view.value='tasks'; tasksTab.value='week'; await switchTasksTab('week'); break;
        case 'days': view.value='tasks'; tasksTab.value='days'; await switchTasksTab('days'); break;
        case 'plan': await loadPlan(); break;
        case 'insights': await loadInsights(); break;
        case 'life': await loadLife(); break;
        case 'cockpit': await loadCockpit(); break;
        case 'notes': await loadNotes(); break;
        case 'reflections': await loadReflections(); break;
        case 'contacts': await Promise.all([loadContacts(), loadColdContacts(), loadContactCategories()]); break;
        case 'memory': await Promise.all([loadMemories(), searchOmeMemories(''), loadMemoryStats()]); break;
        case 'growth': await loadGrowth(); break;
        case 'interviews': if(!interviewGroups.value.length) await loadInterviews(); if(!reportsList.value.length) loadReports(); if(!opts.skipNav){ selectedInterview.value=null; interviewContent.value=''; selectedCandidate.value=null; candidateData.value=null; } break;
        case 'reports': if(!reportsList.value.length) await loadReports(); if(!opts.skipNav){ selectedReport.value=null; reportContent.value=''; } break;
        case 'files': await loadFileTree(); break;
        case 'settings': await loadSettings(); break;
      }
      loading.value = false;
    }

    // Actions
    async function toggleToday(t){
      if(t._toggling) return; t._toggling = true;
      t.done=!t.done;
      await api('/today/toggle',{method:'POST',body:JSON.stringify({text:t.text})});
      t._toggling = false;
      if(t.done) recordInteraction();
      if(t.done && t.repeat === 'daily') showToast('已完成 · 明天自动重新出现 🔁');
      else if(t.done && t.repeat === 'weekly') showToast('已完成 · 下周自动重新出现 🔁');
      else showToast(t.done ? '已完成' : '已取消完成');
    }
    async function toggleWeek(t){
      if(t._toggling) return; t._toggling = true;
      t.done=!t.done;
      await api('/week/toggle',{method:'POST',body:JSON.stringify({text:t.text})});
      t._toggling = false;
      if(t.done && t.repeat) showToast('已完成 · 自动重复 🔁');
      else showToast(t.done ? '已完成' : '已取消完成');
    }
    async function togglePlanTask(t){
      t.done=!t.done;
      await api('/plan/toggle',{method:'POST',body:JSON.stringify({text:t.text})});
      showToast(t.done ? '已完成' : '已取消完成');
      if(planData.value){
        for(const q of planData.value.quarters){
          for(const d of q.dimensions){
            const dt=d.tasks.length; const dd=d.tasks.filter(t=>t.done).length;
            d.stats={total:dt,done:dd,pct:dt?Math.round(dd/dt*100):0};
          }
          const tt=q.dimensions.reduce((s,d)=>s+d.stats.total,0);
          const td=q.dimensions.reduce((s,d)=>s+d.stats.done,0);
          q.stats={total:tt,done:td,pct:tt?Math.round(td/tt*100):0};
        }
        const at=planData.value.quarters.reduce((s,q)=>s+q.stats.total,0);
        const ad=planData.value.quarters.reduce((s,q)=>s+q.stats.done,0);
        planData.value.overview={total:at,done:ad,pct:at?Math.round(ad/at*100):0};
      }
    }

    // Task add with category
    function buildTaskTime() {
      if(!newTaskTime.value) return '';
      if(newTaskTimeRange.value && newTaskTimeEnd.value) return `${newTaskTime.value}-${newTaskTimeEnd.value}`;
      return newTaskTime.value;
    }
    function resetTaskForm() {
      newTaskCategory.value=''; newTaskTime.value=''; newTaskTimeEnd.value=''; newTaskTimeRange.value=false; newTaskRepeat.value='none';
    }
    async function addTodayTask(){
      const text = newTodayTask.value.trim(); if(!text) return;
      const res = await api('/today/add',{method:'POST',body:JSON.stringify({text, category:newTaskCategory.value, time:buildTaskTime(), repeat:newTaskRepeat.value})});
      if(res?.ok){ newTodayTask.value=''; addingTodayTask.value=false; resetTaskForm(); await loadToday(); showToast('任务已添加'); }
    }
    async function addWeekTask(){
      const text = newWeekTask.value.trim(); if(!text) return;
      const payload = {text, category:newTaskCategory.value, time:buildTaskTime(), repeat:newTaskRepeat.value};
      if(newTaskTargetDate.value) payload.target_date = newTaskTargetDate.value;
      const res = await api('/week/add',{method:'POST',body:JSON.stringify(payload)});
      if(res?.ok){
        newWeekTask.value=''; addingWeekTask.value=false; newTaskTargetDate.value=''; resetTaskForm();
        await loadWeek();
        if(res.target==='daily') await loadToday(); // Refresh today if added to a daily file
        showToast(res.date ? `已添加到 ${res.date}` : '任务已添加');
      }
    }

    // Task editing
    function startEditTask(task, type) {
      editingTask.value = {text: task.text, type, date: task.date || ''};
      // Parse time prefix like [09:00] or [09:00-12:00]
      const tmRange = task.text.match(/^\[(\d{2}:\d{2})-(\d{2}:\d{2})\]\s*/);
      const tmPoint = task.text.match(/^\[(\d{2}:\d{2})\]\s*/);
      if(tmRange) {
        editTaskTime.value = tmRange[1];
        editTaskTimeEnd.value = tmRange[2];
        editTaskTimeRange.value = true;
        editTaskText.value = task.text.replace(/^\[\d{2}:\d{2}-\d{2}:\d{2}\]\s*/, '');
      } else if(tmPoint) {
        editTaskTime.value = tmPoint[1];
        editTaskTimeEnd.value = '';
        editTaskTimeRange.value = false;
        editTaskText.value = task.text.replace(/^\[\d{2}:\d{2}\]\s*/, '');
      } else {
        editTaskTime.value = '';
        editTaskTimeEnd.value = '';
        editTaskTimeRange.value = false;
        editTaskText.value = task.text;
      }
      editTaskDesc.value = task.description || '';
    }
    async function _refreshCurrentTab() {
      const tab = tasksTab.value;
      if (tab === 'today') await loadToday();
      else if (tab === 'week') { await loadWeek(); await loadUnifiedTasks('week'); }
      else if (tab === 'tomorrow' || tab === 'month') await loadUnifiedTasks(tab);
    }
    async function saveEditTask() {
      if (!editingTask.value) return;
      const endpoint = editingTask.value.type === 'today' ? '/today/task' : '/week/task';
      let newText = editTaskText.value.trim() || editingTask.value.text;
      newText = newText.replace(/^\[\d{2}:\d{2}(?:-\d{2}:\d{2})?\]\s*/, '');
      if(editTaskTime.value && editTaskTimeRange.value && editTaskTimeEnd.value) {
        newText = `[${editTaskTime.value}-${editTaskTimeEnd.value}] ${newText}`;
      } else if(editTaskTime.value) {
        newText = `[${editTaskTime.value}] ${newText}`;
      }
      const res = await api(endpoint, {method:'PUT', body:JSON.stringify({
        old_text: editingTask.value.text,
        new_text: newText,
        description: editTaskDesc.value.trim(),
      })});
      if (res?.ok) {
        editingTask.value = null;
        await _refreshCurrentTab();
        showToast('任务已更新');
      }
    }
    function cancelEditTask() { editingTask.value = null; }

    async function deleteTask() {
      if (!editingTask.value) return;
      const endpoint = editingTask.value.type === 'today' ? '/today/task' : '/week/task';
      const payload = {text: editingTask.value.text};
      if (editingTask.value.date) payload.date = editingTask.value.date;
      const res = await api(endpoint, {method:'DELETE', body:JSON.stringify(payload)});
      if (res?.ok) {
        editingTask.value = null;
        await _refreshCurrentTab();
        showToast('任务已删除');
      }
    }
    async function quickDeleteTask(task, type) {
      const endpoint = type === 'today' ? '/today/task' : '/week/task';
      // For tasks from specific dates (tomorrow/week/month), pass date context
      const payload = {text: task.text};
      if (task.date) payload.date = task.date;
      const res = await api(endpoint, {method:'DELETE', body:JSON.stringify(payload)});
      if (res?.ok) {
        await _refreshCurrentTab();
        showToast('已删除');
      }
    }

    // Categories
    async function createCategory(){
      if(!newCategory.value.name.trim()) return;
      await api('/categories',{method:'POST',body:JSON.stringify(newCategory.value)});
      newCategory.value={name:'',color:'#888',icon:'📌'}; showCategoryForm.value=false;
      await loadCategories(); showToast('分类已创建');
    }
    async function deleteCategory(id){
      await api('/categories/'+id,{method:'DELETE'});
      await loadCategories(); showToast('分类已删除');
    }

    // Contact categories
    async function createContactCategory(){
      if(!newContactCat.value.name.trim()) return;
      await api('/contact-categories',{method:'POST',body:JSON.stringify(newContactCat.value)});
      newContactCat.value={name:'',color:'#888',icon:'🏷'}; showContactCatForm.value=false;
      await loadContactCategories(); showToast('联系人分类已创建');
    }
    async function deleteContactCategory(id){
      await api('/contact-categories/'+id,{method:'DELETE'});
      await loadContactCategories(); showToast('分类已删除');
    }

    function startEditToday(){todayEditRaw.value=todayData.value?.raw||'';editingToday.value=true;}
    async function saveToday(){
      await api('/today/content',{method:'PUT',body:JSON.stringify({raw:todayEditRaw.value})});
      editingToday.value=false; await loadToday(); showToast('已保存');
    }

    async function submitNote(){
      const text=noteText.value.trim(); if(!text)return;
      const res=await api('/notes',{method:'POST',body:JSON.stringify({text, category:noteCategory.value})});
      if(res?.ok){noteSuccess.value=true;noteTime.value=res.time;noteText.value='';await loadNotes();setTimeout(()=>noteSuccess.value=false,2000);recordInteraction();}
    }

    async function saveAIAsNote(){
      if(!aiResponse.value) return;
      const text = '🤖 AI整理：\n' + aiResponse.value;
      const res = await api('/notes',{method:'POST',body:JSON.stringify({text})});
      if(res?.ok){ showToast('AI回复已保存为速记'); await loadNotes(); }
    }

    function confirmDeleteNote(date, idx, text) {
      const preview = text.length > 20 ? text.slice(0,20)+'...' : text;
      noteDeleteConfirm.value = { date, idx, preview };
    }
    async function executeDeleteNote() {
      if (!noteDeleteConfirm.value) return;
      const { date, idx } = noteDeleteConfirm.value;
      const res = await api(`/notes/${date}/${idx}`, { method: 'DELETE' });
      if (res?.ok) { showToast('已删除'); await loadNotes(); }
      noteDeleteConfirm.value = null;
    }

    async function runSmartInput() {
      const text = noteText.value.trim();
      if (!text) return;
      smartInputLoading.value = true;
      smartInputResult.value = null;
      smartInputSec.value = 0;
      _smartInputTimer = setInterval(() => smartInputSec.value++, 1000);
      try {
        const res = await api('/ai/smart-input', { method: 'POST', body: JSON.stringify({ text }) });
        if (res?.ok) {
          smartInputResult.value = res.data;
        } else {
          showToast(res?.error || 'AI分析失败', 'error');
        }
      } catch(e) {
        showToast('网络错误', 'error');
      }
      clearInterval(_smartInputTimer);
      smartInputLoading.value = false;
    }
    async function applySmartInput() {
      if (!smartInputResult.value) return;
      smartInputApplying.value = true;
      try {
        const res = await api('/ai/smart-input/apply', { method: 'POST', body: JSON.stringify({ data: smartInputResult.value }) });
        if (res?.ok) {
          const r = res.results;
          const parts = [];
          const isRename = smartInputResult.value && smartInputResult.value.type === 'rename';
          if (isRename) {
            if (r.files_renamed) parts.push(`改动${r.files_renamed}个文件`);
            if (r.replacements) parts.push(`替换${r.replacements}处`);
            if (r.contacts_updated) parts.push(`联系人档案更名`);
            if (r.entity_created) parts.push(`EEG新建实体`);
            else if (r.entity_alias_added) parts.push(`EEG登记别名`);
            // Reload EEG ASR rules so future inputs benefit
            if (typeof loadASRFromEEG === 'function') { try { await loadASRFromEEG(); } catch(e){} }
          } else {
            if (r.contacts_created) parts.push(`新建${r.contacts_created}个联系人`);
            if (r.contacts_updated) parts.push(`更新${r.contacts_updated}个联系人`);
            if (r.interactions_added) parts.push(`添加${r.interactions_added}条互动`);
            if (r.todos_added) parts.push(`添加${r.todos_added}条待办`);
            if (r.notes_added) parts.push(`添加${r.notes_added}条笔记`);
          }
          showToast(parts.join('、') || '完成');
          noteText.value = '';
          smartInputResult.value = null;
          recordInteraction(Object.values(r).filter(v=>typeof v==='number').reduce((a,b)=>a+b,0) || 1);
          // Refresh relevant data
          if (view.value === 'today') await loadToday();
          if (view.value === 'notes') await loadNotes();
          if (view.value === 'contacts') await loadContacts();
        } else {
          showToast(res?.error || '写入失败', 'error');
        }
      } catch(e) {
        showToast('网络错误', 'error');
      }
      smartInputApplying.value = false;
    }

    async function createDecision(){
      if(!newDecision.value.title.trim())return;
      const res=await api('/decisions',{method:'POST',body:JSON.stringify(newDecision.value)});
      if(res?.ok){showDecisionForm.value=false;newDecision.value={title:'',scope:'架构',impact:'中',background:''};await loadDecisions();showToast('决策已创建');}
    }
    async function toggleDecisionStatus(d, e){
      if(e) e.stopPropagation();
      const res=await api('/decisions/toggle-status',{method:'POST',body:JSON.stringify({file:d.file})});
      if(res?.ok){ d.status=res.new_status; showToast('状态: '+res.new_status); }
    }
    async function openDecisionDetail(d){
      const res = await api('/decisions/'+encodeURIComponent(d.file));
      if(res) decisionDetail.value = res;
    }

    // Contacts
    async function createContact(){
      if(!newContact.value.name.trim()) return;
      const res = await api('/contacts',{method:'POST',body:JSON.stringify(newContact.value)});
      if(res?.ok){
        showContactForm.value=false;
        newContact.value={name:'',company:'',title:'',category:'industry',tier:'B',met_context:'',background:'',location:'',wechat:'',phone:'',email:''};
        await loadContacts(); showToast('联系人已创建');
      }
    }
    async function selectContactDetail(c, opts={}){
      const res = await api('/contacts/'+encodeURIComponent(c.slug));
      if(res) {
        selectedContact.value = res;
        editingContact.value = false;
        if(!opts.skipNav) pushNav({view:'contacts', detail:c.slug});
      }
    }
    function startEditContact() {
      if (!selectedContact.value) return;
      editContactData.value = {
        name: selectedContact.value.name,
        company: selectedContact.value.company,
        title: selectedContact.value.title,
        category: selectedContact.value.category,
        tier: selectedContact.value.tier,
        location: selectedContact.value.location,
        wechat: selectedContact.value.wechat||'',
        phone: selectedContact.value.phone||'',
        email: selectedContact.value.email||'',
        next_followup: selectedContact.value.next_followup||'',
        met_context: selectedContact.value.met_context||'',
        background: '',
      };
      // Extract background from content
      const bgMatch = (selectedContact.value.content||'').match(/## 关系背景\n([\s\S]*?)(?=\n##|$)/);
      if(bgMatch) editContactData.value.background = bgMatch[1].trim();
      editingContact.value = true;
    }
    async function saveEditContact() {
      if (!selectedContact.value) return;
      const res = await api('/contacts/'+selectedContact.value.slug, {method:'PUT', body:JSON.stringify(editContactData.value)});
      if (res?.ok) {
        editingContact.value = false;
        await selectContactDetail({slug: res.slug || selectedContact.value.slug});
        await loadContacts();
        showToast('联系人已更新');
      }
    }
    async function addInteraction(){
      if(!selectedContact.value || !newInteraction.value.summary.trim()) return;
      const res = await api('/contacts/'+selectedContact.value.slug+'/interact',{method:'POST',body:JSON.stringify(newInteraction.value)});
      if(res?.ok){
        showInteractionForm.value=false; newInteraction.value={method:'微信',summary:''};
        await selectContactDetail(selectedContact.value);
        await loadContacts(); showToast('互动已记录');
      }
    }

    async function mergeContacts(primarySlug, secondarySlug) {
      const res = await api('/contacts/merge', {method:'POST', body:JSON.stringify({primary:primarySlug, secondary:secondarySlug})});
      if(res?.ok) {
        showToast(`已合并到 ${res.merged_into}`);
        selectedContact.value = null;
        await loadContacts();
      } else {
        showToast(res?.error||'合并失败', 'error');
      }
    }

    // Enhanced graph
    async function initGraph(){
      if(!contactGraph.value) return;
      // Lazy load force-graph
      if(typeof ForceGraph === 'undefined'){
        await new Promise((resolve, reject) => {
          const s = document.createElement('script');
          s.src = 'https://unpkg.com/force-graph';
          s.onload = resolve; s.onerror = reject;
          document.head.appendChild(s);
        });
      }
      if(typeof ForceGraph === 'undefined') return;
      const el = document.getElementById('graph-container');
      if(!el) return;
      el.innerHTML = '';
      const width = el.clientWidth || 600;
      const height = 500;

      const graph = ForceGraph()(el)
        .graphData(contactGraph.value)
        .width(width).height(height)
        .nodeCanvasObject((node, ctx, globalScale) => {
          const label = node.name;
          const fontSize = node.id === '__me__' ? 14/globalScale : 11/globalScale;
          const nodeR = node.id === '__me__' ? 10 : Math.sqrt(node.val||3)*3;

          // Draw circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, nodeR, 0, 2*Math.PI, false);
          ctx.fillStyle = node.color || '#666';
          if (node.id === '__me__') {
            ctx.fillStyle = '#c8a96e';
            ctx.shadowColor = '#c8a96e';
            ctx.shadowBlur = 15;
          }
          ctx.fill();
          ctx.shadowBlur = 0;

          // Cold indicator
          if (node.days_cold && node.days_cold > 30) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, nodeR + 2, 0, 2*Math.PI, false);
            ctx.strokeStyle = '#f87171';
            ctx.lineWidth = 1.5/globalScale;
            ctx.setLineDash([3/globalScale, 3/globalScale]);
            ctx.stroke();
            ctx.setLineDash([]);
          }

          // Label
          ctx.font = `${node.id==='__me__'?'bold ':''}${fontSize}px Inter, sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillStyle = node.id === '__me__' ? '#c8a96e' : '#ececf0';
          ctx.fillText(label, node.x, node.y + nodeR + 3/globalScale);

          // Company subtitle
          if (node.company && globalScale > 0.6) {
            ctx.font = `${9/globalScale}px Inter, sans-serif`;
            ctx.fillStyle = '#4e4e66';
            ctx.fillText(node.company, node.x, node.y + nodeR + 3/globalScale + fontSize + 2/globalScale);
          }

          // Tier badge
          if (node.tier === 'A' && node.id !== '__me__') {
            ctx.font = `bold ${8/globalScale}px Inter`;
            ctx.fillStyle = '#c8a96e';
            ctx.fillText('★', node.x + nodeR, node.y - nodeR);
          }
        })
        .nodePointerAreaPaint((node, color, ctx) => {
          const nodeR = node.id === '__me__' ? 12 : Math.sqrt(node.val||3)*3 + 4;
          ctx.beginPath();
          ctx.arc(node.x, node.y, nodeR, 0, 2*Math.PI, false);
          ctx.fillStyle = color;
          ctx.fill();
        })
        .linkColor(link => 'rgba(200,169,110,0.12)')
        .linkWidth(link => 0.8)
        .linkDirectionalParticles(0)
        .backgroundColor('transparent')
        .cooldownTicks(100)
        .onNodeClick(n => {
          if (n.id === '__me__') return;
          selectContactDetail(n);
          contactView.value = 'list';
        });

      // Center on "me" node
      setTimeout(() => graph.centerAt(0, 0, 500), 200);
    }

    async function openFile(path, opts={}){currentFilePath.value=path;if(!opts.skipNav)pushNav({view:'files', detail:shortId(path), _path:path});currentFile.value=await api('/file?path='+encodeURIComponent(path));}
    const noteSourceFile = ref(null);
    async function openNoteFile(group){
      noteSourceFile.value = await api('/file?path='+encodeURIComponent(group.path));
      if(noteSourceFile.value) noteSourceFile.value._path = group.path;
    }
    // Note expand/collapse state (Set of "date|idx" keys)
    const expandedNotes = ref(new Set());
    function isNoteExpanded(date, idx){ return expandedNotes.value.has(date+'|'+idx); }
    function toggleNoteExpand(evt, date, idx){
      const key = date+'|'+idx;
      const s = new Set(expandedNotes.value);
      if (s.has(key)) {
        s.delete(key);
      } else {
        // Before expanding: measure real content height and pin it on --expanded-h
        // so the CSS max-height transition lands on the natural height (not a
        // giant fallback) and the easing curve feels silky.
        const wrap = (evt && evt.currentTarget) || null;
        if (wrap) {
          const text = wrap.querySelector('.capture-text');
          if (text) {
            const fullH = text.scrollHeight;
            if (fullH > 0) wrap.style.setProperty('--expanded-h', fullH + 'px');
          }
        }
        s.add(key);
      }
      expandedNotes.value = s;
    }
    function heatmapClick(d){ if(d.level >= 0) switchView('today'); }

    function barColor(pct){if(pct>=85)return 'good';if(pct>=60)return '';if(pct>=40)return 'warn';return 'bad';}
    function formatMsDate(isoDate) {
      const today = new Date(); const d = new Date(isoDate + 'T00:00:00');
      const todayStr = today.toISOString().slice(0,10);
      if(isoDate === todayStr) return '今天';
      const [y,m,dd] = isoDate.split('-');
      const wd = ['日','一','二','三','四','五','六'][d.getDay()];
      const thisYear = today.getFullYear().toString();
      if(y === thisYear) return `${parseInt(m)}月${parseInt(dd)}日 周${wd}`;
      return `${y}年${parseInt(m)}月${parseInt(dd)}日`;
    }
    function isCurrentMilestone(m){
      if(m.past)return false;
      const all=(planData.value?.milestones||[]).filter(x=>!x.past);
      return all.length>0 && all[0].date===m.date;
    }
    function renderNoteText(text){
      return text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<div class="note-img-wrap"><img src="$2" alt="$1" class="note-img"><a href="$2" target="_blank" class="note-img-zoom" title="查看原图">🔍</a></div>')
                 .replace(/🎤\s*\[语音\]\(([^)]+)\)/g, '<audio controls src="$1" class="note-audio"></audio>')
                 .replace(/\n/g, '<br>');
    }
    function getCatColor(catId){
      const cat = categories.value.find(c=>c.id===catId);
      return cat ? cat.color : '#666';
    }
    function getCatName(catId){
      const cat = categories.value.find(c=>c.id===catId);
      return cat ? cat.name : catId;
    }
    function tierLabel(t){ return {A:'核心',B:'活跃',C:'待激活'}[t]||t; }
    function getContactCatName(id) {
      const c = contactCategories.value.find(x=>x.id===id);
      return c ? c.name : id;
    }
    function getContactCatColor(id) {
      const c = contactCategories.value.find(x=>x.id===id);
      return c ? c.color : '#666';
    }

    // Audio device management
    const audioDevices = ref([]);
    const selectedDevice = ref(localStorage.getItem('ome365_mic') || '');
    const showAudioSettings = ref(false);

    async function loadAudioDevices(){
      try {
        await navigator.mediaDevices.getUserMedia({audio:true}).then(s => s.getTracks().forEach(t=>t.stop()));
        const devices = await navigator.mediaDevices.enumerateDevices();
        audioDevices.value = devices.filter(d => d.kind === 'audioinput');
      } catch(e) {
        showToast('无法获取音频设备列表', 'error');
      }
    }
    function selectAudioDevice(deviceId){
      selectedDevice.value = deviceId;
      localStorage.setItem('ome365_mic', deviceId);
      showAudioSettings.value = false;
      showToast('已切换麦克风');
    }

    // Voice Recording
    // ── Input target routing ──
    // All input now routes to noteText (unified notes input)
    function _target(source) { return noteText; }
    function _append(target, text) { target.value = (target.value ? target.value + '\n' : '') + text; }

    async function toggleRecording(source){
      if(isRecording.value){stopRecording();return;}
      const target = _target(source); // lock at start
      try{
        const constraints = {audio: selectedDevice.value ? {deviceId:{exact:selectedDevice.value}} : true};
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        mediaRecorder = new MediaRecorder(stream);
        recordingChunks = [];
        recordingTime.value = 0;
        mediaRecorder.ondataavailable = e => {if(e.data.size>0)recordingChunks.push(e.data);};
        mediaRecorder.onstop = async () => {
          stream.getTracks().forEach(t=>t.stop());
          clearInterval(recordingTimer);
          const blob = new Blob(recordingChunks, {type:'audio/webm'});
          const formData = new FormData();
          formData.append('file', blob, `voice_${Date.now()}.webm`);
          try {
            const res = await fetch('/api/media/upload', {method:'POST',body:formData});
            const data = await res.json();
            if(data.ok){
              _append(target, `🎤 [语音](${data.url}) (${recordingTime.value}s)`);
              showToast('录音已上传');
            } else {
              showToast(data.error || '录音上传失败', 'error');
            }
          } catch(err) {
            showToast('录音上传失败: ' + err.message, 'error');
          }
        };
        mediaRecorder.start();
        isRecording.value = true;
        recordingTimer = setInterval(()=>recordingTime.value++, 1000);
      }catch(e){
        showToast('无法访问麦克风: '+e.message, 'error');
      }
    }
    function stopRecording(){
      if(mediaRecorder && mediaRecorder.state!=='inactive'){
        mediaRecorder.stop();
        isRecording.value=false;
      }
    }

    // Speech-to-text (server-side Whisper)
    async function startSpeechToText(source) {
      if (isTranscribing.value) {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
          mediaRecorder.stop();
        }
        return;
      }
      const target = _target(source); // lock at start
      try {
        const constraints = {audio: selectedDevice.value ? {deviceId:{exact:selectedDevice.value}} : true};
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        const recorder = new MediaRecorder(stream);
        const chunks = [];
        recorder.ondataavailable = e => { if(e.data.size>0) chunks.push(e.data); };
        recorder.onstop = async () => {
          stream.getTracks().forEach(t=>t.stop());
          isTranscribing.value = false;
          if(!chunks.length) return;
          showToast('识别中...');
          const blob = new Blob(chunks, {type:'audio/webm'});
          const formData = new FormData();
          formData.append('file', blob, 'stt_' + Date.now() + '.webm');
          try {
            const res = await fetch('/api/whisper', {method:'POST', body:formData});
            const data = await res.json();
            if(data.ok && data.text) {
              _append(target, data.text);
              showToast('语音识别完成');
            } else {
              showToast(data.error || '语音识别失败', 'error');
            }
          } catch(e) {
            showToast('语音识别请求失败: ' + e.message, 'error');
          }
        };
        recorder.start();
        mediaRecorder = recorder;
        isTranscribing.value = true;
        showToast('开始录音...再次点击停止并识别');
      } catch(e) {
        showToast('无法访问麦克风: ' + e.message, 'error');
      }
    }

    // Image Upload
    async function uploadImage(e, source){
      const file = e.target.files[0];
      if(!file)return;
      const target = _target(source);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/media/upload', {method:'POST',body:formData});
        const data = await res.json();
        if(data.ok){
          _append(target, `![${file.name}](${data.url})`);
          showToast('图片已上传');
        } else {
          showToast(data.error || '图片上传失败', 'error');
        }
      } catch(err) {
        showToast('上传失败: ' + err.message, 'error');
      }
      e.target.value='';
    }

    // Image OCR — upload image, extract text via AI vision or local OCR
    const ocrLoading = ref(false);
    async function uploadImageOCR(e, source){
      const file = e.target.files[0];
      if(!file)return;
      const target = _target(source);
      ocrLoading.value = true;
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/ocr', {method:'POST', body:formData});
        const data = await res.json();
        if(data.ok && data.text) {
          _append(target, data.text);
          showToast('图片文字已提取');
        } else {
          showToast(data.error || 'OCR 识别失败', 'error');
        }
      } catch(err) {
        showToast('OCR 请求失败: ' + err.message, 'error');
      }
      ocrLoading.value = false;
      e.target.value='';
    }

    // ── Paste image from clipboard ──
    const pastedImage = ref(null);      // { file, previewUrl, source }
    const pasteProcessing = ref('');    // '' | 'ocr' | 'upload'

    function handlePaste(e) {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          if (!file) return;
          // detect source from which textarea fired the event
          const source = e.target.classList.contains('ai-bar-textarea') ? 'ai' : 'notes';
          const url = URL.createObjectURL(file);
          pastedImage.value = { file, previewUrl: url, source };
          return;
        }
      }
    }

    async function pasteAction(action) {
      const img = pastedImage.value;
      if (!img) return;
      const target = _target(img.source);
      pasteProcessing.value = action;
      const formData = new FormData();
      formData.append('file', img.file, 'paste_' + Date.now() + '.png');
      try {
        if (action === 'ocr') {
          const res = await fetch('/api/ocr', { method: 'POST', body: formData });
          const data = await res.json();
          if (data.ok && data.text) {
            _append(target, data.text);
            showToast('图片文字已提取');
          } else {
            showToast(data.error || 'OCR 识别失败', 'error');
          }
        } else {
          const res = await fetch('/api/media/upload', { method: 'POST', body: formData });
          const data = await res.json();
          if (data.ok) {
            _append(target, '![粘贴图片](' + data.url + ')');
            showToast('图片已保存');
          }
        }
      } catch (err) {
        showToast('处理失败: ' + err.message, 'error');
      }
      pasteProcessing.value = '';
      if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
      pastedImage.value = null;
    }

    function pasteDismiss() {
      if (pastedImage.value?.previewUrl) URL.revokeObjectURL(pastedImage.value.previewUrl);
      pastedImage.value = null;
    }

    // AI with Anthropic SDK
    async function askAI(){
      const text = noteText.value.trim();
      if(!text)return;
      aiLoading.value=true; aiError.value=''; aiResponse.value=''; aiFollowUps.value=[]; aiMemoryImpact.value=null;
      const res = await api('/ai',{method:'POST',body:JSON.stringify({prompt:'请帮我整理、分析或补充以下内容：',context:text})});
      aiLoading.value=false;
      if(res?.ok){
        aiResponse.value=res.response;
        if(res.follow_ups?.length) aiFollowUps.value=res.follow_ups;
        if(res.memory_impact) aiMemoryImpact.value=res.memory_impact;
        recordInteraction();
      }
      else aiError.value=res?.error||'AI请求失败';
    }
    async function resetAISession(){
      await api('/ai/reset',{method:'POST'});
      showToast('AI会话已重置');
    }

    // AI Suggestions
    const aiSuggestion = ref('');
    const aiSugLoading = ref(false);
    async function askAISuggestion(type){
      aiSugLoading.value = true; aiSuggestion.value = '';
      const prompts = {
        'today': `看一下我今天的任务和本周计划，给我建议今天最应该优先做什么，用简洁有力的语气。`,
        'next': '看一下我的365计划和最近的日志，告诉我下一个最重要的突破口在哪里，别超过3条。',
        'review': `帮我做一个简短的今日复盘，有什么做得好的、有什么需要改进的。`,
        'energy': '根据我的计划和近期节奏，给我一句打气的话，要有力量感，像教练对运动员说的那种。别太长。',
      };
      const res = await api('/ai',{method:'POST',body:JSON.stringify({prompt:prompts[type]||prompts.today, context:''})});
      aiSugLoading.value = false;
      if(res?.ok) aiSuggestion.value = res.response;
      else aiSuggestion.value = '暂时无法获取建议: ' + (res?.error||'');
    }
    const aiSuggestionHtml = computed(() => aiSuggestion.value ? marked.parse(aiSuggestion.value,{gfm:true,breaks:true}) : '');

    // User name from settings
    const userName = computed(() => settings.value.user_name || '');

    // Greeting with emotion
    const greeting = computed(() => {
      const h = new Date().getHours();
      const dn = dayNumber.value;
      const ds = daysToStart.value;
      const name = userName.value;
      if(ds > 0) return {text:`距离新征程还有 ${ds} 天，这段时间是蓄力期。`, emoji:'🌅'};
      if(h < 6) return {text:`深夜了${name ? '，' + name : ''}。休息好才能打硬仗。`, emoji:'🌙'};
      if(h < 9) return {text:`早安${name ? '，' + name : ''}。Day ${dn}，新的一天。`, emoji:'☀️'};
      if(h < 12) return {text:`上午好。专注模式，减少切换。`, emoji:'🎯'};
      if(h < 14) return {text:`午间，补充能量。`, emoji:'🍜'};
      if(h < 18) return {text:`下午了，保持节奏。`, emoji:'⚡'};
      if(h < 21) return {text:`晚间，该收网了。回顾今天的战果。`, emoji:'📋'};
      return {text:'夜深了，今天辛苦了。明天又是新的一天。', emoji:'🌃'};
    });

    // Mobile FAB
    const showFab = computed(() => view.value !== 'notes');
    function fabAction(){ switchView('notes'); }

    // Init
    // Milestone editing
    const editingMilestone = ref(null);
    const msEditForm = ref({date:'',label:'',category:'',color:''});
    function openMilestoneEdit(m) {
      editingMilestone.value = m;
      msEditForm.value = {date:m.date||'', label:m.label||'', category:m.category||'', color:m.color||'#d4b07a'};
    }
    async function saveMilestoneEdit() {
      const f = msEditForm.value;
      const orig = editingMilestone.value;
      const res = await api('/plan/milestone', {method:'PUT', body:JSON.stringify({
        original_date: orig.date, original_label: orig.label,
        date: f.date, label: f.label, category: f.category, color: f.color
      })});
      editingMilestone.value = null;
      if(res?.ok) { showToast('里程碑已更新'); await loadPlan(); }
      else showToast(res?.error||'更新失败', 'error');
    }

    // ── popstate: restore view+detail from browser history ───────
    async function restoreFromState(state){
      if(!state) state = { view: 'dashboard' };
      navRestoring = true;
      try {
        const canonView = state.view || 'dashboard';
        const subView = state.sub || canonView;
        if(view.value !== canonView){
          await switchView(subView, {skipNav:true});
        } else if(!state.detail) {
          // Same view, no detail — clear all detail selections (back to list)
          selectedReport.value = null; reportContent.value = ''; reportEditing.value = false;
          selectedInterview.value = null; interviewContent.value = '';
          currentFile.value = null; currentFilePath.value = '';
          selectedContact.value = null; editingContact.value = false;
          // Cockpit: back to home
          if(canonView === 'cockpit') cockpitGoHome({skipNav:true});
        }
        // If there's a detail, open it
        if(state.detail){
          const _p = state._path;
          const _findByIdOrPath = (list, id) => _p ? list.find(x => x.path === _p) : list.find(x => shortId(x.path) === id);
          if(state.view === 'cockpit'){
            if(state.detail.startsWith('doc:')){
              const docId = state.detail.slice(4);
              if(!reportsList.value.length) await loadReports();
              const r = _findByIdOrPath(reportsList.value, docId)
                        || (_p ? { path: _p, name: _p.split('/').pop().replace(/\.md$/,''), title: _p.split('/').pop().replace(/\.md$/,'') } : null);
              if(r){
                const blockKey = cockpitActiveBlockKey.value || '';
                if(blockKey && cockpitActiveBlockKey.value !== blockKey) await cockpitSelectBlock(blockKey, {skipNav:true});
                await cockpitOpenDoc(r, {skipNav:true});
              }
            } else if(state.detail.startsWith('block:')){
              const blockKey = state.detail.slice(6);
              if(cockpitActiveBlockKey.value !== blockKey) await cockpitSelectBlock(blockKey, {skipNav:true});
              cockpitOpenReport.value = null;
            }
          } else if(state.view === 'reports'){
            if(!reportsList.value.length) await loadReports();
            const r = _findByIdOrPath(reportsList.value, state.detail)
                      || (_p ? { path: _p, name: _p.split('/').pop().replace(/\.md$/,''), title: _p.split('/').pop().replace(/\.md$/,'') } : null);
            if(r) await openReport(r, {skipNav:true});
          } else if(state.view === 'interviews'){
            if(!interviewGroups.value.length) await loadInterviews();
            if(state.detail && state.detail.startsWith('hiring:')){
              const hid = state.detail.slice(7);
              if(!hiringList.value.length) await loadInterviews();
              const c = hiringList.value.find(x => x.id === hid) || {id: hid, name: hid};
              await openCandidate(c, {skipNav:true});
            } else {
              let found = null;
              for(const g of interviewGroups.value){
                found = (g.items||[]).find(x => _p ? x.path === _p : shortId(x.path) === state.detail);
                if(found) break;
              }
              if(!found && _p) found = { path: _p, name: _p.split('/').pop() };
              if(found) await openInterview(found, {skipNav:true});
            }
          } else if(state.view === 'files'){
            const fPath = _p || state.detail;
            await openFile(fPath, {skipNav:true});
          } else if(state.view === 'contacts'){
            await selectContactDetail({slug: state.detail}, {skipNav:true});
          }
        }
      } finally {
        navRestoring = false;
      }
    }
    window.addEventListener('popstate', (e) => {
      restoreFromState(e.state).then(() => {
        const h = buildNavHash(e.state);
        const sy = sessionStorage.getItem('ome365_sy_'+h);
        if(sy) nextTick(() => { setTimeout(() => window.scrollTo(0, parseInt(sy)), 80); });
      });
    });

    onMounted(async () => {
      loading.value = true;
      // Core data only — minimal for first paint
      // Prefer URL hash over localStorage (lets users bookmark / share links)
      let initialState = null;
      const hash = location.hash.replace(/^#\/?/, '');
      if(hash){
        const parts = hash.split('/');
        const prevState = history.state || {};
        initialState = { view: parts[0], detail: parts.slice(1).join('/') || undefined, _path: prevState._path };
      } else {
        const savedView = localStorage.getItem('ome365_view') || 'dashboard';
        initialState = { view: savedView };
      }
      await Promise.all([loadDashboard(), loadSettings(), loadTenantConfig()]);
      loading.value = false;

      // Seed history with parent state first so in-page back buttons always have somewhere to go
      const parentState = { view: initialState.view || 'dashboard' };
      history.replaceState(parentState, '', buildNavHash(parentState));

      // Restore saved view (will load its own data)
      if (parentState.view !== 'dashboard') {
        await switchView(parentState.view, {skipNav:true});
      }
      // If the initial URL had a detail, push a new history entry for it so
      // history.back() from detail → parent list (instead of leaving the site).
      if(initialState.detail){
        history.pushState(initialState, '', buildNavHash(initialState));
        await restoreFromState(initialState);
      }

      // Secondary data — non-blocking, fills badges & sidebar counts
      Promise.all([loadCategories(), loadContactCategories(), loadStreaks(), loadOnThisDay(), loadFileTree(), loadReflections(), loadInterviews(), loadReports(), loadGrowth(), loadInsights(), loadLife(), loadCockpit(), loadMemoryStats()]);

      // Start reminder & proactive timers
      requestNotifPermission();
      reminderInterval = setInterval(checkReminders, 30000); // every 30s
      checkReminders();
      // Proactive AI every 30 min (first check after 2 min)
      setTimeout(checkProactive, 120000);
      proactiveInterval = setInterval(checkProactive, 1800000);

      document.addEventListener('keydown', e => {
        if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();showSearchPanel.value=!showSearchPanel.value;if(showSearchPanel.value)nextTick(()=>{const el=document.getElementById('search-input');if(el)el.focus();});}
        if((e.metaKey||e.ctrlKey)&&e.key==='j'){e.preventDefault();goSmartNotes();}
        if(e.key==='Escape'&&showSearchPanel.value){showSearchPanel.value=false;}
      });
    });

    // Watch for graph view
    watch(contactView, async (v) => {
      if(v === 'graph'){
        await loadContactGraph();
        await nextTick();
        initGraph();
      } else if(v === 'cold'){
        await loadColdContacts();
      } else if(v === 'org'){
        // 确保 orgPersonsFor 能读到 contacts.value
        if(!contacts.value || !contacts.value.length) await loadContacts();
      }
    });

    // Watch note filter
    watch(noteCategoryFilter, () => loadNotes());

    return {
      renderMd,
      view, dash, todayData, weekData, planData, decisions, notes, fileTree, currentFile, currentFilePath, currentFileHtml,
      noteText, noteSuccess, noteTime, notePlaceholder, loading,
      sidebarCollapsed, mobileNavOpen, editingToday, todayEditRaw,
      showDecisionForm, newDecision, isMac,
      heatmapData, heatmapActive, heatmapMonths,
      planQuarter, currentPlanQ, msFilter, filteredMilestones,
      isRecording, recordingTime, aiResponse, aiResponseHtml, aiLoading, aiError,
      isTranscribing,
      navItems, mobileNavItems, currentTitle,
      dateDisplay, weekday, dayNumber, week, quarter, quarterTheme, daysToStart, yearPct, planDays,
      todayTasks, todayStats, weekTasks, weekStats, milestones, todayHtml, weekHtml,
      decisionColumns, decisionDetail, decisionDetailHtml,
      newTodayTask, newWeekTask, addingTodayTask, addingWeekTask, newTaskCategory, newTaskTime, newTaskRepeat, newTaskTargetDate, weekDayOptions,
      tasksTab, taskTabs, tasksTabTitle, unifiedTasks, unifiedTasksDone, unifiedTasksPct, unifiedSchedule, unifiedTaskGroups,
      switchTasksTab, toggleUnifiedTask, addUnifiedTask,
      editingTask, editTaskText, editTaskDesc, editTaskTime, editTaskTimeEnd, editTaskTimeRange,
      newTaskTimeEnd, newTaskTimeRange,
      timeBlocks, showTimeBlockForm, editingBlockIdx, blockForm,
      reminders, showReminderForm, newReminder, loadReminders, addReminder, deleteReminder,
      agendaItems, agendaTimed, agendaUntimed,
      omeMemoryQuery, omeMemories, omeMemoryLoading, searchOmeMemories,
      editingOmeMemId, editingOmeMemContent, startEditOmeMem, saveOmeMemEdit,
      confirmingDeleteId, askDeleteOmeMem, confirmDeleteOmeMem,
      notifEnabled, notifSound, proactiveMsg, showProactive,
      toggleNotif, setNotifSound, playSound, dismissProactive, acknowledgeProactive,
      categories, noteCategory, noteCategoryFilter, showCategoryForm, newCategory,
      contacts, contactGraph, coldContacts, selectedContact, contactDetailHtml,
      showContactForm, contactFilter, contactView, showInteractionForm,
      orgTree, orgExpandedNodes, toggleOrgNode, orgPersonExpanded, toggleOrgPersons, orgPersonsFor,
      newContact, newInteraction, contactCatLabels, contactCatColors,
      editingContact, editContactData, showMergeSelect,
      contactCategories, showContactCatForm, newContactCat,
      toastMsg, toastType, showFab, noteSourceFile,
      aiSuggestion, aiSuggestionHtml, aiSugLoading, greeting, userName,
      audioDevices, selectedDevice, showAudioSettings,
      specialDays, showDayForm, newDay, calendarMonth, calendarYear, calendarDays, calendarMonthLabel, editingDay,
      dayTypeIcons,
      fileBrowserMode, selectedFolder, selectedFolderFiles,
      settings, settingsSaved, aiTestResult, aiTestLoading, apiPresets, applyPreset,
      // v0.2: Memory
      memories, memoryIndex, showMemoryForm, editingMemory, memoryForm, memoryTypes,
      loadMemories, saveMemory, editMemoryFile, deleteMemory,
      // v0.2: Search
      searchQuery, searchResults, searchTotal, searchLoading, showSearchPanel,
      doSearch, onSearchInput, openSearchResult,
      // v0.2: Streaks & Mood
      streakData, todayMood, todayEnergy, todayFocus, moodOptions,
      setMood, setEnergy, setFocus,
      // v0.2: Reflection
      reflectResult, reflectLoadingType, reflectHtml, doReflect,
      // v0.2: On This Day
      onThisDayEntries,
      // v0.3: Growth + v0.5 Ome enhancements
      growthData, growthPhases, editingOmeProfile, omeNameEdit, omePersonalityEdit,
      growthTimeline, emotionHistory, omeMemoryStats, omeMemTypeFilter, loadMemoryStats,
      aiFollowUps, aiMemoryImpact,
      loadGrowth, startEditOmeProfile, saveOmeProfile, phaseClass, evolving, evolveError, triggerEvolve,
      // v0.8: Growth page v2
      achFilter, orbColor, orbWarmth, orbEnergy, maturityPct,
      radarVals, radarDataPts, radarPt, radarTri, radarLbl,
      moodCn, signalCn, valencePoints, valenceLine, valenceArea,
      capPhases, currentPhaseId,
      skillArr, skillNm,
      filteredAch, achUnlocked, achTotal, achClass, achIcon, achName, achDesc,
      statsChips,
      // v0.4: Note delete + Smart Input
      noteDeleteConfirm, confirmDeleteNote, executeDeleteNote,
      smartInputResult, smartInputLoading, smartInputApplying, smartInputSec,
      runSmartInput, applySmartInput, goSmartNotes,
      reflectionsList, reflectionsLoading, loadReflections,
      showGoalEdit, goalEditText, goalEditStart, goalEditDays, openGoalEdit, saveGoalEdit,
      editingMilestone, msEditForm, openMilestoneEdit, saveMilestoneEdit,
      // Functions
      loadAudioDevices, selectAudioDevice,
      switchView, navBack, toggleToday, toggleWeek, togglePlanTask,
      addTodayTask, addWeekTask, createCategory, deleteCategory,
      startEditTask, saveEditTask, cancelEditTask, deleteTask, quickDeleteTask,
      loadTimeBlocks, addTimeBlock, editTimeBlock, saveBlockForm, deleteTimeBlock,
      startEditToday, saveToday, submitNote, saveAIAsNote,
      createDecision, toggleDecisionStatus, openDecisionDetail,
      // Insights
      insightsOverview, insightsTab, insightsDays, insightsFocus, insightsLatest, insightsCards,
      insightsLoading, insightsError, insightsAskQ, insightsAskReply, insightsAskLoading, insightsAskHistory,
      loadInsights, runSynthesize, saveInsightCard, deleteInsightCard, askInsight, setInsightFollowup,
      // Life
      lifeOverview, lifeTab, lifeLoading, lifeEditDaughter, lifeDaughterEdit,
      lifeNewWeekend, lifeShowWeekendForm, lifeIdeasLoading, lifeIdeasVibe,
      lifeHealthDraft, lifeHealthNote, lifeNewRitual, lifeNewMoment, lifeShowMomentForm,
      loadLife, saveDaughter, createWeekend, toggleWeekendDone, deleteWeekend,
      generateWeekendIdeas, ideaToWeekend, saveHealth, setHealthRing,
      addRitual, toggleRitual, deleteRitual, addMoment, deleteMoment,
      // Cockpit
      cockpitData, cockpitLoading, cockpitError, cockpitActiveSection,
      expandedTrack, toggleTrack, financeTotal, northStarTiers, oneLinerParts,
      expandedChannels, isChannelExpanded, toggleChannelExpand,
      reportParsed, scrollToReportSection, scrollCockpitToStage, tocMode, cycleTocMode,
      showCockpitEditor, mdEditorContent, mdEditorDirty, mdEditorSaving,
      loadCockpit, scrollCockpitTo, openCockpitExport, downloadCockpitHtml,
      openCockpitEditor, closeCockpitEditor, saveCockpitRaw, reloadCockpitRaw,
      // Cockpit in-page navigation (W4.2 · replaces drawer)
      cockpitBlocks, cockpitPrimaryBlocks, cockpitSecondaryBlocks, cockpitFlagshipBlocks, cockpitTertiaryBlocks,
      cockpitActiveBlockKey, cockpitActiveBlockData,
      cockpitDrillPerson, cockpitCurrentDrill,
      cockpitOpenReport,
      cockpitBloomMaster, cockpitBloomChapters, cockpitBloomStageGroups, cockpitBloomKeyInsights, cockpitBloomLoading,
      forecastSelectedTrack, toggleForecastTrack,
      cockpitSelectBlock, cockpitGoHome,
      cockpitDrillTo, cockpitClearDrill,
      cockpitOpenDoc, cockpitCloseReport, cockpitOpenChapter,
      createContact, selectContactDetail, startEditContact, saveEditContact, addInteraction, mergeContacts,
      createContactCategory, deleteContactCategory,
      openFile, openNoteFile, heatmapClick,
      expandedNotes, isNoteExpanded, toggleNoteExpand,
      barColor, isCurrentMilestone, formatMsDate, renderNoteText, askAISuggestion,
      getCatColor, getCatName, tierLabel, getContactCatName, getContactCatColor, formatNoteDate, notesDisplay,
      resetAISession,
      toggleRecording, stopRecording, startSpeechToText, uploadImage, uploadImageOCR, ocrLoading,
      handlePaste, pastedImage, pasteProcessing, pasteAction, pasteDismiss,
      askAI,
      loadSpecialDays, createSpecialDay, deleteSpecialDay, prevMonth, nextMonth, openDayFormForDate, onDayTypeChange,
      loadSettings, saveSettings, testAI, toggleProxy, theme, setTheme, tenantConfig,
      fabAction, showToast,
      // Interviews & Reports
      interviewGroups, interviewCount, interviewStats, interviewCatFilter, interviewCats, filteredInterviewGroups,
      hiringList, selectedCandidate, candidateData, candidateTab, candidateRoundSubTab, candidateTranscript, candidateTransBlocks, candidateSumSections, candidateSpeakerMap, loadRoundTranscript, loadRoundSummary, openCandidate, filteredFiles,
      selectedInterview, interviewContent,
      interviewTab, interviewSummary, interviewTranscript, interviewMeta,
      interviewSummarySections, interviewTranscriptBlocks, interviewInsights, interviewSpeakers, interviewSpeakerMap, interviewTags,
      SPEAKER_COLORS, fixASR, renderMd, updateSpeakerName, shareInterview, shareToast, shareDialog, openShareDialog, checkShareSlug, registerShareSlug, copyShareUrl, toggleSlugMode, updateShare, unregisterShare,
      reportsList, selectedReport, reportContent, reportEditing, reportEditText,
      activeReportSection, visibleReportSections, currentReportSection,
      primarySections, secondarySections, tertiarySections,
      reportDrillPerson, currentDrillPerson, currentDocBreadcrumb,
      navigateToBreadcrumb, openPersonDrill, clearPersonDrill,
      reportsGroupBy, reportsSearch, reportsExpandedGroups, toggleReportsGroup,
      reportsFlatAll, reportsFiltered, reportsGrouped,
      loadInterviews, openInterview, loadReports, openReport, startEditReport, saveReport,
    };
  }
});

// ── Directive: note-clamp ─────────────────────────────────────────────
// Two jobs:
//  1) Mark wrap with `.is-clampable` when text needs >2 lines so the
//     chevron pill and fade mask appear only when there's actually more.
//  2) Keep `--expanded-h` synced to real content height so the max-height
//     CSS transition has an exact target — no fallback-to-1600px sluggishness.
// scrollHeight returns natural content height regardless of current clip,
// so we can measure without toggling classes on/off.
app.directive('note-clamp', {
  mounted(el) {
    const text = el.querySelector('.capture-text');
    if (!text) return;
    const check = () => {
      const cs = getComputedStyle(text);
      const lineH = parseFloat(cs.lineHeight) || 22;
      const fullH = text.scrollHeight;
      const twoLineH = lineH * 2;
      const overflowing = fullH > twoLineH + 2;
      el.classList.toggle('is-clampable', overflowing);
      if (overflowing) {
        el.style.setProperty('--expanded-h', fullH + 'px');
      } else {
        el.style.removeProperty('--expanded-h');
      }
    };
    requestAnimationFrame(check);
    setTimeout(check, 400);
    el._noteClampCheck = check;
    // Images may change natural height after load → remeasure
    el.querySelectorAll('img').forEach(img => {
      if (!img.complete) img.addEventListener('load', check, { once: true });
    });
    // Container width / font changes → remeasure
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => check());
      ro.observe(el);
      el._noteClampRO = ro;
    }
  },
  updated(el) {
    if (el._noteClampCheck) requestAnimationFrame(el._noteClampCheck);
  },
  unmounted(el) {
    if (el._noteClampRO) el._noteClampRO.disconnect();
  }
});

app.mount('#app');
