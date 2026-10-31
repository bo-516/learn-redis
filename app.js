/* Redis 学习手册 —— 纯静态单页应用，无需构建 */
(function () {
  "use strict";
  var CH = window.CHAPTERS || [];
  var CMDS = window.CMDS || [];
  var $app = document.getElementById("app");
  var LS = "learn-redis:";
  function load(k, d) { try { var v = localStorage.getItem(LS + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function save(k, v) { try { localStorage.setItem(LS + k, JSON.stringify(v)); } catch (e) {} }

  // ---------- 数据整理 ----------
  var QUIZ = [], BANK = [];
  CH.forEach(function (c) {
    (c.quiz || []).forEach(function (q, i) { q.id = c.id + "-q" + (i + 1); q.code = c.code + "-Q" + pad(i + 1); q.cat = c.id; QUIZ.push(q); });
    (c.bank || []).forEach(function (q, i) { q.id = c.id + "-b" + (i + 1); q.code = c.code + "-" + pad(i + 1); q.cat = c.id; BANK.push(q); });
  });
  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  var TYPE = { single: "单选", multi: "多选", tf: "判断", fill: "填空" };
  var LV = { 1: "基础", 2: "进阶", 3: "深入" };

  var st = {
    quizRes: load("quiz", {}),       // id -> {ok:bool, pick:any}
    mastered: load("mastered", {}),  // bank id -> 1
    open: {},
    f: { q: "", lv: "all", ty: "all", hot: false, hide: false, wrong: false }
  };

  // ---------- 简易 Markdown ----------
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function inline(s) {
    var codes = [];
    s = s.replace(/`([^`]+)`/g, function (_, c) { codes.push(c); return "\u0000" + (codes.length - 1) + "\u0000"; });
    s = esc(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
         .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
         .replace(/(^|[\s（(])(https?:\/\/[^\s<)）]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    return s.replace(/\u0000(\d+)\u0000/g, function (_, i) { return "<code>" + esc(codes[+i]) + "</code>"; });
  }
  function md(src) {
    if (!src) return "";
    var lines = String(src).replace(/\r/g, "").split("\n"), out = [], i = 0;
    while (i < lines.length) {
      var l = lines[i];
      if (/^```/.test(l)) {
        var buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++; out.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>"); continue;
      }
      if (/^\s*$/.test(l)) { i++; continue; }
      var h = /^(#{2,4})\s+(.*)$/.exec(l);
      if (h) { var lv = Math.min(h[1].length + 1, 4); out.push("<h" + lv + ">" + inline(h[2]) + "</h" + lv + ">"); i++; continue; }
      if (/^\|/.test(l)) {
        var rows = [];
        while (i < lines.length && /^\|/.test(lines[i])) { rows.push(lines[i]); i++; }
        var cells = function (r) { return r.replace(/^\||\|$/g, "").split("|").map(function (c) { return c.trim(); }); };
        var html = "<table><thead><tr>" + cells(rows[0]).map(function (c) { return "<th>" + inline(c) + "</th>"; }).join("") + "</tr></thead><tbody>";
        rows.slice(2).forEach(function (r) { html += "<tr>" + cells(r).map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>"; });
        out.push(html + "</tbody></table>"); continue;
      }
      if (/^>\s?/.test(l)) {
        var bq = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) { bq.push(lines[i].replace(/^>\s?/, "")); i++; }
        out.push("<blockquote>" + inline(bq.join(" ")) + "</blockquote>"); continue;
      }
      if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
        var ordered = /^\s*\d+\./.test(l), items = [];
        while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
          var t = lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""); i++;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) { t += " " + lines[i].trim(); i++; }
          items.push("<li>" + inline(t) + "</li>");
        }
        out.push((ordered ? "<ol>" : "<ul>") + items.join("") + (ordered ? "</ol>" : "</ul>")); continue;
      }
      var p = [l]; i++;
      while (i < lines.length && lines[i].trim() && !/^(```|#{2,4}\s|\||>|\s*([-*]|\d+\.)\s)/.test(lines[i])) { p.push(lines[i]); i++; }
      out.push("<p>" + inline(p.join(" ")) + "</p>");
    }
    return out.join("\n");
  }
  window.__md = md;

  // ---------- 通用 ----------
  function toast(t) { var d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.appendChild(d); setTimeout(function () { d.remove(); }, 1400); }
  function copy(text) {
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { toast("已复制"); }, function () { toast("复制失败"); });
  }
  function catName(id) { for (var i = 0; i < CH.length; i++) if (CH[i].id === id) return CH[i]; return {}; }
  function bar(label, done, total) {
    var pct = total ? Math.round(done * 100 / total) : 0;
    return '<div class="stat"><b>' + label + '</b><div class="num">' + done + " / " + total + ' <small style="color:var(--mut)">' + pct + '%</small></div><div class="bar"><i style="width:' + pct + '%"></i></div></div>';
  }
  function stats() {
    var answered = 0, right = 0, ms = 0;
    QUIZ.forEach(function (q) { var r = st.quizRes[q.id]; if (r) { answered++; if (r.ok) right++; } });
    BANK.forEach(function (q) { if (st.mastered[q.id]) ms++; });
    return '<div class="stats">' + bar("练习题已作答", answered, QUIZ.length) + bar("练习题答对", right, QUIZ.length) + bar("面试题已掌握", ms, BANK.length) + "</div>";
  }
  function match(q, text) {
    if (!st.f.q) return true;
    var k = st.f.q.toLowerCase();
    return text.toLowerCase().indexOf(k) >= 0;
  }

  // ---------- 首页 ----------
  function home() {
    var cards = CH.map(function (c, i) {
      return '<div class="rcard"><span class="cat-code" style="align-self:flex-start">阶段 ' + c.stage + " · " + c.code + '</span><h3>' + (i + 1) + ". " + esc(c.name) + '</h3><p>' + esc(c.desc) + '</p><span class="meta">' + c.quiz.length + " 道练习 · " + c.bank.length + ' 道面试题</span><div class="actions"><a class="btn pri" href="#/learn/' + c.id + '">读课程</a><a class="btn" href="#/quiz/' + c.id + '">做练习</a><a class="btn" href="#/bank/' + c.id + '">面试题</a></div></div>';
    }).join("");
    return '<div class="page"><section class="masthead"><div class="eyebrow">LEARN REDIS · 小白 → 高手</div><h1>Redis 学习手册</h1><p class="lede">一套照着走就能从零到能在生产里用好 Redis 的学习路线：' + CH.length + " 章课程讲清原理和命令，" + QUIZ.length + " 道练习题（单选 / 多选 / 判断 / 命令填空）每题都附正误解析，" + BANK.length + " 道面试题给出标准答案与深入讲解，外加 " + CMDS.reduce(function (a, g) { return a + g.items.length; }, 0) + ' 条常用命令速查。内容以 Redis Open Source 8.x（截至 2026 年 10 月最新稳定版 8.10.x）为准，兼容 7.x 的知识点会单独说明。进度只保存在当前浏览器。</p>' + stats() + '</section>' +
      '<h2>学习路线</h2><div class="road">' + cards + '</div>' +
      '<div class="lesson md">' + md(window.HOME_EXTRA || "") + '</div><footer class="foot">Redis 学习手册 · 内容参考 redis.io 官方文档整理 · 纯静态页面，可直接部署到 GitHub Pages</footer></div>';
  }

  // ---------- 课程 ----------
  function learn(sel) {
    var side = '<aside class="side"><h4>课程目录 · ' + CH.length + ' 章</h4>' + CH.map(function (c) {
      return '<a href="#/learn/' + c.id + '" class="' + (sel === c.id ? "on" : "") + '"><span>' + esc(c.name) + '</span><span class="n">' + c.code + "</span></a>";
    }).join("") + '<div class="note">每章读完后去做对应练习，答错的题会自动进入「只看错题」。</div></aside>';
    var list = sel ? CH.filter(function (c) { return c.id === sel; }) : CH;
    var idx = CH.indexOf(list[0]);
    var main = list.map(function (c) {
      return '<section class="cat" id="sec-' + c.id + '"><header class="cat-head"><span class="cat-code">阶段 ' + c.stage + " · " + c.code + '</span><h2>' + esc(c.name) + '</h2><p class="cat-desc">' + esc(c.desc) + '</p></header><article class="lesson md">' + md(c.lesson) + '</article><div class="actions"><a class="btn pri" href="#/quiz/' + c.id + '">做本章练习（' + c.quiz.length + ' 题）</a><a class="btn" href="#/bank/' + c.id + '">本章面试题（' + c.bank.length + ' 题）</a></div></section>';
    }).join("");
    if (sel) {
      var nav = '<div class="actions" style="justify-content:space-between;margin-top:10px">' + (idx > 0 ? '<a class="btn" href="#/learn/' + CH[idx - 1].id + '">← ' + esc(CH[idx - 1].name) + "</a>" : "<span></span>") + (idx < CH.length - 1 ? '<a class="btn" href="#/learn/' + CH[idx + 1].id + '">' + esc(CH[idx + 1].name) + " →</a>" : "") + "</div>";
      main += nav;
    }
    return '<div class="page"><section class="masthead"><div class="eyebrow">LESSONS</div><h1>课程</h1><p class="lede">按阶段读：入门 → 核心 → 进阶 → 高手。每章都有可直接在 redis-cli 里敲的命令示例。</p></section><div class="layout">' + side + "<main>" + main + "</main></div></div>";
  }

  // ---------- 工具栏 ----------
  function toolbar(kind, all) {
    var f = st.f, cnt = function (lv) { return all.filter(function (q) { return q.level === lv; }).length; };
    var chip = function (key, val, label, c) { return '<button type="button" class="chip" data-f="' + key + '" data-v="' + val + '" aria-pressed="' + (String(f[key]) === String(val)) + '">' + label + (c != null ? '<span class="c">' + c + "</span>" : "") + "</button>"; };
    var tog = function (key, label) { return '<button type="button" class="chip" data-t="' + key + '" aria-pressed="' + !!f[key] + '">' + label + "</button>"; };
    var h = '<div class="toolbar"><div class="tb-row"><label class="search"><span>🔍</span><input id="sq" type="search" value="' + esc(f.q) + '" placeholder="' + (kind === "quiz" ? "搜索题目或解析，例如 SETNX、AOF、跨槽" : kind === "bank" ? "搜索面试题，例如 雪崩、COW、Redlock、热 Key" : "搜索命令或说明，例如 ZADD、过期、SCAN") + '" autocomplete="off" spellcheck="false" aria-label="搜索"><kbd>/</kbd></label>';
    if (kind !== "cmd") {
      h += '<div class="chips">' + chip("lv", "all", "全部") + chip("lv", 1, "基础", cnt(1)) + chip("lv", 2, "进阶", cnt(2)) + chip("lv", 3, "深入", cnt(3)) + "</div>";
      if (kind === "quiz") h += '<div class="chips">' + chip("ty", "all", "全部题型") + ["single", "multi", "tf", "fill"].map(function (t) { return chip("ty", t, TYPE[t], all.filter(function (q) { return q.type === t; }).length); }).join("") + "</div>";
      h += '<div class="chips">' + tog("hot", "只看高频") + (kind === "quiz" ? tog("wrong", "只看错题") + tog("hide", "隐藏已答对") : tog("hide", "隐藏已掌握")) + "</div>";
    }
    h += '<div class="actions"><button type="button" class="btn" data-act="expand">展开全部</button><button type="button" class="btn" data-act="collapse">折叠全部</button>' + (kind === "quiz" ? '<button type="button" class="btn" data-act="reset">重置练习进度</button>' : kind === "bank" ? '<button type="button" class="btn" data-act="resetb">清空掌握标记</button>' : "") + "</div></div>";
    return h + '<p class="tb-status" id="tbs"></p></div>';
  }

  function sidebar(kind, counts, note) {
    return '<aside class="side" id="side"><h4>章节目录 · ' + CH.length + " 章</h4>" + CH.map(function (c) {
      return '<a href="#/' + kind + "/" + c.id + '" data-sec="' + c.id + '"><span>' + esc(c.name) + '</span><span class="n">' + (counts[c.id] || 0) + "</span></a>";
    }).join("") + '<div class="note">' + note + "</div></aside>";
  }

  // ---------- 练习题 ----------
  function quizFilter(q) {
    var f = st.f, r = st.quizRes[q.id];
    if (f.lv !== "all" && q.level !== +f.lv) return false;
    if (f.ty !== "all" && q.type !== f.ty) return false;
    if (f.hot && !q.hot) return false;
    if (f.wrong && !(r && !r.ok)) return false;
    if (f.hide && r && r.ok) return false;
    return match(q, q.q + " " + (q.code || "") + " " + (q.snippet || "") + " " + (q.options || []).join(" ") + " " + q.explain);
  }
  function answerText(q) {
    if (q.type === "single") return String.fromCharCode(65 + q.answer) + ". " + q.options[q.answer];
    if (q.type === "multi") return q.answer.map(function (i) { return String.fromCharCode(65 + i); }).join("、");
    if (q.type === "tf") return q.answer ? "正确" : "错误";
    return q.answer[0];
  }
  function quizItem(q) {
    var r = st.quizRes[q.id], open = st.open[q.id];
    var status = r ? (r.ok ? '<span class="ty" style="color:var(--ok)">✓ 答对</span>' : '<span class="ty" style="color:var(--bad)">✗ 答错</span>') : "";
    var h = '<details class="q' + (r && r.ok ? " done" : "") + '" id="' + q.id + '"' + (open ? " open" : "") + '><summary><span class="qid">' + q.code + '</span><span class="lv lv' + q.level + '">' + LV[q.level] + '</span><span class="ty">' + TYPE[q.type] + '</span><span class="qt">' + inline(q.q) + "</span>" + (q.hot ? '<span class="hot">高频</span>' : "") + status + '<span class="qside"><button type="button" class="copy" data-copy="' + q.id + '" title="复制题目，方便发给 AI 讨论">复制</button></span></summary>';
    if (open) h += '<div class="q-body">' + quizBody(q, r) + "</div>";
    return h + "</details>";
  }
  function quizBody(q, r) {
    var h = q.snippet ? md("```\n" + q.snippet + "\n```") : "";
    var revealed = !!r;
    if (q.type === "fill") {
      h += '<div class="fill"><input data-fill="' + q.id + '" placeholder="在这里输入命令或答案，回车提交" value="' + esc(r ? r.pick || "" : "") + '"' + (revealed ? " disabled" : "") + "></div>";
    } else {
      var opts = q.type === "tf" ? ["正确", "错误"] : q.options;
      var multi = q.type === "multi";
      h += '<ul class="opts">' + opts.map(function (o, i) {
        var val = q.type === "tf" ? (i === 0) : i;
        var isAns = q.type === "single" ? q.answer === i : multi ? q.answer.indexOf(i) >= 0 : q.answer === val;
        var picked = r && (multi ? (r.pick || []).indexOf(i) >= 0 : r.pick === val);
        var cls = revealed ? (isAns ? " right" : picked ? " wrong" : "") : "";
        return '<li><label class="opt' + cls + '"><input type="' + (multi ? "checkbox" : "radio") + '" name="o-' + q.id + '" value="' + i + '"' + (picked ? " checked" : "") + (revealed ? " disabled" : "") + '><span class="k">' + (q.type === "tf" ? "" : String.fromCharCode(65 + i) + ".") + "</span><span>" + inline(o) + "</span></label></li>";
      }).join("") + "</ul>";
    }
    if (!revealed) {
      h += '<div class="actions"><button type="button" class="btn pri" data-submit="' + q.id + '">提交答案</button><button type="button" class="btn" data-reveal="' + q.id + '">不会，直接看解析</button></div>';
    } else {
      h += '<div class="verdict ' + (r.ok ? "ok" : "no") + '">' + (r.ok ? "回答正确 ✓" : r.gave ? "已查看答案" : "回答错误 ✗") + "　正确答案：" + inline(answerText(q)) + (q.type === "fill" && q.answer.length > 1 ? '<br><small style="font-weight:400">也接受：' + q.answer.slice(1).map(function (a) { return "<code>" + esc(a) + "</code>"; }).join(" ") + "</small>" : "") + "</div>";
      h += '<div class="explain md"><b>解析</b>' + md(q.explain) + '</div><div class="actions"><button type="button" class="btn" data-redo="' + q.id + '">重做这题</button></div>';
    }
    return h;
  }
  function norm(s) { return String(s).trim().replace(/\s+/g, " ").replace(/;$/, "").toLowerCase(); }
  function grade(q, pick) {
    if (q.type === "single" || q.type === "tf") return pick === q.answer;
    if (q.type === "multi") { var a = q.answer.slice().sort().join(","), b = (pick || []).slice().sort().join(","); return a === b; }
    return q.answer.some(function (a) { return norm(a) === norm(pick); });
  }

  // ---------- 面试题 ----------
  function bankFilter(q) {
    var f = st.f;
    if (f.lv !== "all" && q.level !== +f.lv) return false;
    if (f.hot && !q.hot) return false;
    if (f.hide && st.mastered[q.id]) return false;
    return match(q, q.title + " " + q.code + " " + q.answer + " " + (q.deep || ""));
  }
  function bankItem(q) {
    var done = !!st.mastered[q.id], open = st.open[q.id];
    var h = '<details class="q' + (done ? " done" : "") + '" id="' + q.id + '"' + (open ? " open" : "") + '><summary><span class="qid">' + q.code + '</span><span class="lv lv' + q.level + '">' + LV[q.level] + '</span><span class="qt">' + inline(q.title) + "</span>" + (q.hot ? '<span class="hot">高频</span>' : "") + '<span class="qside"><button type="button" class="copy" data-copy="' + q.id + '" title="复制题目，方便发给 AI 讨论">复制</button><button type="button" class="mark" data-mark="' + q.id + '" aria-pressed="' + done + '" title="' + (done ? "取消已掌握" : "标记为已掌握") + '">✓</button></span></summary>';
    if (open) h += '<div class="q-body"><div class="md ans">' + md(q.answer) + "</div>" + (q.deep ? '<section class="deep"><h3>深入讲解</h3><div class="md">' + md(q.deep) + "</div></section>" : "") + "</div>";
    return h + "</details>";
  }

  // ---------- 列表页 ----------
  function listPage(kind, sel) {
    var all = kind === "quiz" ? QUIZ : BANK;
    var counts = {}; all.forEach(function (q) { counts[q.cat] = (counts[q.cat] || 0) + 1; });
    var title = kind === "quiz" ? "练习题" : "面试题库";
    var lede = kind === "quiz" ? "单选、多选、判断、命令填空四种题型。先自己作答再提交，每题都解释「为什么对、其余选项为什么错」。答错的题可以用「只看错题」反复刷。" : "按章节整理的高频面试题。先自己口述答案，再展开对照标准答案和「深入讲解」。点击右侧圆形按钮标记已掌握。";
    var note = kind === "quiz" ? "按 <kbd>/</kbd> 搜索；填空题按 <kbd>Enter</kbd> 提交。进度只保存在当前浏览器。" : "按 <kbd>/</kbd> 搜索。点击题目右侧的圆形按钮标记已掌握。进度只保存在当前浏览器。";
    return '<div class="page"><section class="masthead"><div class="eyebrow">' + (kind === "quiz" ? "PRACTICE" : "INTERVIEW BANK") + "</div><h1>" + title + '</h1><p class="lede">' + lede + "</p>" + stats() + "</section>" + toolbar(kind, all) + '<div class="layout">' + sidebar(kind, counts, note) + '<main id="list"></main></div><footer class="foot">Redis 学习手册 · 共 ' + all.length + " 题</footer></div>";
  }
  function renderList(kind) {
    var all = kind === "quiz" ? QUIZ : BANK, flt = kind === "quiz" ? quizFilter : bankFilter, item = kind === "quiz" ? quizItem : bankItem;
    var shown = all.filter(flt), html = "";
    CH.forEach(function (c) {
      var qs = shown.filter(function (q) { return q.cat === c.id; });
      if (!qs.length) return;
      var tot = all.filter(function (q) { return q.cat === c.id; });
      var lc = function (l) { return tot.filter(function (q) { return q.level === l; }).length; };
      html += '<section class="cat" id="sec-' + c.id + '" data-sec="' + c.id + '"><header class="cat-head"><span class="cat-code">' + c.code + "</span><h2>" + esc(c.name) + '</h2><p class="cat-desc">' + esc(c.desc) + '</p><p class="cat-meta">' + tot.length + " 题 · 基础 " + lc(1) + " · 进阶 " + lc(2) + " · 深入 " + lc(3) + "</p></header>" + qs.map(item).join("") + "</section>";
    });
    if (!shown.length) html = '<div class="empty"><b>没有符合条件的题目</b>换个关键词，或者放宽筛选。<div><button type="button" class="btn" data-act="clear">清除全部筛选</button></div></div>';
    document.getElementById("list").innerHTML = html;
    var filtered = st.f.q || st.f.lv !== "all" || st.f.ty !== "all" || st.f.hot || st.f.hide || st.f.wrong;
    document.getElementById("tbs").innerHTML = (filtered ? "显示 " + shown.length + " / " + all.length + " 题 " : "共 " + all.length + " 题 ") + (filtered ? '<button type="button" class="link" data-act="clear">清除筛选</button>' : "");
    return shown;
  }

  // ---------- 命令手册 ----------
  function cmdPage() {
    var counts = {}; CMDS.forEach(function (g) { counts[g.id] = g.items.length; });
    var side = '<aside class="side" id="side"><h4>命令分组</h4>' + CMDS.map(function (g) { return '<a href="#sec-' + g.id + '" data-sec="' + g.id + '" data-jump="1"><span>' + esc(g.name) + '</span><span class="n">' + g.items.length + "</span></a>"; }).join("") + '<div class="note">每条都给出语法、时间复杂度提示和一个可直接粘贴到 redis-cli 的例子。</div></aside>';
    return '<div class="page"><section class="masthead"><div class="eyebrow">CHEATSHEET</div><h1>命令手册</h1><p class="lede">按数据结构和用途分组的常用命令速查。完整参考见 https://redis.io/docs/latest/commands/</p></section>' + toolbar("cmd", []) + '<div class="layout">' + side + '<main id="list" class="cmdgrid"></main></div></div>';
  }
  function renderCmds() {
    var html = "", n = 0, tot = 0;
    CMDS.forEach(function (g) {
      tot += g.items.length;
      var its = g.items.filter(function (c) { return match(c, c.cmd + " " + c.desc + " " + c.ex); });
      if (!its.length) return; n += its.length;
      html += '<section class="cat" id="sec-' + g.id + '" data-sec="' + g.id + '"><header class="cat-head"><h2>' + esc(g.name) + '</h2><p class="cat-desc">' + esc(g.desc || "") + "</p></header>" + its.map(function (c, i) {
        var id = "cmd-" + g.id + "-" + i, open = st.open[id];
        return '<details class="q" id="' + id + '"' + (open ? " open" : "") + '><summary><span class="qt">' + esc(c.cmd) + '</span><span class="ty">' + esc(c.cx || "") + '</span></summary>' + (open ? '<div class="q-body md">' + md(c.desc + "\n\n```\n" + c.ex + "\n```") + "</div>" : "") + "</details>";
      }).join("") + "</section>";
    });
    if (!n) html = '<div class="empty"><b>没有匹配的命令</b></div>';
    document.getElementById("list").innerHTML = html;
    document.getElementById("tbs").textContent = st.f.q ? "显示 " + n + " / " + tot + " 条" : "共 " + tot + " 条";
  }

  // ---------- 路由 ----------
  var cur = { r: "", kind: "" };
  function route() {
    var parts = (location.hash.replace(/^#\/?/, "") || "").split("/");
    var r = parts[0] || "home", sub = parts[1];
    if (/^sec-/.test(r)) return; // 页内锚点
    document.querySelectorAll("#nav a").forEach(function (a) { a.classList.toggle("on", a.dataset.r === r); });
    var chg = r !== cur.r;
    cur = { r: r, kind: r };
    if (r === "learn") { $app.innerHTML = learn(sub); document.title = "课程 · Redis 学习手册"; }
    else if (r === "quiz" || r === "bank") {
      if (chg || !document.getElementById("list")) { $app.innerHTML = listPage(r, sub); }
      renderList(r);
      document.title = (r === "quiz" ? "练习题" : "面试题库") + " · Redis 学习手册";
      if (sub) { var el = document.getElementById("sec-" + sub); if (el) { el.scrollIntoView(); return; } }
    }
    else if (r === "cmd") { $app.innerHTML = cmdPage(); renderCmds(); document.title = "命令手册 · Redis 学习手册"; }
    else { cur.r = "home"; $app.innerHTML = home(); document.title = "Redis 学习手册 · 从小白到高手"; }
    if (chg) window.scrollTo(0, 0);
  }
  function rerender() {
    if (cur.r === "quiz" || cur.r === "bank") renderList(cur.r);
    else if (cur.r === "cmd") renderCmds();
  }
  function refreshItem(id) {
    var el = document.getElementById(id); if (!el) return;
    var q = QUIZ.concat(BANK).filter(function (x) { return x.id === id; })[0]; if (!q) return;
    var tmp = document.createElement("div"); tmp.innerHTML = cur.r === "quiz" ? quizItem(q) : bankItem(q);
    el.replaceWith(tmp.firstChild);
    var s = document.querySelector(".masthead .stats"); if (s) s.outerHTML = stats();
  }

  // ---------- 事件 ----------
  document.addEventListener("toggle", function (e) {
    var d = e.target; if (!d.matches || !d.matches("details.q")) return;
    var was = !!st.open[d.id];
    if (d.open === was) return;
    if (d.open) st.open[d.id] = 1; else delete st.open[d.id];
    if (d.open && !d.querySelector(".q-body")) refreshItem(d.id) || (cur.r === "cmd" && renderCmds());
  }, true);

  document.addEventListener("click", function (e) {
    var t = e.target.closest("button,a"); if (!t) return;
    var ds = t.dataset;
    if (ds.f) { st.f[ds.f] = ds.v === "all" ? "all" : ds.v; document.querySelectorAll('[data-f="' + ds.f + '"]').forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.v === ds.v); }); rerender(); }
    else if (ds.t) { st.f[ds.t] = !st.f[ds.t]; t.setAttribute("aria-pressed", st.f[ds.t]); rerender(); }
    else if (ds.act === "expand") { document.querySelectorAll("#list details.q").forEach(function (d) { st.open[d.id] = 1; }); rerender(); }
    else if (ds.act === "collapse") { st.open = {}; rerender(); }
    else if (ds.act === "clear") { st.f = { q: "", lv: "all", ty: "all", hot: false, hide: false, wrong: false }; route(); var i = document.getElementById("sq"); if (i) i.value = ""; $app.innerHTML = ""; cur.r = ""; route(); }
    else if (ds.act === "reset") { if (confirm("确定清空全部练习题作答记录？")) { st.quizRes = {}; save("quiz", {}); cur.r = ""; route(); } }
    else if (ds.act === "resetb") { if (confirm("确定清空全部「已掌握」标记？")) { st.mastered = {}; save("mastered", {}); cur.r = ""; route(); } }
    else if (ds.mark) { e.preventDefault(); e.stopPropagation(); if (st.mastered[ds.mark]) delete st.mastered[ds.mark]; else st.mastered[ds.mark] = 1; save("mastered", st.mastered); refreshItem(ds.mark); }
    else if (ds.copy) {
      e.preventDefault(); e.stopPropagation();
      var q = QUIZ.concat(BANK).filter(function (x) { return x.id === ds.copy; })[0];
      var txt = "【Redis · " + catName(q.cat).name + " · " + q.code + "】\n" + (q.q || q.title) + (q.snippet ? "\n" + q.snippet : "") + (q.options ? "\n" + q.options.map(function (o, i) { return String.fromCharCode(65 + i) + ". " + o; }).join("\n") : "");
      copy(txt);
    }
    else if (ds.submit) {
      var q2 = QUIZ.filter(function (x) { return x.id === ds.submit; })[0], pick;
      if (q2.type === "fill") { pick = document.querySelector('[data-fill="' + q2.id + '"]').value; if (!pick.trim()) return toast("先输入答案"); }
      else {
        var ch = Array.prototype.map.call(document.querySelectorAll('input[name="o-' + q2.id + '"]:checked'), function (x) { return +x.value; });
        if (!ch.length) return toast("先选择一个选项");
        pick = q2.type === "multi" ? ch : q2.type === "tf" ? ch[0] === 0 : ch[0];
      }
      st.quizRes[q2.id] = { ok: grade(q2, pick), pick: pick }; save("quiz", st.quizRes); refreshItem(q2.id);
    }
    else if (ds.reveal) { st.quizRes[ds.reveal] = { ok: false, gave: true, pick: null }; save("quiz", st.quizRes); refreshItem(ds.reveal); }
    else if (ds.redo) { delete st.quizRes[ds.redo]; save("quiz", st.quizRes); refreshItem(ds.redo); }
    else if (ds.jump) { e.preventDefault(); var s = document.getElementById("sec-" + ds.sec); if (s) s.scrollIntoView({ behavior: "smooth" }); }
    else if (t.closest("#side") && t.dataset.sec && cur.r === t.getAttribute("href").split("/")[1]) {
      e.preventDefault(); var s2 = document.getElementById("sec-" + t.dataset.sec); if (s2) s2.scrollIntoView({ behavior: "smooth" }); history.replaceState(null, "", t.getAttribute("href"));
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { var i = document.getElementById("sq"); if (i) { e.preventDefault(); i.focus(); } }
    if (e.key === "Enter" && e.target.dataset && e.target.dataset.fill) { var b = document.querySelector('[data-submit="' + e.target.dataset.fill + '"]'); if (b) b.click(); }
    if (e.key === "Escape" && e.target.id === "sq") { e.target.value = ""; st.f.q = ""; rerender(); e.target.blur(); }
  });
  var timer;
  document.addEventListener("input", function (e) { if (e.target.id === "sq") { clearTimeout(timer); timer = setTimeout(function () { st.f.q = e.target.value.trim(); rerender(); }, 120); } });

  // 主题
  var MODES = ["system", "light", "dark"], NAMES = { system: "跟随系统", light: "浅色", dark: "深色" };
  var mode = load("theme-mode", "system");
  function applyTheme() {
    var dark = mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { if (mode === "system") localStorage.removeItem(LS + "theme"); else localStorage.setItem(LS + "theme", mode); } catch (e) {}
    var b = document.getElementById("theme"); b.textContent = (mode === "dark" ? "🌙 " : mode === "light" ? "☀️ " : "🖥 ") + NAMES[mode]; b.title = "配色：" + NAMES[mode] + "（点击切换）";
  }
  document.getElementById("theme").onclick = function () { mode = MODES[(MODES.indexOf(mode) + 1) % 3]; save("theme-mode", mode); applyTheme(); };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
  applyTheme();
  var top = document.getElementById("totop");
  window.addEventListener("scroll", function () { top.classList.toggle("show", scrollY > 600); });
  top.onclick = function () { scrollTo({ top: 0, behavior: "smooth" }); };

  window.addEventListener("hashchange", route);
  route();
})();
