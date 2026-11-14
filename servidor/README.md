# Servidor de comentarios de Nico World

Flask mínimo con SQLite. La página (`../index.html`) vive en GitHub Pages con el dominio propio; este servidor vive en PythonAnywhere y solo guarda las opiniones.

| Ruta | Qué hace |
|---|---|
| `GET /api/comentarios` | Comentarios **aprobados**, los más nuevos primero (máx. 200) |
| `POST /api/comentarios` | Recibe un comentario. Queda **pendiente** hasta que lo apruebes |
| `GET /admin` | Panel privado (usuario y contraseña) para aprobar o borrar |
| `POST /webhook/github` | Despliegue automático, igual que AstroWorld |

Protecciones: solo acepta envíos desde tu dominio (CORS), bloquea correos, teléfonos y enlaces, máximo 5 comentarios cada 10 minutos y 20 al día por visitante, campo trampa para robots, y no guarda la IP (solo un resumen que cambia cada día y vive en memoria).

## Probar en tu computadora

```bash
pip install -r requirements.txt pytest
python -m pytest -q
ADMIN_PASSWORD=prueba ALLOWED_ORIGINS=http://localhost:8080 python flask_app.py
```

Panel en http://localhost:5001/admin (usuario `admin`).

## Publicar en PythonAnywhere (plan gratuito)

1. Crea una cuenta *Beginner* nueva (cada cuenta gratuita admite una sola app web; si ya usas la tuya para AstroWorld o FlagWorld, crea otra, por ejemplo `nicoworld`).
2. Consola **Bash**:
   ```bash
   git clone https://github.com/cviteri2/nicouniverse.git
   ```
   El repositorio es privado: usa un *fine-grained token* de GitHub con *Contents: Read-only* como contraseña.
3. Pestaña **Web** → *Add a new web app* → *Manual configuration* → la versión de Python más reciente.
4. Abre el **WSGI configuration file**, borra todo y deja esto (cambia `TU_USUARIO`, el dominio y la contraseña):
   ```python
   import os, sys
   os.environ['ADMIN_PASSWORD'] = 'UNA_CONTRASEÑA_LARGA'
   os.environ['ALLOWED_ORIGINS'] = 'https://tudominio.com,https://www.tudominio.com'
   # Despliegue automático (opcional, ver README de AstroWorld):
   # os.environ['GITHUB_WEBHOOK_SECRET'] = 'EL_SECRETO'
   # os.environ['WSGI_FILE'] = '/var/www/TU_USUARIO_pythonanywhere_com_wsgi.py'
   path = '/home/TU_USUARIO/nicouniverse/servidor'
   if path not in sys.path:
       sys.path.insert(0, path)
   from flask_app import app as application
   ```
5. Activa **Force HTTPS** y pulsa **Reload**.
6. Comprueba: `https://TU_USUARIO.pythonanywhere.com/api/comentarios` debe responder `{"comentarios": []}`.
7. En `../index.html` cambia la línea `var API = '';` por `var API = 'https://TU_USUARIO.pythonanywhere.com';`, haz commit y push. La nota amarilla de «Vista previa» desaparece sola.

**Revisar comentarios:** entra a `https://TU_USUARIO.pythonanywhere.com/admin`, usuario `admin` y tu contraseña. Los aprobados aparecen en la página en menos de un minuto.

**Copia de seguridad:** la base está en `servidor/data/comentarios.db` (no se sube a GitHub). Descárgala de vez en cuando desde la pestaña *Files*.

**Importante:** en el plan gratuito la app se apaga si no la renuevas cada 3 meses (*Web* → *Run until 3 months from today*). Si se apaga, la página sigue funcionando pero la sección de opiniones muestra «No se pudieron cargar los comentarios».
