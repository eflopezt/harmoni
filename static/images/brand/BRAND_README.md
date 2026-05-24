# Harmoni · Logo Pack

Assets de marca para harmoni.pe. Todos los archivos están en `brand/`.

## Archivos disponibles

### Logo original (PNG con transparencia)
- `harmoni-logo-original.png` — lockup con fondo teal oscuro (1188×258)
- `harmoni-logo-transparent.png` — lockup completo, fondo transparente (1188×258)
- `harmoni-mark-original.png` — solo isotipo (la H + wave), fondo teal oscuro (380×258)
- `harmoni-mark-transparent.png` — solo isotipo, fondo transparente (380×258)

### Lockup horizontal · transparent · sized
> Logo completo (H + wordmark "Harmoni"). Úsalo en header, hero, footer, firmas de correo.

- `png/harmoni-logo-400.png`
- `png/harmoni-logo-800.png`
- `png/harmoni-logo-1200.png`
- `png/harmoni-logo-1600.png`

### Isotipo (mark) · transparent · sized
> Solo la H+wave. Úsalo en favicon móvil, avatares, sellos pequeños, OG image.

- `png/harmoni-mark-128.png`
- `png/harmoni-mark-256.png`
- `png/harmoni-mark-512.png`
- `png/harmoni-mark-1024.png`

### Favicon · square con fondo teal oscuro
> Cuadrado redondeado con padding y fondo de marca. Listo para `<link rel="icon">`.

- `png/harmoni-favicon-32.png`   ← favicon clásico
- `png/harmoni-favicon-64.png`
- `png/harmoni-favicon-180.png`  ← apple-touch-icon
- `png/harmoni-favicon-256.png`
- `png/harmoni-favicon-512.png`  ← PWA manifest

---

## Implementación en tu landing

### `<head>`
```html
<!-- Favicons -->
<link rel="icon" type="image/png" sizes="32x32"  href="/brand/png/harmoni-favicon-32.png" />
<link rel="icon" type="image/png" sizes="64x64"  href="/brand/png/harmoni-favicon-64.png" />
<link rel="apple-touch-icon" sizes="180x180"     href="/brand/png/harmoni-favicon-180.png" />

<!-- PWA / manifest -->
<link rel="icon" type="image/png" sizes="512x512" href="/brand/png/harmoni-favicon-512.png" />

<!-- Open Graph (social cards) -->
<meta property="og:image"        content="https://harmoni.pe/brand/png/harmoni-logo-1200.png" />
<meta property="og:image:width"  content="1200" />
<meta property="og:image:height" content="630" />
```

### Header de la landing
```html
<!-- Lockup completo: header desktop, footer -->
<img src="/brand/png/harmoni-logo-800.png" alt="Harmoni" height="40" />

<!-- Solo isotipo: header móvil, avatares -->
<img src="/brand/png/harmoni-mark-256.png" alt="Harmoni" height="36" />
```

> ⚠️ El logo actual está pensado para **fondos oscuros** (las pilares son blancas).  
> Si lo necesitas sobre fondo claro, usa el contenedor con fondo teal oscuro (`#042F2A`) o pide una variante.

---

## Tokens de marca

```css
:root {
  /* Teal · principal */
  --teal:        #0D9488;   /* botones primarios, links */
  --teal-dark:   #064E3B;   /* hover, acentos */
  --teal-deep:   #042F2A;   /* fondos hero, secciones oscuras */
  --teal-light:  #5EEAD4;   /* highlights sobre fondo oscuro */
  --teal-tint:   #CCFBF1;   /* fondos sutiles, badges */

  /* Acento */
  --accent:      #F59E0B;   /* CTAs, destacados, "PLAN STARTER" */
  --accent-dark: #B45309;

  /* Neutros */
  --ink:         #0F172A;   /* texto principal */
  --gray:        #475569;   /* texto secundario */
  --gray-soft:   #E2E8F0;   /* bordes, dividers */
  --paper:       #FFFFFF;
}
```

---

## Tipografía

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@600;800;900&family=Inter:wght@400;500;600;700&family=Cormorant+Garamond:ital,wght@0,500;1,400&display=swap" rel="stylesheet" />
```

- **Nunito** (800/900) — wordmark del logo, números grandes
- **Inter** (400/500/600/700) — UI y cuerpo
- **Cormorant Garamond** (500/400 italic) — titulares editoriales (brochure)

---

## Reglas de uso

✅ **Hacer**  
- Usar el lockup completo en header y comunicaciones principales  
- Mantener el isotipo solo cuando el espacio es muy reducido  
- Respetar área de seguridad = altura de un pilar de la H  
- Tamaño mínimo: 24px de altura en pantalla

❌ **No hacer**  
- Cambiar los colores del logo  
- Deformar, rotar o inclinar la marca  
- Usar sobre fondos del mismo tono teal sin contraste  
- Agregar efectos (sombras, brillos, gradientes)

---

Cualquier duda: **elopez@harmoni.pe**
