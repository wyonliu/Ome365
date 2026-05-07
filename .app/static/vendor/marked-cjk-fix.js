/*!
 * marked-cjk-fix.js · 中文 markdown 渲染兜底（v4·Proxy 方案）
 *
 * 修复 CommonMark 在中文标点紧贴粗体符号时不渲染的问题。
 * 例如：建造行业的[STAR][STAR]「汽车」重新发明[STAR][STAR]（对标X） 不渲染。
 *
 * 实现：Proxy 拦截 marked.parse / parseInline，在输出 HTML 后做 post-process
 * （跳过 code/pre 段），把残留的粗体/斜体序列转成 strong/em 标签。
 *
 * marked v15 的 parse 是不可写 getter，必须用 Proxy 才能 patch。
 */
(function () {
  if (typeof marked === 'undefined') {
    console.warn('[marked-cjk-fix] marked not loaded');
    return;
  }
  if (typeof Proxy === 'undefined') {
    console.warn('[marked-cjk-fix] Proxy not supported');
    return;
  }

  function postFixCJK(html) {
    if (!html || typeof html !== 'string') return html;
    const stash = [];
    let s = html
      .replace(/<pre[\s\S]*?<\/pre>/gi, (m) => { stash.push(m); return '\x00CK' + (stash.length - 1) + '\x00'; })
      .replace(/<code[\s\S]*?<\/code>/gi, (m) => { stash.push(m); return '\x00CK' + (stash.length - 1) + '\x00'; });
    s = s.replace(/\*\*([^*\n<>][^*\n]*?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^\s*<>])\*([^\s*\n<>][^*\n<>]*?)\*(?=[^*]|$)/g, '$1<em>$2</em>');
    s = s.replace(/\x00CK(\d+)\x00/g, (_, i) => stash[+i]);
    return s;
  }

  const _origMarked = marked;
  const wrappedParse = function () { return postFixCJK(_origMarked.parse.apply(_origMarked, arguments)); };
  const wrappedInline = function () { return postFixCJK(_origMarked.parseInline.apply(_origMarked, arguments)); };

  // 用 Proxy 拦截属性访问，所有 marked.parse(...) 调用都返回 wrapper
  const proxied = new Proxy(_origMarked, {
    get(target, prop, receiver) {
      if (prop === 'parse') return wrappedParse;
      if (prop === 'parseInline') return wrappedInline;
      if (prop === '_cjkFixed') return true;
      if (prop === '_cjkPostFix') return postFixCJK;
      return Reflect.get(target, prop, receiver);
    },
    has(target, prop) {
      if (prop === '_cjkFixed' || prop === '_cjkPostFix') return true;
      return Reflect.has(target, prop);
    }
  });

  // 把全局 marked 替换为 Proxy 版本
  try {
    window.marked = proxied;
    if (typeof globalThis !== 'undefined') globalThis.marked = proxied;
    console.log('[marked-cjk-fix] v4 Proxy patched');
  } catch (e) {
    console.error('[marked-cjk-fix] failed to replace marked:', e);
  }
})();
