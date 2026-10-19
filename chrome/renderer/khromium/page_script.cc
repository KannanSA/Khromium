// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/renderer/khromium/page_script.h"

#include "base/json/json_writer.h"
#include "base/values.h"

namespace khromium {

std::string HeuristicScanScript() {
  // The isolated world owns a short-lived MutationObserver. Hooking
  // blink::MutationObserver in core/dom would run for every node mutation in
  // every document. C++ also schedules a second pass two seconds later, which
  // reads whatever the observer recorded.
  return R"JS((() => {
  const MAX = 8000;
  const phrases = [
    'disable your ad blocker',
    'disable adblock',
    'ad blocker detected',
    'adblock detected',
    'whitelist this site',
    'turn off your ad blocker',
    'please disable your ad blocker',
    'adblock plus'
  ];
  function classText(el) {
    return typeof el.className === 'string' ? el.className : '';
  }
  function textOf(el) {
    return (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 400);
  }
  function selectorFor(el) {
    if (el.id && /^[A-Za-z][\w:.-]*$/.test(el.id)) {
      return '#' + CSS.escape(el.id);
    }
    const classes = classText(el).trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (classes.length) {
      return el.tagName.toLowerCase() + classes.map(c => '.' + CSS.escape(c)).join('');
    }
    return el.tagName.toLowerCase();
  }
  function consider(el, hits) {
    if (!el || el.nodeType !== 1 || hits.length >= 8) return;
    if (el === document.body || el === document.documentElement) return;
    let style;
    try { style = getComputedStyle(el); } catch (e) { return; }
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth || 1;
    const vh = window.innerHeight || 1;
    const z = parseInt(style.zIndex, 10);
    const fixed = style.position === 'fixed' || style.position === 'sticky';
    const covers = rect.width >= vw * 0.6 && rect.height >= vh * 0.4;
    const high = !Number.isNaN(z) && z >= 1000;
    const text = textOf(el);
    const lower = text.toLowerCase();
    const phrase = phrases.some(p => lower.includes(p));
    const bait = /ad-banner|adsbox|ad-container|banner-ad|anti-adblock|adblock/i
      .test((el.id || '') + ' ' + classText(el));
    if (!(phrase || (fixed && covers && (high || phrase || bait)) || (bait && (fixed || high)))) {
      return;
    }
    const selector = selectorFor(el);
    if (hits.some(hit => hit.selector === selector && hit.text === text.slice(0, 240))) return;
    hits.push({
      selector: selector,
      text: text.slice(0, 240),
      position: style.position,
      zIndex: style.zIndex,
      phrase: phrase,
      fixed: fixed,
      covers: covers,
      high: high,
      bait: bait
    });
  }
  const state = globalThis.__khromium || (globalThis.__khromium = {hits: [], installed: false});
  if (!state.installed && document.documentElement) {
    state.installed = true;
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        for (const node of record.addedNodes) {
          if (!node || node.nodeType !== 1) continue;
          consider(node, state.hits);
          if (node.querySelectorAll && state.hits.length < 8) {
            const inner = node.querySelectorAll('div,section,aside,dialog');
            const limit = Math.min(inner.length, 12);
            for (let i = 0; i < limit; i++) consider(inner[i], state.hits);
          }
          if (state.hits.length >= 8) {
            observer.disconnect();
            return;
          }
        }
      }
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
    setTimeout(() => observer.disconnect(), 12000);
  }
  const hits = state.hits.slice();
  const nodes = document.body ? document.body.querySelectorAll('*') : [];
  let scanned = 0;
  for (const el of nodes) {
    if (++scanned > 2500 || hits.length >= 8) break;
    consider(el, hits);
  }
  function locked(el) {
    if (!el) return false;
    const style = getComputedStyle(el);
    return /hidden|clip/.test(style.overflow + ' ' + style.overflowY);
  }
  const scrollLock = locked(document.documentElement) || locked(document.body);
  const scripts = [];
  for (const s of document.scripts) {
    const src = s.src || '';
    const inline = (s.textContent || '').slice(0, 240);
    const blob = (src + ' ' + inline).toLowerCase();
    if (/fuckadblock|blockadblock|antiadblock|adblock-detector|adblockdetect|adbdetect/.test(blob)) {
      scripts.push((src || inline).slice(0, 200));
    }
    if (scripts.length >= 3) break;
  }
  const strong = hits.some(hit => hit.phrase || (hit.fixed && hit.covers && (hit.high || hit.bait)) || (hit.bait && (hit.fixed || hit.high)));
  if (!strong && !scripts.length) return '';
  let raw = JSON.stringify({
    url: String(location.href || '').slice(0, 200),
    scroll_lock: scrollLock,
    hits: hits,
    scripts: scripts
  });
  if (raw.length > MAX) raw = raw.slice(0, MAX);
  return raw;
})())JS";
}

std::string CleanupScript(const std::vector<std::string>& selectors,
                          bool restore_scroll) {
  base::ListValue list;
  for (const std::string& selector : selectors) {
    list.Append(selector);
  }
  const std::string json = base::WriteJson(list).value_or("[]");
  std::string script = "(() => {\n  const selectors = " + json +
                       ";\n  const restore = " +
                       (restore_scroll ? "true" : "false") +
                       ";\n";
  script += R"JS(  let hidden = 0;
  for (const sel of selectors) {
    let nodes = [];
    try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
    for (const node of nodes) {
      if (!node || node === document.body || node === document.documentElement) continue;
      if (hidden >= 8) break;
      node.style.setProperty('display', 'none', 'important');
      node.setAttribute('data-khromium-hidden', '1');
      hidden++;
    }
  }
  if (restore) {
    for (const el of [document.documentElement, document.body]) {
      if (!el) continue;
      el.style.setProperty('overflow', 'visible', 'important');
      el.style.setProperty('overflow-y', 'visible', 'important');
    }
  }
  return true;
})())JS";
  return script;
}

}  // namespace khromium
