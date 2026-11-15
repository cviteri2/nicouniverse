// Captura la página real (index.html) en tamaño de celular para usarla en los videos.
// Uso: node promo/capturar.js <carpeta_salida>   (con la página servida en http://localhost:8765)
const { chromium } = require('playwright');

(async () => {
  const out = process.argv[2];
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5 });
  await p.goto('http://localhost:8765/index.html', { waitUntil: 'networkidle' });
  // Recorre la página para que aparezca el contenido que se revela al hacer scroll.
  for (let y = 0; y < 20000; y += 400) {
    await p.evaluate(y => window.scrollTo(0, y), y);
    await p.waitForTimeout(60);
  }
  await p.evaluate(() => window.scrollTo(0, 0));
  // Oculta el botón flotante de música para que no tape el contenido.
  await p.addStyleTag({ content: '#music-btn{display:none!important}' });
  await p.waitForTimeout(800);
  await p.screenshot({ path: out + '/pagina.png', fullPage: true });
  const info = await p.evaluate(() => {
    const r = e => { const b = e.getBoundingClientRect(); return { x: Math.round(b.left), y: Math.round(b.top + scrollY), w: Math.round(b.width), h: Math.round(b.height) }; };
    return {
      alto: document.documentElement.scrollHeight,
      secciones: [...document.querySelectorAll('[id]')].filter(e => e.offsetHeight > 100).map(e => ({ id: e.id, ...r(e) })),
      mundos: [...document.querySelectorAll('.world')].map(e => ({ nombre: e.querySelector('h3') && e.querySelector('h3').textContent, ...r(e) })),
      botones: [...document.querySelectorAll('a.btn')].map(e => ({ texto: e.textContent.trim(), ...r(e) })),
    };
  });
  require('fs').writeFileSync(out + '/pagina.json', JSON.stringify(info, null, 1));
  console.log(JSON.stringify(info));
  await b.close();
})();
