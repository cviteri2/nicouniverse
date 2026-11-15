# Videos promocionales

Tres videos verticales (1080×1920, 30 fps, ~25 s) con texto y música, sin voz. Todos empiezan con una barra de búsqueda que escribe `nicouniverse.com` y despliega las secciones de la página, incluidas las tres apps.

| Archivo | Contenido |
|---|---|
| `videos/nicouniverse-1-recorrido.mp4` | Recorrido por la página hasta los tres mundos y los botones para entrar |
| `videos/nicouniverse-2-tres-mundos.mp4` | Las tarjetas de AstroWorld, FlagWorld y Humanity World con su botón «Jugar» |
| `videos/nicouniverse-3-lugar-seguro.mp4` | Datos de la portada, compromisos (sin cuentas, sin internet, cualquier pantalla) y «Elige tu mundo» |

Las imágenes son capturas reales de `index.html`; los textos sobreimpresos citan textos de la página. La música es original, generada con `musica.py`.

## Volver a generarlos
```bash
python3 -m http.server 8765 --bind 127.0.0.1 &      # desde la raíz del repositorio
node promo/capturar.js promo/build                   # captura la página
for v in 1 2 3; do node promo/renderizar.js $v promo/build/s$v.mp4; done
python3 promo/musica.py 1 25 promo/build/m1.wav     # 2 → 26 s, 3 → 25 s
ffmpeg -i promo/build/s1.mp4 -i promo/build/m1.wav -c:v copy -c:a aac -shortest promo/videos/nicouniverse-1-recorrido.mp4
```
