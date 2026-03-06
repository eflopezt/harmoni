/**
 * Harmoni AI — Chat Widget v2
 * Chat asistente con streaming SSE, gráficos inline Chart.js,
 * modo fallback sin IA, sugerencias inteligentes.
 */
(function () {
    'use strict';

    const CHAT_URL = '/asistencia/ia/chat/';
    const STATUS_URL = '/asistencia/ia/status/';
    const UPLOAD_URL = '/asistencia/ia/upload/';

    let chatHistory = [];
    let isStreaming = false;
    let chartCounter = 0;

    // ── Maximize state ──
    let isMaximized = false;
    let backdropEl = null;

    // ── File attachment state ──
    let attachedFile = null;   // { type, name, content, preview, size_kb, truncated }
    let isUploading = false;

    // ── DOM refs ──
    let fab, panel, messagesEl, inputEl, sendBtn, quickActions;
    let statusDot, statusText;
    let fileInput, fileAttachBtn, filePillRow;

    // ── CSRF Token ──
    function getCsrf() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    let isFallbackMode = false;

    // ── Init ──
    async function init() {
        fab = document.getElementById('aiChatFab');
        panel = document.getElementById('aiChatPanel');
        messagesEl = document.getElementById('aiChatMessages');
        inputEl = document.getElementById('aiChatInput');
        sendBtn = document.getElementById('aiChatSend');
        quickActions = document.getElementById('aiQuickActions');
        statusDot = document.querySelector('.ai-status-dot');
        statusText = document.querySelector('.ai-chat-subtitle');
        fileInput = document.getElementById('aiFileInput');
        fileAttachBtn = document.getElementById('aiFileAttachBtn');
        filePillRow = document.getElementById('aiFilePillRow');

        if (!fab || !panel) return;

        // Check AI availability
        try {
            const resp = await fetch(STATUS_URL);
            const data = await resp.json();
            if (!data.available) {
                document.getElementById('harmoniAiChat').style.display = 'none';
                return;
            }
            isFallbackMode = !!data.fallback;
            updateStatusIndicator();
        } catch (e) {
            document.getElementById('harmoniAiChat').style.display = 'none';
            return;
        }

        // Show widget
        document.getElementById('harmoniAiChat').style.display = 'block';

        // Restore history
        try {
            const saved = sessionStorage.getItem('harmoni_ai_history');
            if (saved) {
                chatHistory = JSON.parse(saved);
                renderHistory();
            }
        } catch (e) { /* ignore */ }

        bindEvents();
    }

    function updateStatusIndicator() {
        if (!statusText) return;
        if (isFallbackMode) {
            statusText.innerHTML = '<span class="ai-status-dot ai-status-fallback"></span> Modo datos (sin IA)';
        } else {
            statusText.innerHTML = '<span class="ai-status-dot ai-status-online"></span> Asistente de RRHH';
        }
    }

    // ── Events ──
    function bindEvents() {
        fab.addEventListener('click', togglePanel);
        document.getElementById('aiChatClose').addEventListener('click', closePanel);
        document.getElementById('aiChatMaximize').addEventListener('click', toggleMaximize);
        document.getElementById('aiChatClear').addEventListener('click', clearChat);

        sendBtn.addEventListener('click', () => sendFromInput());
        inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendFromInput();
            }
        });

        // Auto-resize textarea
        inputEl.addEventListener('input', () => {
            inputEl.style.height = 'auto';
            inputEl.style.height = Math.min(inputEl.scrollHeight, 80) + 'px';
        });

        // Quick action buttons (delegation for dynamic buttons)
        quickActions.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-prompt]');
            if (btn) sendMessage(btn.dataset.prompt);
        });

        // Toggle quick actions button
        const toggleBtn = document.getElementById('aiToggleQuickActions');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                const isVisible = quickActions.style.display !== 'none';
                quickActions.style.display = isVisible ? 'none' : 'flex';
                toggleBtn.querySelector('i').className = isVisible
                    ? 'fas fa-lightbulb' : 'fas fa-chevron-down';
                toggleBtn.title = isVisible ? 'Mostrar sugerencias' : 'Ocultar sugerencias';
            });
        }

        // Export chat
        const exportBtn = document.getElementById('aiExportChat');
        if (exportBtn) {
            exportBtn.addEventListener('click', exportConversation);
        }

        // File attachment
        if (fileAttachBtn && fileInput) {
            fileAttachBtn.addEventListener('click', () => {
                if (attachedFile) {
                    clearAttachedFile();
                } else {
                    fileInput.click();
                }
            });
            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                fileInput.value = '';  // Reset so same file can be re-selected
                await uploadFile(file);
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+Shift+H to toggle chat
            if (e.ctrlKey && e.shiftKey && e.key === 'H') {
                e.preventDefault();
                togglePanel();
            }
            // ESC to exit maximize or close panel
            if (e.key === 'Escape') {
                if (isMaximized) {
                    toggleMaximize();
                } else if (panel.classList.contains('open')) {
                    closePanel();
                }
            }
        });
    }

    function togglePanel() {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) {
            inputEl.focus();
            scrollToBottom();
        }
    }

    function closePanel() {
        if (isMaximized) restoreFromMaximize();
        panel.classList.remove('open');
    }

    // ── Maximize / Restore ──
    function toggleMaximize() {
        if (isMaximized) {
            restoreFromMaximize();
        } else {
            panel.classList.add('maximized');
            isMaximized = true;
            // Swap icon to compress
            const icon = document.querySelector('#aiChatMaximize i');
            if (icon) icon.className = 'fas fa-compress';
            document.getElementById('aiChatMaximize').title = 'Restaurar';
            // Create backdrop
            backdropEl = document.createElement('div');
            backdropEl.className = 'ai-maximize-backdrop';
            backdropEl.addEventListener('click', toggleMaximize);
            document.body.appendChild(backdropEl);
            // Re-render charts at new size
            rerenderVisibleCharts();
            scrollToBottom();
        }
    }

    function restoreFromMaximize() {
        if (!isMaximized) return;
        panel.classList.remove('maximized');
        isMaximized = false;
        // Swap icon back to expand
        const icon = document.querySelector('#aiChatMaximize i');
        if (icon) icon.className = 'fas fa-expand';
        document.getElementById('aiChatMaximize').title = 'Maximizar';
        // Remove backdrop
        if (backdropEl) {
            backdropEl.remove();
            backdropEl = null;
        }
        // Re-render charts at original size
        rerenderVisibleCharts();
        scrollToBottom();
    }

    function rerenderVisibleCharts() {
        if (typeof Chart === 'undefined') return;
        // Give CSS transition time to finish
        setTimeout(() => {
            document.querySelectorAll('.ai-chat-chart-canvas canvas').forEach(canvas => {
                const chart = Chart.getChart(canvas);
                if (chart) chart.resize();
            });
        }, 350);
    }

    // ── File Attachment ──
    async function uploadFile(file) {
        if (isUploading || isStreaming) return;

        // Size check: 10 MB max
        if (file.size > 10 * 1024 * 1024) {
            showToast('Archivo demasiado grande (máx. 10 MB)');
            return;
        }

        isUploading = true;

        // Show uploading pill immediately
        showFilePill({
            type: 'uploading',
            name: file.name,
            icon: 'fa-spinner',
        });

        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch(UPLOAD_URL, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrf() },
                body: formData,
            });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                showToast('Error: ' + (data.error || 'No se pudo procesar el archivo'));
                clearAttachedFile();
                return;
            }
            attachedFile = data;  // { type, name, content, preview, size_kb, truncated }
            showFilePill(attachedFile);
            // Update attach button style
            if (fileAttachBtn) {
                fileAttachBtn.classList.add('has-file');
                fileAttachBtn.title = 'Quitar archivo adjunto';
                fileAttachBtn.querySelector('i').className = 'fas fa-times';
            }
            // Focus input for question
            inputEl.focus();
            inputEl.placeholder = `Pregunta sobre ${attachedFile.name}...`;
        } catch (e) {
            showToast('Error al subir archivo: ' + e.message);
            clearAttachedFile();
        } finally {
            isUploading = false;
        }
    }

    function clearAttachedFile() {
        attachedFile = null;
        isUploading = false;
        if (filePillRow) filePillRow.innerHTML = '';
        if (fileAttachBtn) {
            fileAttachBtn.classList.remove('has-file');
            fileAttachBtn.title = 'Adjuntar archivo (PDF, Excel, imagen)';
            fileAttachBtn.querySelector('i').className = 'fas fa-paperclip';
        }
        if (inputEl) inputEl.placeholder = 'Escribe tu consulta...';
    }

    function showFilePill(fileInfo) {
        if (!filePillRow) return;
        filePillRow.innerHTML = '';

        const iconMap = {
            'pdf': 'fa-file-pdf',
            'excel': 'fa-file-excel',
            'image': 'fa-image',
            'text': 'fa-file-alt',
            'uploading': 'fa-spinner',
        };
        const typeClass = fileInfo.type || 'text';
        const icon = iconMap[fileInfo.type] || 'fa-file';
        const sizeStr = fileInfo.size_kb ? ` (${fileInfo.size_kb} KB)` : '';

        const pill = document.createElement('div');
        pill.className = `ai-file-pill ${typeClass}`;
        pill.innerHTML = `
            <i class="fas ${icon}"></i>
            <span class="ai-file-pill-name" title="${escapeHtml(fileInfo.name)}">${escapeHtml(fileInfo.name)}${sizeStr}</span>
            ${fileInfo.type !== 'uploading'
                ? `<button class="ai-file-pill-remove" title="Quitar archivo"><i class="fas fa-times"></i></button>`
                : ''}
        `;

        if (fileInfo.type !== 'uploading') {
            pill.querySelector('.ai-file-pill-remove').addEventListener('click', clearAttachedFile);
        }
        filePillRow.appendChild(pill);
    }

    function clearChat() {
        chatHistory = [];
        sessionStorage.removeItem('harmoni_ai_history');
        messagesEl.innerHTML = '';
        appendWelcome();
        quickActions.style.display = 'flex';
        removeSuggestionChips();
    }

    // ── Messages ──
    function appendWelcome() {
        const div = document.createElement('div');
        div.className = 'ai-msg ai-msg-assistant';
        div.innerHTML = '<div class="ai-msg-content">' +
            '\ud83d\udc4b Hola, soy <strong>Harmoni AI</strong>, tu asistente de RRHH. ' +
            'Puedo ayudarte con consultas del sistema, datos de personal, ' +
            'y pol\u00edticas laborales.<br><br>' +
            '<em>\ud83d\udcca Tip: P\u00eddeme gr\u00e1ficos como "Mu\u00e9strame un gr\u00e1fico del personal por \u00e1rea"</em>' +
            '<br><em>\u2328\ufe0f Atajo: Ctrl+Shift+H para abrir/cerrar</em></div>';
        messagesEl.appendChild(div);
    }

    function appendMessage(role, content) {
        const div = document.createElement('div');
        div.className = `ai-msg ai-msg-${role}`;
        div.innerHTML = `<div class="ai-msg-content">${escapeHtml(content)}</div>`;
        messagesEl.appendChild(div);
        scrollToBottom();
    }

    function createAssistantBubble() {
        const div = document.createElement('div');
        div.className = 'ai-msg ai-msg-assistant';
        const content = document.createElement('div');
        content.className = 'ai-msg-content';
        div.appendChild(content);
        messagesEl.appendChild(div);
        scrollToBottom();
        return content;
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'ai-msg ai-msg-assistant';
        div.id = 'aiTypingIndicator';
        div.innerHTML = '<div class="ai-typing">' +
            '<span></span><span></span><span></span>' +
            '<span class="ai-typing-text">' +
            (isFallbackMode ? 'Consultando datos...' : 'Pensando...') +
            '</span></div>';
        messagesEl.appendChild(div);
        scrollToBottom();
        return div;
    }

    function removeTyping() {
        const el = document.getElementById('aiTypingIndicator');
        if (el) el.remove();
    }

    function scrollToBottom() {
        // Use rAF to ensure DOM has updated
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (messagesEl) {
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                }
            });
        });
    }

    function renderHistory() {
        messagesEl.innerHTML = '';
        appendWelcome();
        chatHistory.forEach(msg => {
            const div = document.createElement('div');
            div.className = `ai-msg ai-msg-${msg.role}`;
            if (msg.role === 'assistant') {
                const content = document.createElement('div');
                content.className = 'ai-msg-content';
                // Support single chartData or array of charts (dashboard grid)
                if (msg.chartData) {
                    const charts = Array.isArray(msg.chartData) ? msg.chartData : [msg.chartData];
                    if (charts.length > 1) {
                        // Multi-chart: wrap in dashboard grid
                        const grid = document.createElement('div');
                        grid.className = 'ai-dashboard-grid';
                        charts.forEach(cd => grid.appendChild(buildChartElement(cd)));
                        content.appendChild(grid);
                    } else {
                        charts.forEach(cd => content.appendChild(buildChartElement(cd)));
                    }
                }
                const textDiv = document.createElement('div');
                textDiv.innerHTML = renderMarkdown(msg.content);
                content.appendChild(textDiv);
                // Restore fallback badge
                if (msg.isFallback) {
                    content.appendChild(createFallbackBadge());
                }
                div.appendChild(content);
            } else {
                div.innerHTML = `<div class="ai-msg-content">${escapeHtml(msg.content)}</div>`;
            }
            messagesEl.appendChild(div);
        });
        setTimeout(renderDeferredCharts, 100);
        scrollToBottom();
    }

    // ── Suggestion Chips ──
    const SUGGESTION_MAP = {
        'empleado': ['¿Cómo se distribuyen por área?', 'Gráfico por género', 'Gráfico por antigüedad'],
        'asistencia': ['Gráfico asistencia semanal', 'Horas extra', 'Resumen general'],
        'pendiente': ['Detalle de papeletas', 'Solicitudes de HE', 'Vacaciones pendientes'],
        'contrato': ['Gráfico por tipo de contrato', 'Empleados activos', 'Distribución por áreas'],
        'vacacion': ['Gráfico vacaciones por estado', 'Personal en goce', 'Resumen general'],
        'capacitacion': ['Gráfico capacitaciones', 'Certificaciones vencidas', 'Evaluaciones'],
        'evaluacion': ['OKRs en riesgo', 'PDI activos', 'Resumen general'],
        'prestamo': ['Saldo pendiente total', 'Resumen general'],
        'genero': ['Gráfico por edad', 'Empleados activos', 'Gráfico por área'],
        'edad': ['Gráfico por género', 'Gráfico por antigüedad', 'Empleados activos'],
        'area': ['Gráfico por género', 'Gráfico por edad', 'Empleados activos'],
        'grafico': ['Gráfico por género', 'Gráfico por edad', 'Gráfico de HE'],
        'dashboard': ['Exportar reporte en Excel', 'Gráfico por área y guárdalo en mi dashboard', 'Resumen general'],
        'gerencia': ['Exportar reporte en Excel', 'Dashboard de gerencia', 'Gráfico por área'],
        'guardar': ['Gráfico de personal por área y guárdalo en mi dashboard', 'Dashboard de gerencia', 'Resumen general'],
        'fijar': ['Gráfico de personal por área y guárdalo en mi dashboard', 'Resumen general'],
        'reporte': ['Dashboard de gerencia', 'Resumen general', 'Gráfico por área'],
        'excel': ['Dashboard de gerencia', 'Resumen general', 'Empleados activos'],
        '_default': ['Resumen general', '¿Cuántos empleados hay?', 'Gráfico por área'],
    };

    function getSuggestions(userMsg) {
        const msg = userMsg.toLowerCase();
        for (const [key, suggestions] of Object.entries(SUGGESTION_MAP)) {
            if (key !== '_default' && msg.includes(key)) {
                return suggestions;
            }
        }
        return SUGGESTION_MAP['_default'];
    }

    function showSuggestionChips(userMsg) {
        removeSuggestionChips();
        const suggestions = getSuggestions(userMsg);

        const container = document.createElement('div');
        container.className = 'ai-suggestion-chips';
        container.id = 'aiSuggestionChips';

        suggestions.forEach(text => {
            const chip = document.createElement('button');
            chip.className = 'ai-suggestion-chip';
            chip.textContent = text;
            chip.addEventListener('click', () => {
                removeSuggestionChips();
                sendMessage(text);
            });
            container.appendChild(chip);
        });

        messagesEl.appendChild(container);
        scrollToBottom();
    }

    function removeSuggestionChips() {
        const existing = document.getElementById('aiSuggestionChips');
        if (existing) existing.remove();
    }

    // ── Fallback Badge ──
    function createFallbackBadge() {
        const badge = document.createElement('div');
        badge.className = 'ai-fallback-badge';
        badge.innerHTML = '<i class="fas fa-database"></i>Respuesta directa (sin IA)';
        return badge;
    }

    // ── Inline Chart ──
    function buildChartElement(chartData) {
        chartCounter++;
        const wrapper = document.createElement('div');
        wrapper.className = 'ai-chat-chart-wrapper';

        const title = document.createElement('div');
        title.className = 'ai-chat-chart-title';
        const chartIcon = {
            'doughnut': 'fa-chart-pie',
            'bar': 'fa-chart-bar',
            'line': 'fa-chart-line',
        }[chartData.chart] || 'fa-chart-pie';
        title.innerHTML = `<i class="fas ${chartIcon}"></i> ${escapeHtml(chartData.title)}`;
        wrapper.appendChild(title);

        const canvasWrap = document.createElement('div');
        canvasWrap.className = 'ai-chat-chart-canvas';
        const canvas = document.createElement('canvas');
        canvas.id = `aiInlineChart_${chartCounter}`;
        canvas.setAttribute('data-chart', JSON.stringify(chartData));
        canvasWrap.appendChild(canvas);
        wrapper.appendChild(canvasWrap);

        if (chartData.summary) {
            const summary = document.createElement('div');
            summary.className = 'ai-chat-chart-summary';
            summary.textContent = chartData.summary;
            wrapper.appendChild(summary);
        }

        // Show legend for doughnut and bar charts with per-bar colors
        const showLegend = (chartData.chart === 'doughnut') ||
            (chartData.chart === 'bar' && chartData.colors.length > 1 && !chartData.multi_series);
        if (showLegend && chartData.labels) {
            const legend = document.createElement('div');
            legend.className = 'ai-chat-chart-legend';
            chartData.labels.forEach((label, i) => {
                const item = document.createElement('span');
                item.className = 'ai-chart-legend-item';
                const color = chartData.colors[i] || '#999';
                item.innerHTML = `<span class="ai-chart-legend-dot" style="background:${color}"></span>${escapeHtml(label)}: <strong>${chartData.values[i]}</strong>`;
                legend.appendChild(item);
            });
            wrapper.appendChild(legend);
        }

        return wrapper;
    }

    function renderDeferredCharts() {
        document.querySelectorAll('.ai-chat-chart-canvas canvas[data-chart]').forEach(canvas => {
            if (canvas._chartRendered) return;
            try {
                const spec = JSON.parse(canvas.getAttribute('data-chart'));
                renderChart(canvas, spec);
                canvas._chartRendered = true;
            } catch (e) { /* skip */ }
        });
    }

    function renderChart(canvas, spec) {
        if (typeof Chart === 'undefined') return;
        const ctx = canvas.getContext('2d');

        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600 },
        };

        if (spec.chart === 'doughnut') {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: spec.labels,
                    datasets: [{
                        data: spec.values,
                        backgroundColor: spec.colors,
                        borderWidth: 2,
                        borderColor: '#fff',
                    }]
                },
                options: {
                    ...commonOptions,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                    const pct = total ? ((ctx.raw / total) * 100).toFixed(1) : '0';
                                    return ` ${ctx.label}: ${ctx.raw} (${pct}%)`;
                                }
                            }
                        }
                    },
                    cutout: '55%',
                }
            });
        } else if (spec.chart === 'bar') {
            if (spec.multi_series && spec.values2) {
                const isStacked = spec.stacked !== false; // default true for backward compat
                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: spec.labels,
                        datasets: [
                            {
                                label: (spec.series_labels && spec.series_labels[0]) || 'Serie 1',
                                data: spec.values,
                                backgroundColor: spec.colors[0] || 'rgba(15,118,110,.7)',
                                borderRadius: 3,
                            },
                            {
                                label: (spec.series_labels && spec.series_labels[1]) || 'Serie 2',
                                data: spec.values2,
                                backgroundColor: spec.colors[1] || 'rgba(239,68,68,.7)',
                                borderRadius: 3,
                            },
                        ],
                    },
                    options: {
                        ...commonOptions,
                        plugins: { legend: { display: true, position: 'bottom', labels: { font: { size: 9 }, boxWidth: 10, padding: 5 } } },
                        scales: {
                            x: { stacked: isStacked, grid: { display: false }, ticks: { font: { size: 9 } } },
                            y: { stacked: isStacked, grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 } }, beginAtZero: true },
                        },
                    },
                });
            } else {
                // Use per-bar colors if multiple colors provided, else single color
                const bgColor = spec.colors.length > 1
                    ? spec.colors.slice(0, spec.values.length)
                    : (spec.colors[0] || 'rgba(15,118,110,.6)');
                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: spec.labels,
                        datasets: [{
                            label: spec.title,
                            data: spec.values,
                            backgroundColor: bgColor,
                            borderRadius: 4,
                        }]
                    },
                    options: {
                        ...commonOptions,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { display: false }, ticks: { font: { size: 9 } } },
                            y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 } }, beginAtZero: true }
                        }
                    }
                });
            }
        } else if (spec.chart === 'line') {
            // Support multi-series line: spec.multi_series + spec.values2
            const lineDatasets = [{
                label: (spec.series_labels && spec.series_labels[0]) || spec.title,
                data: spec.values,
                borderColor: spec.colors[0] || '#0f766e',
                backgroundColor: 'rgba(15,118,110,.08)',
                fill: !spec.multi_series,
                tension: 0.3,
                pointRadius: 3,
                pointHoverRadius: 5,
            }];
            if (spec.multi_series && spec.values2) {
                lineDatasets.push({
                    label: (spec.series_labels && spec.series_labels[1]) || 'Serie 2',
                    data: spec.values2,
                    borderColor: spec.colors[1] || '#d97706',
                    backgroundColor: 'rgba(217,119,6,.06)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                });
            }
            new Chart(ctx, {
                type: 'line',
                data: { labels: spec.labels, datasets: lineDatasets },
                options: {
                    ...commonOptions,
                    plugins: {
                        legend: {
                            display: spec.multi_series || false,
                            position: 'bottom',
                            labels: { font: { size: 9 }, boxWidth: 10, padding: 5 }
                        }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { font: { size: 9 } } },
                        y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 } } }
                    }
                }
            });
        }
    }

    // ── Pin-to-Dashboard Card ──
    function buildPinCard(pinData) {
        const card = document.createElement('div');
        card.className = 'ai-pin-card';
        card.innerHTML = `
            <div class="ai-pin-card-icon"><i class="fas fa-thumbtack"></i></div>
            <div class="ai-pin-card-body">
                <div class="ai-pin-card-title">¿Guardar en tu Dashboard IA?</div>
                <div class="ai-pin-card-subtitle">${escapeHtml(pinData.titulo || 'Gráfico')}</div>
            </div>
            <button class="ai-pin-save-btn" onclick="window.aiSaveWidget(this, ${JSON.stringify(JSON.stringify(pinData))})">
                <i class="fas fa-check"></i> Guardar
            </button>`;
        return card;
    }

    window.aiSaveWidget = async function(btn, pinDataStr) {
        try {
            const pinData = JSON.parse(pinDataStr);
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            const resp = await fetch('/analytics/widgets/guardar/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({
                    titulo: pinData.titulo,
                    chart_type: pinData.chart_type,
                    data_source: pinData.data_source,
                    config: pinData.config,
                }),
            });
            const data = await resp.json();
            if (data.ok) {
                const card = btn.closest('.ai-pin-card');
                if (card) {
                    card.innerHTML = `<div class="ai-pin-success"><i class="fas fa-check-circle"></i> Guardado en tu <a href="/analytics/ia/" target="_blank">Dashboard IA</a></div>`;
                }
            } else {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-check"></i> Guardar';
                alert(data.error || 'Error al guardar');
            }
        } catch (e) {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-check"></i> Guardar'; }
        }
    };

    // ── Send ──
    function sendFromInput() {
        const text = inputEl.value.trim();
        if (!text) return;
        inputEl.value = '';
        inputEl.style.height = 'auto';
        sendMessage(text);
    }

    async function sendMessage(text) {
        if (isStreaming || isUploading) return;
        isStreaming = true;
        sendBtn.disabled = true;

        // Snapshot and clear attached file before sending
        const fileCtx = attachedFile ? { ...attachedFile } : null;
        if (fileCtx) clearAttachedFile();

        // Hide quick actions after first message
        quickActions.style.display = 'none';
        removeSuggestionChips();

        // Build user bubble (with optional file badge)
        const userDiv = document.createElement('div');
        userDiv.className = 'ai-msg ai-msg-user';
        let userHtml = '';
        if (fileCtx) {
            const fileIconMap = { pdf: 'fa-file-pdf', excel: 'fa-file-excel', image: 'fa-image', text: 'fa-file-alt' };
            const fileIcon = fileIconMap[fileCtx.type] || 'fa-file';
            userHtml += `<div class="ai-msg-file-badge"><i class="fas ${fileIcon}"></i> ${escapeHtml(fileCtx.name)}</div>`;
        }
        userHtml += `<div class="ai-msg-content">${escapeHtml(text)}</div>`;
        userDiv.innerHTML = userHtml;
        messagesEl.appendChild(userDiv);
        scrollToBottom();

        chatHistory.push({ role: 'user', content: text });

        const typingEl = showTyping();
        const bubble = createAssistantBubble();

        let currentChartData = null;

        try {
            const requestBody = {
                message: text,
                history: chatHistory.slice(-10),
            };
            // Include file context if a file was attached (send content, not base64 image directly)
            if (fileCtx) {
                requestBody.file_context = {
                    type: fileCtx.type,
                    name: fileCtx.name,
                    content: fileCtx.content || '',
                    truncated: fileCtx.truncated || false,
                };
            }
            const response = await fetch(CHAT_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrf(),
                },
                body: JSON.stringify(requestBody),
            });

            removeTyping();

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                bubble.innerHTML = `<em class="ai-error-msg">${err.error || 'Error al conectar con Harmoni AI.'}</em>`;
                isStreaming = false;
                sendBtn.disabled = false;
                return;
            }

            // Read SSE stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = '';
            let textContainer = null;
            let isCurrentFallback = false;
            let allChartData = [];  // Support multiple charts per message
            let isDashboardMode = false;  // Track if this is a multi-chart dashboard
            let dashboardGrid = null;     // Grid container for dashboard charts

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const token = line.slice(6);
                        if (token === '[DONE]') continue;

                        // ── Detect fallback marker ──
                        if (token === '[FALLBACK]') {
                            isCurrentFallback = true;
                            continue;
                        }

                        // ── Detect maximize marker (auto-maximize for dashboards) ──
                        if (token === '[MAXIMIZE]') {
                            isDashboardMode = true;
                            if (!isMaximized && panel.classList.contains('open')) {
                                toggleMaximize();
                            }
                            // Create grid container for dashboard charts
                            dashboardGrid = document.createElement('div');
                            dashboardGrid.className = 'ai-dashboard-grid';
                            bubble.appendChild(dashboardGrid);
                            continue;
                        }

                        // ── Detect download marker ──
                        const dlMatch = token.match(/^\[DOWNLOAD:(\w+)\]$/);
                        if (dlMatch) {
                            fullResponse += `[DOWNLOAD:${dlMatch[1]}]`;
                            const target = textContainer || bubble;
                            target.innerHTML = renderMarkdown(fullResponse);
                            scrollToBottom();
                            continue;
                        }

                        // ── Detect pin-to-dashboard marker ──
                        const pinMatch = token.match(/^\[PIN_WIDGET\](.*)\[\/PIN_WIDGET\]$/);
                        if (pinMatch) {
                            try {
                                const pinData = JSON.parse(pinMatch[1]);
                                const pinCard = buildPinCard(pinData);
                                bubble.appendChild(pinCard);
                                scrollToBottom();
                            } catch (e) { /* skip if malformed */ }
                            continue;
                        }

                        // ── Detect inline chart marker ──
                        const chartMatch = token.match(/^\[CHART\](.*)\[\/CHART\]$/);
                        if (chartMatch) {
                            try {
                                currentChartData = JSON.parse(chartMatch[1]);
                                allChartData.push(currentChartData);
                                const chartEl = buildChartElement(currentChartData);
                                // Append to grid if dashboard mode, otherwise to bubble
                                const chartTarget = dashboardGrid || bubble;
                                chartTarget.appendChild(chartEl);
                                // Create/update text container after charts
                                if (!textContainer) {
                                    textContainer = document.createElement('div');
                                    textContainer.className = 'ai-chat-chart-narrative';
                                    bubble.appendChild(textContainer);
                                }
                                setTimeout(renderDeferredCharts, 50);
                                scrollToBottom();
                            } catch (e) {
                                fullResponse += token;
                                const target = textContainer || bubble;
                                target.innerHTML = renderMarkdown(fullResponse);
                            }
                            continue;
                        }

                        fullResponse += token;
                        const target = textContainer || bubble;
                        target.innerHTML = renderMarkdown(fullResponse);
                        scrollToBottom();
                    }
                }
            }

            if (fullResponse || allChartData.length > 0) {
                chatHistory.push({
                    role: 'assistant',
                    content: fullResponse,
                    chartData: allChartData.length === 1 ? allChartData[0]
                             : allChartData.length > 1 ? allChartData
                             : undefined,
                    isFallback: isCurrentFallback || undefined,
                });
                saveHistory();
            }

            // Show fallback badge
            if (isCurrentFallback && bubble) {
                bubble.appendChild(createFallbackBadge());
            }

            // Show suggestion chips
            showSuggestionChips(text);

        } catch (e) {
            removeTyping();
            bubble.innerHTML = '<em class="ai-error-msg">Error de conexi\u00f3n. Verifica que el servidor est\u00e9 corriendo.</em>';
        }

        isStreaming = false;
        sendBtn.disabled = false;
        inputEl.focus();
    }

    // ── Persistence ──
    function saveHistory() {
        try {
            sessionStorage.setItem(
                'harmoni_ai_history',
                JSON.stringify(chatHistory.slice(-20))
            );
        } catch (e) { /* quota exceeded */ }
    }

    // ── Clean AI internal markers ──
    function cleanAiMarkers(text) {
        if (!text) return '';
        text = text.replace(/\[DATOS REALES[^\]]*\]/gi, '');
        text = text.replace(/\[\/CHART\]/g, '');
        text = text.replace(/\[CHART\][^\[]*\[\/CHART\]/g, '');
        text = text.replace(/\[FALLBACK\]/g, '');
        text = text.replace(/\[MAXIMIZE\]/g, '');
        text = text.replace(/\[PIN_WIDGET\].*?\[\/PIN_WIDGET\]/gs, '');
        return text.trim();
    }

    // ── Markdown (enhanced) ──
    function renderMarkdown(text) {
        if (!text) return '';
        text = cleanAiMarkers(text);

        // Extract [DOWNLOAD:type] markers before any processing
        const downloadButtons = [];
        text = text.replace(/\[DOWNLOAD:(\w+)\]/g, (match, type) => {
            downloadButtons.push(type);
            return `AIDLBTN${downloadButtons.length - 1}AIDLBTN`;
        });

        // Restore escaped newlines from SSE transport
        text = text.replace(/\\n/g, '\n');
        let html = escapeHtml(text);

        // Headers (### h3, ## h2)
        html = html.replace(/^### (.+)$/gm, '<h4 class="ai-md-h4">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 class="ai-md-h3">$1</h3>');

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Italic (careful not to match ** or list bullets)
        html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code class="ai-md-code">$1</code>');

        // Numbered lists (1. 2. 3.)
        html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="ai-md-oli">$2</li>');
        html = html.replace(/((?:<li class="ai-md-oli">.*<\/li>\n?)+)/g,
            '<ol class="ai-md-ol">$1</ol>');

        // Unordered lists (- or *)
        html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>(?!class).*<\/li>\n?)+)/g,
            '<ul class="ai-md-ul">$1</ul>');

        // Horizontal rule
        html = html.replace(/^---$/gm, '<hr class="ai-md-hr">');

        // Line breaks (but not inside lists)
        html = html.replace(/\n/g, '<br>');

        // Clean up double <br> inside lists
        html = html.replace(/<\/li><br>/g, '</li>');
        html = html.replace(/<\/ul><br>/g, '</ul>');
        html = html.replace(/<\/ol><br>/g, '</ol>');
        html = html.replace(/<\/h[34]><br>/g, (m) => m.replace('<br>', ''));

        // Restore download buttons
        downloadButtons.forEach((type, i) => {
            const btnHtml = `<button class="ai-download-btn" onclick="window.aiDownloadReport('${type}')">`
                + `<i class="fas fa-file-excel"></i> Descargar Reporte Ejecutivo (.xlsx)</button>`;
            html = html.replace(`AIDLBTN${i}AIDLBTN`, btnHtml);
        });

        return html;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ── Export Conversation ──
    function exportConversation() {
        if (chatHistory.length === 0) {
            showToast('No hay mensajes para exportar.');
            return;
        }

        const now = new Date();
        const dateStr = now.toISOString().slice(0, 10);
        const timeStr = now.toTimeString().slice(0, 5).replace(':', '');

        let md = `# Conversación Harmoni AI\n`;
        md += `**Fecha**: ${now.toLocaleDateString('es-PE')} ${now.toLocaleTimeString('es-PE')}\n\n`;
        md += `---\n\n`;

        chatHistory.forEach((msg) => {
            const role = msg.role === 'user' ? '👤 **Tú**' : '🤖 **Harmoni AI**';
            const badge = msg.isFallback ? ' _(respuesta directa)_' : '';
            md += `${role}${badge}:\n\n${msg.content}\n\n`;
            if (msg.chartData) {
                // chartData can be a single object or an array (multi-chart)
                const charts = Array.isArray(msg.chartData) ? msg.chartData : [msg.chartData];
                const titles = charts.map(c => c.title || '?').join(', ');
                md += `📊 _[Gráfico${charts.length > 1 ? 's' : ''}: ${titles}]_\n\n`;
            }
            md += `---\n\n`;
        });

        md += `_Exportado desde Harmoni AI — ${dateStr}_\n`;

        // Download as .md file
        const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `harmoni-ai-chat-${dateStr}-${timeStr}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('Conversación exportada ✓');
    }

    function showToast(message) {
        // Lightweight toast notification
        const toast = document.createElement('div');
        toast.className = 'ai-toast';
        toast.textContent = message;
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, 2500);
    }

    // ── Download Report (global for inline onclick) ──
    window.aiDownloadReport = async function (type) {
        const btn = document.querySelector('.ai-download-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
        }
        try {
            const resp = await fetch('/asistencia/ia/exportar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrf(),
                },
                body: JSON.stringify({ type: type }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.error || 'Error al generar reporte');
            }
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const dateStr = new Date().toISOString().slice(0, 10);
            a.download = `reporte-ejecutivo-${dateStr}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Reporte descargado ✓');
        } catch (e) {
            showToast('Error: ' + e.message);
        }
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-file-excel"></i> Descargar Reporte Ejecutivo (.xlsx)';
        }
    };

    // ── Start ──
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
