// Renderiza video.html cuadro por cuadro y lo pasa a ffmpeg.
// Uso: node promo/renderizar.js <v> <salida.mp4> [fps]       (página servida en http://localhost:8765)
//      node promo/renderizar.js <v> <carpeta> --frames 1,3.5,8   (solo cuadros sueltos en PNG)
const { chromium } = require('playwright');
const { spawn } = require('child_process');

(async () => {
  const [v, out, third, fourth] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5 });
  await p.goto(`http://localhost:8765/promo/video.html?v=${v}`, { waitUntil: 'networkidle' });
  await p.evaluate(() => window.ready);
  const stage = await p.$('#stage');

  if (third === '--frames') {
    for (const t of fourth.split(',').map(Number)) {
      await p.evaluate(t => window.seek(t), t);
      await stage.screenshot({ path: `${out}/v${v}_${t}.png` });
    }
    await b.close();
    return;
  }

  const fps = +(third || 30);
  const dur = await p.evaluate(() => window.DURATION);
  const n = Math.round(dur * fps);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let i = 0; i < n; i++) {
    await p.evaluate(t => window.seek(t), i / fps);
    const buf = await stage.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`v${v}: ${i}/${n}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await b.close();
})();
