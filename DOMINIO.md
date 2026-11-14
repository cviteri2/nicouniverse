# Conectar Nico World a un dominio de GoDaddy (GitHub Pages)

Cambia `tudominio.com` por el dominio real.

## 1. Activar GitHub Pages
1. Junta la rama de trabajo en `main` (pull request y *Merge*).
2. GitHub → repositorio `nicouniverse` → *Settings → Pages*.
3. *Source*: **Deploy from a branch** · Rama **main** · Carpeta **/ (root)** · *Save*.
4. Espera 1–2 minutos: la página queda en `https://cviteri2.github.io/nicouniverse/`.

> GitHub Pages en un repositorio **privado** exige un plan de pago (GitHub Pro). Con el plan gratuito, el repositorio tiene que ser público (*Settings → General → Change visibility*).

## 2. Verificar el dominio en GitHub (recomendado)
*Settings de tu cuenta* (no del repo) → *Pages* → *Add a domain* → escribe `tudominio.com`. GitHub te da un registro **TXT** (`_github-pages-challenge-cviteri2`). Créalo en GoDaddy (paso 3) y pulsa *Verify*. Esto evita que otra persona use tu dominio en GitHub.

## 3. DNS en GoDaddy
GoDaddy → *Mis productos* → dominio → *DNS* → *Administrar DNS*.

1. Borra los registros **A** con nombre `@` que apunten a «Parked» / página de GoDaddy, y desactiva *Forwarding* si está activo.
2. Agrega 4 registros **A**, nombre `@`, TTL 1 hora:
   - `185.199.108.153`
   - `185.199.109.153`
   - `185.199.110.153`
   - `185.199.111.153`
3. (Opcional, IPv6) 4 registros **AAAA**, nombre `@`:
   - `2606:50c0:8000::153`
   - `2606:50c0:8001::153`
   - `2606:50c0:8002::153`
   - `2606:50c0:8003::153`
4. Registro **CNAME**: nombre `www` → valor `cviteri2.github.io` (edita el `www` que ya existe; no puede haber dos).

## 4. Dominio en el repositorio
*Settings → Pages → Custom domain* → `tudominio.com` → *Save*. GitHub crea el archivo `CNAME` en el repositorio.

## 5. HTTPS
Cuando el chequeo DNS salga en verde (de minutos a 24 h), marca **Enforce HTTPS**. El certificado puede tardar hasta 1 hora más.

## Comprobar
```bash
dig tudominio.com +short
dig www.tudominio.com +short
```
El primero debe mostrar las cuatro IP `185.199.x.153`; el segundo, `cviteri2.github.io`.
