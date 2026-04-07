const { createApp, ref, computed, onMounted, nextTick, watch } = Vue;

createApp({
  setup() {
    const view = ref('dashboard');
    const dash = ref(null);
    const todayData = ref(null);
    const weekData = ref(null);
    const planData = ref(null);
    const decisions = ref([]);
    const notes = ref([]);
    const fileTree = ref([]);
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

    // Loading
    const loading = ref(true);

    // Task add
    const newTodayTask = ref('');
    const newWeekTask = ref('');
    const addingTodayTask = ref(false);
    const addingWeekTask = ref(false);
    const newTaskCategory = ref('');
    const newTaskTime = ref('');
    const newTaskRepeat = ref('none');

    // Task editing
    const editingTask = ref(null); // {text, description, type:'today'|'week'}
    const editTaskText = ref('');
    const editTaskDesc = ref('');

    // Categories
    const categories = ref([]);
    const noteCategory = ref('');
    const noteCategoryFilter = ref('all');
    const showCategoryForm = ref(false);
    const newCategory = ref({name:'',color:'#888',icon:'📌'});

    // Decision detail
    const decisionDetail = ref(null);

    // Contacts
    const contacts = ref([]);
    const contactGraph = ref(null);
    const coldContacts = ref([]);
    const selectedContact = ref(null);
    const showContactForm = ref(false);
    const contactFilter = ref({category:'',tier:''});
    const contactView = ref('list');
    const showInteractionForm = ref(false);
    const newContact = ref({name:'',company:'',title:'',category:'industry',tier:'B',met_context:'',background:'',location:'',wechat:'',phone:'',email:''});
    const newInteraction = ref({method:'微信',summary:''});

    // Contact editing
    const editingContact = ref(false);
    const editContactData = ref({});

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
    const reflectLoading = ref(false);

    // On This Day
    const onThisDayEntries = ref([]);

    // AI
    const aiResponse = ref('');
    const aiLoading = ref(false);
    const aiError = ref('');

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

    // File browser state
    const fileBrowserMode = ref('tree'); // tree | split
    const selectedFolder = ref(null);

    // Nav
    const navItems = computed(() => [
      {key:'dashboard',icon:'📊',label:'总览'},
      {key:'today',icon:'📅',label:'今日'},
      {key:'week',icon:'📋',label:'本周'},
      {key:'plan',icon:'🗺️',label:'地图'},
      {key:'decisions',icon:'⚡',label:'决策',badge:dash.value?.decision_count||''},
      {key:'notes',icon:'✏️',label:'速记',badge:dash.value?.notes_count||''},
      {key:'contacts',icon:'👤',label:'关系',badge:dash.value?.contact_count||''},
      {key:'memory',icon:'🧠',label:'记忆',badge:dash.value?.memory_count||''},
      {key:'days',icon:'🗓',label:'日子'},
      {key:'files',icon:'📁',label:'文件'},
      {key:'settings',icon:'⚙️',label:'设置'},
    ]);
    const mobileNavItems = [
      {key:'dashboard',icon:'📊',label:'总览'},
      {key:'today',icon:'📅',label:'今日'},
      {key:'notes',icon:'✏️',label:'速记'},
      {key:'contacts',icon:'👤',label:'关系'},
      {key:'files',icon:'📁',label:'更多'},
    ];
    const titles = {dashboard:'总览',today:'今日',week:'本周',plan:'365天作战地图',decisions:'决策日志',notes:'速记',contacts:'关系网络',memory:'记忆',days:'日子',files:'文件',settings:'设置'};
    const currentTitle = computed(() => titles[view.value]||'');
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
    const yearPct = computed(() => Math.min(100,Math.round(dayNumber.value/365*100)));

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
    const milestones = computed(() => {
      const all = dash.value?.milestones||[];
      const future = all.filter(m=>!m.past);
      const past = all.filter(m=>m.past);
      return [...past.slice(-1), ...future.slice(0,6)];
    });
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
      return html;
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

    // AI Reflection
    async function doReflect(type) {
      reflectLoading.value = true; reflectResult.value = '';
      const res = await api('/reflect',{method:'POST',body:JSON.stringify({type})});
      reflectLoading.value = false;
      if(res?.ok) reflectResult.value = res.response;
      else reflectResult.value = '反思失败: ' + (res?.error||'');
    }
    const reflectHtml = computed(() => reflectResult.value ? marked.parse(reflectResult.value,{gfm:true,breaks:true}) : '');

    // On This Day
    async function loadOnThisDay() {
      const res = await api('/on-this-day');
      if(res) onThisDayEntries.value = res.entries||[];
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
        cells.push({day:d, date:ds, isToday, events});
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

    async function switchView(key){
      view.value=key; currentFile.value=null; editingToday.value=false; showDecisionForm.value=false; decisionDetail.value=null; selectedContact.value=null; editingContact.value=false;
      localStorage.setItem('ome365_view', key);
      loading.value = true;
      switch(key){
        case 'dashboard': await Promise.all([loadDashboard(), loadStreaks(), loadOnThisDay()]); break;
        case 'today': await loadToday(); todayMood.value=dash.value?.today_mood||''; todayEnergy.value=dash.value?.today_energy||''; todayFocus.value=dash.value?.today_focus||''; break;
        case 'week': await loadWeek(); break;
        case 'plan': await loadPlan(); break;
        case 'decisions': await loadDecisions(); break;
        case 'notes': await loadNotes(); break;
        case 'contacts': await Promise.all([loadContacts(), loadColdContacts(), loadContactCategories()]); break;
        case 'memory': await loadMemories(); break;
        case 'days': await loadSpecialDays(); break;
        case 'files': await loadFileTree(); break;
        case 'settings': await loadSettings(); break;
      }
      loading.value = false;
    }

    // Actions
    async function toggleToday(t){
      t.done=!t.done;
      await api('/today/toggle',{method:'POST',body:JSON.stringify({text:t.text})});
      if(t.done && t.repeat === 'daily') showToast('已完成 · 明天自动重新出现 🔁');
      else if(t.done && t.repeat === 'weekly') showToast('已完成 · 下周自动重新出现 🔁');
      else showToast(t.done ? '已完成' : '已取消完成');
    }
    async function toggleWeek(t){
      t.done=!t.done;
      await api('/week/toggle',{method:'POST',body:JSON.stringify({text:t.text})});
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
    async function addTodayTask(){
      const text = newTodayTask.value.trim(); if(!text) return;
      const res = await api('/today/add',{method:'POST',body:JSON.stringify({text, category:newTaskCategory.value, time:newTaskTime.value, repeat:newTaskRepeat.value})});
      if(res?.ok){ newTodayTask.value=''; addingTodayTask.value=false; newTaskCategory.value=''; newTaskTime.value=''; newTaskRepeat.value='none'; await loadToday(); showToast(newTaskRepeat.value!=='none'?'任务已添加（重复）':'任务已添加'); }
    }
    async function addWeekTask(){
      const text = newWeekTask.value.trim(); if(!text) return;
      const res = await api('/week/add',{method:'POST',body:JSON.stringify({text, category:newTaskCategory.value, time:newTaskTime.value, repeat:newTaskRepeat.value})});
      if(res?.ok){ newWeekTask.value=''; addingWeekTask.value=false; newTaskCategory.value=''; newTaskTime.value=''; newTaskRepeat.value='none'; await loadWeek(); showToast('任务已添加'); }
    }

    // Task editing
    function startEditTask(task, type) {
      editingTask.value = {text: task.text, type};
      editTaskText.value = task.text;
      editTaskDesc.value = task.description || '';
    }
    async function saveEditTask() {
      if (!editingTask.value) return;
      const endpoint = editingTask.value.type === 'today' ? '/today/task' : '/week/task';
      const res = await api(endpoint, {method:'PUT', body:JSON.stringify({
        old_text: editingTask.value.text,
        new_text: editTaskText.value.trim() || editingTask.value.text,
        description: editTaskDesc.value.trim(),
      })});
      if (res?.ok) {
        editingTask.value = null;
        if (endpoint.includes('today')) await loadToday(); else await loadWeek();
        showToast('任务已更新');
      }
    }
    function cancelEditTask() { editingTask.value = null; }

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
      if(res?.ok){noteSuccess.value=true;noteTime.value=res.time;noteText.value='';await loadNotes();setTimeout(()=>noteSuccess.value=false,2000);}
    }

    async function saveAIAsNote(){
      if(!aiResponse.value) return;
      const text = '🤖 AI整理：\n' + aiResponse.value;
      const res = await api('/notes',{method:'POST',body:JSON.stringify({text})});
      if(res?.ok){ showToast('AI回复已保存为速记'); await loadNotes(); }
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
    async function selectContactDetail(c){
      const res = await api('/contacts/'+encodeURIComponent(c.slug));
      if(res) { selectedContact.value = res; editingContact.value = false; }
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

    // Enhanced graph
    function initGraph(){
      if(!contactGraph.value || typeof ForceGraph === 'undefined') return;
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

    async function openFile(path){currentFilePath.value=path;currentFile.value=await api('/file?path='+encodeURIComponent(path));}
    const noteSourceFile = ref(null);
    async function openNoteFile(group){
      noteSourceFile.value = await api('/file?path='+encodeURIComponent(group.path));
      if(noteSourceFile.value) noteSourceFile.value._path = group.path;
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
                 .replace(/🎤\s*\[语音\]\(([^)]+)\)/g, '<audio controls src="$1" class="note-audio"></audio>');
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
    async function toggleRecording(){
      if(isRecording.value){stopRecording();return;}
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
          const res = await fetch('/api/media/upload', {method:'POST',body:formData});
          const data = await res.json();
          if(data.ok){
            const entry = `🎤 [语音](${data.url}) (${recordingTime.value}s)`;
            noteText.value = (noteText.value ? noteText.value+'\n' : '') + entry;
            showToast('录音已上传');
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
    async function startSpeechToText() {
      if (isTranscribing.value) {
        // Stop recording and transcribe
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
          mediaRecorder.stop();
        }
        return;
      }
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
              noteText.value = (noteText.value ? noteText.value + '\n' : '') + data.text;
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
    async function uploadImage(e){
      const file = e.target.files[0];
      if(!file)return;
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/media/upload', {method:'POST',body:formData});
      const data = await res.json();
      if(data.ok){
        const entry = `![${file.name}](${data.url})`;
        noteText.value = (noteText.value ? noteText.value+'\n' : '') + entry;
        showToast('图片已上传');
      }
      e.target.value='';
    }

    // AI with Anthropic SDK
    async function askAI(){
      const text = noteText.value.trim();
      if(!text)return;
      aiLoading.value=true; aiError.value=''; aiResponse.value='';
      const res = await api('/ai',{method:'POST',body:JSON.stringify({prompt:'请帮我整理、分析或补充以下内容：',context:text})});
      aiLoading.value=false;
      if(res?.ok){
        aiResponse.value=res.response;
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
    onMounted(async () => {
      loading.value = true;
      await Promise.all([loadDashboard(), loadCategories(), loadContactCategories(), loadSettings(), loadStreaks(), loadOnThisDay()]);
      loading.value = false;

      // Restore saved view
      const savedView = localStorage.getItem('ome365_view');
      if (savedView && savedView !== 'dashboard') {
        await switchView(savedView);
      }

      document.addEventListener('keydown', e => {
        if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();showSearchPanel.value=!showSearchPanel.value;if(showSearchPanel.value)nextTick(()=>{const el=document.getElementById('search-input');if(el)el.focus();});}
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
      }
    });

    // Watch note filter
    watch(noteCategoryFilter, () => loadNotes());

    return {
      view, dash, todayData, weekData, planData, decisions, notes, fileTree, currentFile, currentFilePath, currentFileHtml,
      noteText, noteSuccess, noteTime, notePlaceholder, loading,
      sidebarCollapsed, mobileNavOpen, editingToday, todayEditRaw,
      showDecisionForm, newDecision, isMac,
      heatmapData, heatmapActive, heatmapMonths,
      planQuarter, currentPlanQ,
      isRecording, recordingTime, aiResponse, aiResponseHtml, aiLoading, aiError,
      isTranscribing,
      navItems, mobileNavItems, currentTitle,
      dateDisplay, weekday, dayNumber, week, quarter, quarterTheme, daysToStart, yearPct,
      todayTasks, todayStats, weekTasks, weekStats, milestones, todayHtml, weekHtml,
      decisionColumns, decisionDetail, decisionDetailHtml,
      newTodayTask, newWeekTask, addingTodayTask, addingWeekTask, newTaskCategory, newTaskTime, newTaskRepeat,
      editingTask, editTaskText, editTaskDesc,
      categories, noteCategory, noteCategoryFilter, showCategoryForm, newCategory,
      contacts, contactGraph, coldContacts, selectedContact, contactDetailHtml,
      showContactForm, contactFilter, contactView, showInteractionForm,
      newContact, newInteraction, contactCatLabels, contactCatColors,
      editingContact, editContactData,
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
      reflectResult, reflectLoading, reflectHtml, doReflect,
      // v0.2: On This Day
      onThisDayEntries,
      // Functions
      loadAudioDevices, selectAudioDevice,
      switchView, toggleToday, toggleWeek, togglePlanTask,
      addTodayTask, addWeekTask, createCategory, deleteCategory,
      startEditTask, saveEditTask, cancelEditTask,
      startEditToday, saveToday, submitNote, saveAIAsNote,
      createDecision, toggleDecisionStatus, openDecisionDetail,
      createContact, selectContactDetail, startEditContact, saveEditContact, addInteraction,
      createContactCategory, deleteContactCategory,
      openFile, openNoteFile, heatmapClick,
      barColor, isCurrentMilestone, formatMsDate, renderNoteText, askAISuggestion,
      getCatColor, getCatName, tierLabel, getContactCatName, getContactCatColor, formatNoteDate, notesDisplay,
      resetAISession,
      toggleRecording, stopRecording, startSpeechToText, uploadImage, askAI,
      loadSpecialDays, createSpecialDay, deleteSpecialDay, prevMonth, nextMonth, openDayFormForDate, onDayTypeChange,
      loadSettings, saveSettings, testAI, toggleProxy,
      fabAction, showToast,
    };
  }
}).mount('#app');
