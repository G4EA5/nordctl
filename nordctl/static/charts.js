/* nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a */
/** nordctl — shared canvas/SVG charts for dashboard visualizations */
(function (global) {
  "use strict";

  const resizeBound = new WeakSet();

  function pushBuffer(buf, val, maxLen) {
    const n = Number(val);
    if (!Number.isFinite(n)) return buf;
    buf.push(n);
    while (buf.length > maxLen) buf.shift();
    return buf;
  }

  function setupCanvas(canvas, cssH) {
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const dpr = global.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || canvas.parentElement?.clientWidth || 320;
    const cssHeight = cssH || parseInt(canvas.getAttribute("height"), 10) || 120;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w: cssW, h: cssHeight };
  }

  function bindResize(canvas, drawFn) {
    if (!canvas || resizeBound.has(canvas)) return;
    resizeBound.add(canvas);
    global.addEventListener("resize", () => drawFn(), { passive: true });
  }

  function fmtShort(n, unit) {
    if (!Number.isFinite(n)) return "—";
    if (unit === "pct") return `${Math.round(n)}%`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
    return String(Math.round(n * 10) / 10);
  }

  function drawGrid(ctx, pad, plotW, plotH, gridLines, maxVal, fmtY) {
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    ctx.fillStyle = "rgba(255,255,255,0.35)";
    ctx.font = "10px ui-monospace, monospace";
    for (let i = 0; i <= gridLines; i++) {
      const y = pad.t + (plotH * i) / gridLines;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + plotW, y);
      ctx.stroke();
      if (i === 0 && fmtY) ctx.fillText(fmtY(maxVal), pad.l + 2, y + 10);
    }
  }

  function drawMultiLine(canvas, series, opts = {}) {
    if (!canvas) return;
    const draw = () => {
      const setup = setupCanvas(canvas, opts.height || 140);
      if (!setup) return;
      const { ctx, w, h } = setup;
      const pad = opts.pad || { l: 8, r: 8, t: 10, b: 22 };
      const plotW = w - pad.l - pad.r;
      const plotH = h - pad.t - pad.b;
      ctx.clearRect(0, 0, w, h);
      const all = series.flatMap((s) => s.values || []);
      const maxVal = Math.max(opts.minMax || 1, ...(all.length ? all : [0]), opts.peak || 0);
      drawGrid(ctx, pad, plotW, plotH, opts.gridLines || 4, maxVal, opts.fmtY);
      const cap = opts.maxPoints || Math.max(...series.map((s) => (s.values || []).length), 2);
      series.forEach((s) => {
        const vals = s.values || [];
        if (vals.length < 2) return;
        ctx.strokeStyle = s.color || "#5eead4";
        ctx.lineWidth = s.width || 2;
        ctx.lineJoin = "round";
        ctx.beginPath();
        vals.forEach((v, i) => {
          const x = pad.l + (plotW * i) / Math.max(1, cap - 1);
          const y = pad.t + plotH - (Math.min(v, maxVal) / maxVal) * plotH;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        const last = vals[vals.length - 1];
        const lx = pad.l + (plotW * (vals.length - 1)) / Math.max(1, cap - 1);
        const ly = pad.t + plotH - (Math.min(last, maxVal) / maxVal) * plotH;
        ctx.fillStyle = s.color || "#5eead4";
        ctx.beginPath();
        ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
        ctx.fill();
      });
      const empty = opts.emptyEl;
      if (empty) empty.classList.toggle("hidden", all.length >= 2);
    };
    bindResize(canvas, draw);
    draw();
  }

  function drawSparkline(canvas, values, color, opts = {}) {
    if (!canvas || !values?.length) return;
    const draw = () => {
      const setup = setupCanvas(canvas, opts.height || 22);
      if (!setup) return;
      const { ctx, w, h } = setup;
      ctx.clearRect(0, 0, w, h);
      const max = Math.max(...values, opts.minMax || 1);
      const pad = 2;
      ctx.strokeStyle = color || "#5eead4";
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.beginPath();
      values.forEach((v, i) => {
        const x = pad + ((w - pad * 2) * i) / Math.max(1, values.length - 1);
        const y = h - pad - (v / max) * (h - pad * 2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      if (opts.fill) {
        const lastX = pad + ((w - pad * 2) * (values.length - 1)) / Math.max(1, values.length - 1);
        ctx.lineTo(lastX, h);
        ctx.lineTo(pad, h);
        ctx.closePath();
        ctx.fillStyle = opts.fill;
        ctx.fill();
      }
    };
    bindResize(canvas, draw);
    draw();
  }

  function drawBars(canvas, items, opts = {}) {
    if (!canvas) return;
    const draw = () => {
      const setup = setupCanvas(canvas, opts.height || 160);
      if (!setup) return;
      const { ctx, w, h } = setup;
      ctx.clearRect(0, 0, w, h);
      const rows = items || [];
      if (!rows.length) return;
      const pad = { l: 4, r: 8, t: 12, b: 28 };
      const plotW = w - pad.l - pad.r;
      const plotH = h - pad.t - pad.b;
      const max = Math.max(1, ...rows.map((r) => r.value || 0));
      const gap = opts.gap || 6;
      const barW = Math.max(8, (plotW - gap * (rows.length - 1)) / rows.length);
      ctx.font = "10px ui-sans-serif, system-ui, sans-serif";
      rows.forEach((row, i) => {
        const bh = ((row.value || 0) / max) * plotH;
        const x = pad.l + i * (barW + gap);
        const y = pad.t + plotH - bh;
        const r = Math.min(4, barW / 3);
        ctx.fillStyle = row.color || "#5eead4";
        ctx.globalAlpha = row.muted ? 0.45 : 0.92;
        if (typeof ctx.roundRect === "function") {
          ctx.beginPath();
          ctx.roundRect(x, y, barW, bh, [r, r, 0, 0]);
          ctx.fill();
        } else {
          ctx.fillRect(x, y, barW, bh);
        }
        ctx.globalAlpha = 1;
        ctx.fillStyle = "rgba(255,255,255,0.55)";
        const lbl = String(row.label || "").slice(0, 10);
        ctx.fillText(lbl, x + barW / 2 - ctx.measureText(lbl).width / 2, h - 8);
        if (opts.showValues) {
          ctx.fillStyle = "rgba(255,255,255,0.75)";
          const vt = String(row.value);
          ctx.fillText(vt, x + barW / 2 - ctx.measureText(vt).width / 2, y - 4);
        }
      });
    };
    bindResize(canvas, draw);
    draw();
  }

  function drawDonut(canvas, segments, opts = {}) {
    if (!canvas) return;
    const draw = () => {
      const setup = setupCanvas(canvas, opts.height || 140);
      if (!setup) return;
      const { ctx, w, h } = setup;
      ctx.clearRect(0, 0, w, h);
      const total = segments.reduce((s, seg) => s + (seg.value || 0), 0);
      if (total <= 0) return;
      const cx = w / 2;
      const cy = h / 2;
      const r = Math.min(w, h) * 0.36;
      const thick = opts.thickness || 14;
      let start = -Math.PI / 2;
      segments.forEach((seg) => {
        const slice = ((seg.value || 0) / total) * Math.PI * 2;
        ctx.strokeStyle = seg.color || "#5eead4";
        ctx.lineWidth = thick;
        ctx.beginPath();
        ctx.arc(cx, cy, r, start, start + slice);
        ctx.stroke();
        start += slice;
      });
      if (opts.centerText) {
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        ctx.font = `700 ${opts.centerSize || 18}px ui-sans-serif, system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(opts.centerText, cx, cy - (opts.centerSub ? 6 : 0));
        if (opts.centerSub) {
          ctx.font = "10px ui-sans-serif, system-ui";
          ctx.fillStyle = "rgba(255,255,255,0.45)";
          ctx.fillText(opts.centerSub, cx, cy + 12);
        }
      }
    };
    bindResize(canvas, draw);
    draw();
  }

  function setSvgRing(circleEl, pct, opts = {}) {
    if (!circleEl) return;
    const r = opts.r || 52;
    const c = 2 * Math.PI * r;
    circleEl.style.strokeDasharray = `${c}`;
    const p = Math.max(0, Math.min(100, Number(pct) || 0));
    circleEl.style.strokeDashoffset = `${c * (1 - p / 100)}`;
    if (opts.color) circleEl.style.stroke = opts.color;
  }

  function renderHBarList(container, items, opts = {}) {
    if (!container) return;
    const rows = items || [];
    if (!rows.length) {
      container.innerHTML = `<p class="muted chart-empty-hint">${opts.empty || "No data yet."}</p>`;
      return;
    }
    const max = Math.max(1, ...rows.map((r) => r.value || 0));
    container.innerHTML = rows.map((row) => {
      const pct = Math.round(((row.value || 0) / max) * 100);
      return `<div class="chart-hbar-row">
        <span class="chart-hbar-label">${row.label || "—"}</span>
        <div class="chart-hbar-track"><span class="chart-hbar-fill" style="width:${pct}%;background:${row.color || "#5eead4"}"></span></div>
        <span class="chart-hbar-val">${row.display ?? row.value ?? ""}</span>
      </div>`;
    }).join("");
  }

  function bucketByDay(events, days = 7) {
    const now = Date.now();
    const buckets = Array.from({ length: days }, (_, i) => ({
      label: "",
      value: 0,
      ok: 0,
      fail: 0,
    }));
    for (let i = 0; i < days; i++) {
      const d = new Date(now - (days - 1 - i) * 86400000);
      buckets[i].label = d.toLocaleDateString([], { weekday: "short" });
    }
    (events || []).forEach((e) => {
      const ts = e.ts ? new Date(e.ts).getTime() : 0;
      if (!ts) return;
      const dayIdx = Math.floor((ts - (now - days * 86400000)) / 86400000);
      if (dayIdx < 0 || dayIdx >= days) return;
      buckets[dayIdx].value += 1;
      if (e.ok) buckets[dayIdx].ok += 1;
      else buckets[dayIdx].fail += 1;
    });
    return buckets;
  }

  function bucketLogsByHour(entries, hours = 24) {
    const now = Date.now();
    const buckets = Array.from({ length: hours }, () => 0);
    (entries || []).forEach((e) => {
      const ts = e.ts ? new Date(e.ts).getTime() : 0;
      if (!ts || ts < now - hours * 3600000) return;
      const idx = Math.floor((ts - (now - hours * 3600000)) / 3600000);
      if (idx >= 0 && idx < hours) buckets[idx] += 1;
    });
    return buckets;
  }

  function parseProtocolCounts(summaryLines) {
    const counts = { TCP: 0, UDP: 0, ICMP: 0, Other: 0 };
    (summaryLines || []).forEach((ln) => {
      const s = String(ln);
      if (/\bTCP\b/i.test(s)) counts.TCP += 1;
      else if (/\bUDP\b/i.test(s)) counts.UDP += 1;
      else if (/\bICMP\b/i.test(s)) counts.ICMP += 1;
      else counts.Other += 1;
    });
    return Object.entries(counts)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => ({ label: k, value: v, color: k === "TCP" ? "#22d3ee" : k === "UDP" ? "#c084fc" : k === "ICMP" ? "#fbbf24" : "#94a3b8" }));
  }

  global.NordctlCharts = {
    pushBuffer,
    setupCanvas,
    bindResize,
    drawMultiLine,
    drawSparkline,
    drawBars,
    drawDonut,
    setSvgRing,
    renderHBarList,
    bucketByDay,
    bucketLogsByHour,
    parseProtocolCounts,
    fmtShort,
  };
})(window);
