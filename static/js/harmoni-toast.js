/**
 * Harmoni Toast System — global.
 *
 * Estilo handoff design: bottom-right, background --hm-teal-deep, border-left 3px
 * variante, progress bar visible, botón Deshacer opcional.
 *
 * API nueva (recomendada):
 *   Harmoni.toast({ title: 'Saved', kind: 'success' });
 *   Harmoni.toast({
 *     title: 'Empleado desactivado',
 *     detail: 'Carla Pérez (DNI 12345678)',
 *     kind: 'warning',
 *     undoable: true,
 *     onUndo: () => fetch('/personal/.../reactivar/', {method:'POST'}),
 *   });
 *   Harmoni.toast({ title: 'Procesando…', duration: 0 });  // sin auto-dismiss
 *
 * API legacy (backward compat):
 *   harmoniToast('Vacante creada ✓');                      // default success
 *   harmoniToast('Error de conexión', 'error');
 *   harmoniToast('Procesando…', 'info', { duration: 0 });
 *
 * Kind: 'success' | 'warning' | 'error' | 'info' | undefined.
 *
 * Auto-disparadores:
 *   - URL: ?toast=mensaje&toast_type=success (limpia URL tras mostrar)
 *   - DOM: <div class="django-messages-toast" data-type="...">texto</div>
 *   - Event: window.dispatchEvent(new CustomEvent('harmoni:toast', { detail: {...} }))
 */
(function () {
    'use strict';

    const ICONS = {
        success: 'fa-circle-check',
        warning: 'fa-triangle-exclamation',
        error:   'fa-circle-xmark',
        info:    'fa-circle-info',
    };

    function ensureContainer() {
        let c = document.getElementById('hmToastContainer');
        if (c) return c;
        c = document.createElement('div');
        c.id = 'hmToastContainer';
        c.className = 'hm-toast-container';
        c.setAttribute('role', 'region');
        c.setAttribute('aria-live', 'polite');
        c.setAttribute('aria-label', 'Notificaciones efímeras');
        document.body.appendChild(c);
        return c;
    }

    function escapeHTML(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    /**
     * Muestra un toast con la API moderna.
     * @param {object} opts
     * @param {string} opts.title       — Texto principal (requerido)
     * @param {string} [opts.detail]    — Texto secundario
     * @param {string} [opts.kind]      — 'success' | 'warning' | 'error' | 'info'
     * @param {number} [opts.duration]  — ms (default 5000, 0 = no auto-dismiss)
     * @param {boolean}[opts.undoable]  — botón Deshacer
     * @param {function}[opts.onUndo]   — callback al click Deshacer
     * @returns {{dismiss: function, element: HTMLElement}}
     */
    function toast(opts) {
        opts = opts || {};
        const title    = opts.title || '';
        const detail   = opts.detail || '';
        const kind     = (opts.kind && ICONS[opts.kind]) ? opts.kind : '';
        const duration = typeof opts.duration === 'number' ? opts.duration : 5000;
        const undoable = !!opts.undoable;

        const el = document.createElement('div');
        el.className = 'hm-toast' + (kind ? ' hm-toast--' + kind : '');
        el.style.setProperty('--hm-toast-duration', duration + 'ms');

        const iconKey = kind ? ICONS[kind] : 'fa-bell';

        el.innerHTML = ''
            + '<button class="hm-toast__close" aria-label="Cerrar">&times;</button>'
            + '<div class="hm-toast__row">'
            +   '<i class="fas ' + iconKey + ' hm-toast__icon" aria-hidden="true"></i>'
            +   '<div class="hm-toast__body">'
            +     '<div class="hm-toast__title">' + escapeHTML(title) + '</div>'
            +     (detail ? '<div class="hm-toast__detail">' + escapeHTML(detail) + '</div>' : '')
            +     (undoable ? '<div class="hm-toast__actions"><button class="hm-toast__btn" data-undo>Deshacer</button></div>' : '')
            +   '</div>'
            + '</div>'
            + (duration > 0 ? '<div class="hm-toast__progress"></div>' : '');

        let dismissed = false;
        let timer = null;

        function dismiss() {
            if (dismissed) return;
            dismissed = true;
            if (timer) { clearTimeout(timer); timer = null; }
            el.classList.add('hm-toast--leave');
            el.classList.remove('hm-toast--show');
            setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 280);
        }

        el.querySelector('.hm-toast__close').addEventListener('click', dismiss);
        if (undoable) {
            el.querySelector('[data-undo]').addEventListener('click', function () {
                try {
                    if (typeof opts.onUndo === 'function') opts.onUndo();
                } catch (e) { console.error('Toast onUndo error', e); }
                dismiss();
            });
        }

        // Pausa progress al hover
        el.addEventListener('mouseenter', function () {
            const p = el.querySelector('.hm-toast__progress');
            if (p) p.style.animationPlayState = 'paused';
            if (timer) { clearTimeout(timer); timer = null; }
        });
        el.addEventListener('mouseleave', function () {
            const p = el.querySelector('.hm-toast__progress');
            if (p) p.style.animationPlayState = 'running';
            if (duration > 0 && !dismissed) timer = setTimeout(dismiss, 2000);
        });

        ensureContainer().appendChild(el);
        requestAnimationFrame(() => {
            requestAnimationFrame(() => el.classList.add('hm-toast--show'));
        });
        if (duration > 0) timer = setTimeout(dismiss, duration);

        return { dismiss: dismiss, element: el };
    }

    // ── API legacy: harmoniToast(message, type, opts) ──
    function legacyToast(message, type, legacyOpts) {
        return toast({
            title: message,
            kind: type,
            duration: legacyOpts && typeof legacyOpts.duration === 'number'
                      ? legacyOpts.duration : 5000,
        });
    }

    // ── Expose ──
    window.Harmoni = window.Harmoni || {};
    window.Harmoni.toast = toast;
    window.harmoniToast = legacyToast;

    // ── Bridge para custom events ──
    window.addEventListener('harmoni:toast', function (e) {
        if (e && e.detail) toast(e.detail);
    });

    // ── Auto-pickup desde URL: ?toast=mensaje&toast_type=success ──
    document.addEventListener('DOMContentLoaded', function () {
        try {
            const url = new URL(window.location.href);
            const msg = url.searchParams.get('toast');
            if (msg) {
                const type = url.searchParams.get('toast_type') || 'success';
                toast({ title: decodeURIComponent(msg), kind: type });
                url.searchParams.delete('toast');
                url.searchParams.delete('toast_type');
                history.replaceState({}, '', url.toString());
            }
        } catch (e) { /* noop */ }

        // ── Auto-pickup desde Django messages framework ──
        document.querySelectorAll('.django-messages-toast').forEach(function (node) {
            const msg = node.textContent.trim();
            const type = node.dataset.type || 'success';
            if (msg) toast({ title: msg, kind: type });
            node.remove();
        });

        // ── Seeds del nuevo formato (data-title, data-detail, data-kind) ──
        document.querySelectorAll('.hm-toast-seed').forEach(function (seed) {
            toast({
                title:  seed.dataset.title || '',
                detail: seed.dataset.detail || '',
                kind:   seed.dataset.kind || '',
            });
            seed.parentNode.removeChild(seed);
        });
    });
})();
