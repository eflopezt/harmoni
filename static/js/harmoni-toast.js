/**
 * Harmoni Toast — sistema global de notificaciones efímeras.
 *
 * Uso:
 *   harmoniToast('Vacante creada ✓');                       // default success
 *   harmoniToast('Error de conexión', 'error');             // rojo
 *   harmoniToast('Procesando…', 'info', { duration: 0 });   // sin auto-dismiss
 *
 * Si la URL trae ?toast=mensaje[&toast_type=success|error|info|warning]
 * o si Django messages framework dejó un mensaje, se muestra automáticamente.
 */
(function () {
    'use strict';

    const COLORS = {
        success: { bg: '#0f766e', icon: 'fa-check-circle' },
        error:   { bg: '#dc2626', icon: 'fa-times-circle' },
        warning: { bg: '#d97706', icon: 'fa-exclamation-triangle' },
        info:    { bg: '#0891b2', icon: 'fa-info-circle' },
    };

    function ensureContainer() {
        let c = document.getElementById('harmoni-toast-container');
        if (c) return c;
        c = document.createElement('div');
        c.id = 'harmoni-toast-container';
        c.style.cssText = [
            'position:fixed', 'top:20px', 'right:20px', 'z-index:9999',
            'display:flex', 'flex-direction:column', 'gap:10px',
            'max-width:min(360px, 92vw)',
            'pointer-events:none',
        ].join(';');
        document.body.appendChild(c);
        return c;
    }

    function show(message, type, opts) {
        const cfg = COLORS[type] || COLORS.success;
        const duration = (opts && typeof opts.duration === 'number') ? opts.duration : 4000;

        const el = document.createElement('div');
        el.style.cssText = [
            `background:${cfg.bg}`,
            'color:#fff',
            'padding:12px 16px',
            'border-radius:10px',
            'box-shadow:0 8px 24px rgba(0,0,0,.18)',
            'font:500 14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif',
            'display:flex', 'align-items:center', 'gap:10px',
            'pointer-events:auto', 'cursor:pointer',
            'transform:translateX(120%)', 'opacity:0',
            'transition:transform .25s ease, opacity .25s ease',
        ].join(';');

        const icon = document.createElement('i');
        icon.className = `fas ${cfg.icon}`;
        icon.style.cssText = 'flex-shrink:0;font-size:18px';
        el.appendChild(icon);

        const text = document.createElement('span');
        text.style.cssText = 'flex:1';
        text.textContent = message;
        el.appendChild(text);

        const close = document.createElement('button');
        close.innerHTML = '&times;';
        close.style.cssText = 'background:none;border:0;color:rgba(255,255,255,.85);font-size:18px;cursor:pointer;padding:0 4px';
        close.setAttribute('aria-label', 'Cerrar');
        el.appendChild(close);

        ensureContainer().appendChild(el);

        // animate in
        requestAnimationFrame(() => {
            el.style.transform = 'translateX(0)';
            el.style.opacity = '1';
        });

        function dismiss() {
            el.style.transform = 'translateX(120%)';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 280);
        }
        close.addEventListener('click', dismiss);
        el.addEventListener('click', (e) => {
            if (e.target !== close) dismiss();
        });
        if (duration > 0) {
            setTimeout(dismiss, duration);
        }
        return { dismiss };
    }

    // Expose globally
    window.harmoniToast = show;

    // Auto-pickup desde URL: ?toast=mensaje&toast_type=success
    document.addEventListener('DOMContentLoaded', function () {
        try {
            const url = new URL(window.location.href);
            const msg = url.searchParams.get('toast');
            if (msg) {
                const type = url.searchParams.get('toast_type') || 'success';
                show(decodeURIComponent(msg), type);
                // Limpiar la URL para no re-mostrar al refrescar
                url.searchParams.delete('toast');
                url.searchParams.delete('toast_type');
                history.replaceState({}, '', url.toString());
            }
        } catch (e) { /* noop */ }

        // Auto-pickup desde Django messages (busca .messages > li)
        document.querySelectorAll('.django-messages-toast').forEach((node) => {
            const msg = node.textContent.trim();
            const type = node.dataset.type || 'success';
            if (msg) show(msg, type);
            node.remove();
        });
    });
})();
