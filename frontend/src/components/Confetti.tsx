/** A short burst of confetti, drawn on a temporary canvas. Skipped for people who prefer reduced motion. */
export function celebrate(intensity = 1) {
  if (typeof window === "undefined") return;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const canvas = document.createElement("canvas");
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  Object.assign(canvas.style, { position: "fixed", inset: "0", width: "100vw", height: "100vh", pointerEvents: "none", zIndex: "100" });
  canvas.setAttribute("aria-hidden", "true");
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) { canvas.remove(); return; }
  ctx.scale(dpr, dpr);
  const colors = ["#0e9a69", "#3d6fd6", "#d97f06", "#7f5bd1", "#e6b422", "#e85d75"];
  const W = window.innerWidth, H = window.innerHeight;
  const n = Math.round(140 * intensity);
  const parts = Array.from({ length: n }, (_, i) => {
    const fromLeft = i % 2 === 0;
    const angle = (fromLeft ? -60 : -120) * (Math.PI / 180) + (Math.random() - 0.5) * 0.9;
    const speed = 9 + Math.random() * 9;
    return {
      x: fromLeft ? W * 0.08 : W * 0.92, y: H * 0.75,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      w: 6 + Math.random() * 6, h: 3 + Math.random() * 4, r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
      c: colors[i % colors.length],
    };
  });
  const start = performance.now();
  const frame = (t: number) => {
    const age = (t - start) / 1000;
    ctx.clearRect(0, 0, W, H);
    for (const p of parts) {
      p.vy += 0.32; p.vx *= 0.99; p.vy *= 0.99;
      p.x += p.vx; p.y += p.vy; p.r += p.vr;
      ctx.save();
      ctx.globalAlpha = Math.max(0, 1 - Math.max(0, age - 1.6) / 0.8);
      ctx.translate(p.x, p.y); ctx.rotate(p.r);
      ctx.fillStyle = p.c; ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }
    if (age < 2.4) requestAnimationFrame(frame);
    else canvas.remove();
  };
  requestAnimationFrame(frame);
}
