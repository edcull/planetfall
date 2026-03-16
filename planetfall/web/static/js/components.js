/**
 * Planetfall Web UI — Core rendering components and utilities.
 *
 * Provides: openModal factory, renderEvents, renderColonyStatus, renderRoster,
 * renderCharacterBackgrounds, renderTurnSummary, renderLogContent, and utility functions.
 *
 * Related modules (loaded after this file):
 *   components-map.js     — Campaign map rendering
 *   components-modals.js  — All modal opener functions
 *   components-combat.js  — Combat display components
 */

// ── Generic modal factory ───────────────────────────────────
function openModal(modalId, title, bodyHtml, options = {}) {
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = modalId;
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    if (options.maxWidth) modal.style.maxWidth = options.maxWidth;
    if (options.zIndex) overlay.style.zIndex = options.zIndex;

    modal.innerHTML = `
        <div class="modal-header">
            <h2>${title}</h2>
            <button class="modal-close" onclick="document.getElementById('${modalId}').remove()">&times;</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);

    if (options.onOpen) options.onOpen(overlay, modal);

    return overlay;
}

// ── Events ──────────────────────────────────────────────────

function renderEvents(events) {
    const log = document.getElementById('message-log');
    for (const e of events) {
        const div = document.createElement('div');
        div.className = 'event-line';
        div.innerHTML = `
            <span class="event-icon ${e.event_type}">&#9656;</span>
            <span>${escapeHtml(e.description)}</span>
        `;
        log.appendChild(div);
    }
    log.scrollTop = log.scrollHeight;
    checkEventsForToasts(events);
}

// ── Colony Status ───────────────────────────────────────────

// Store latest colony data for modal access
let _lastColonyData = null;

function renderColonyStatus(data) {
    _lastColonyData = data;
    const builtCount = (data.buildings_built || []).length;

    // Sidebar: navigation buttons only (colony stats moved to campaign info panel)
    const panel = document.getElementById('colony-status');
    let sidebarHtml = `
        <div class="sidebar-buttons">
            <div class="sidebar-btn-group">
                <button class="btn sidebar-btn" onclick="openRosterModal()">Roster &#9655;</button>
                <button class="btn sidebar-btn" onclick="openArmoryModal()">Armory &#9655;</button>
            </div>
            <div class="sidebar-btn-group">
                <button class="btn sidebar-btn" onclick="openResearchModal()">Research &#9655;</button>
                <button class="btn sidebar-btn" onclick="openBuildingsModal()">Buildings${builtCount ? ' (' + builtCount + ')' : ''} &#9655;</button>
                <button class="btn sidebar-btn" onclick="openAugmentationsModal()">Augmentations &#9655;</button>
            </div>
            <div class="sidebar-btn-group">
                <button class="btn sidebar-btn" onclick="openAncientSignsModal()">Discoveries &#9655;</button>
            </div>
            <div class="sidebar-btn-group">
                <button class="btn sidebar-btn" onclick="openConditionsModal()">Conditions &#9655;</button>
                <button class="btn sidebar-btn" onclick="openLifeformsModal()">Lifeforms &#9655;</button>
                <button class="btn sidebar-btn" onclick="openEnemiesModal()">Enemies &#9655;</button>
            </div>
            <div class="sidebar-btn-group">
                <button class="btn sidebar-btn" onclick="openMoraleModal()">Morale &#9655;</button>
                <button class="btn sidebar-btn" onclick="openMilestonesModal()">Milestones &#9655;</button>
                <button class="btn sidebar-btn" onclick="openCalamitiesModal()">Calamities &#9655;</button>
            </div>
            <div class="sidebar-btn-group">
                <button class="btn sidebar-btn" onclick="openColonyLog()">Colony Log &#9655;</button>
            </div>
        </div>
    `;
    panel.innerHTML = sidebarHtml;

    // Also update campaign info panel colony status if it exists
    const campaignColony = document.getElementById('campaign-colony-status');
    if (campaignColony) {
        campaignColony.innerHTML = _buildColonyStatusHtml(data);
    }
}

/** Build colony status HTML (reusable for sidebar + campaign info panel). */
function _buildColonyStatusHtml(data) {
    const moraleCls = data.morale >= 0 ? 'positive' : 'negative';
    const integrityCls = data.integrity >= 0 ? 'positive' : 'negative';

    return `
        <div class="colony-panel">
            <h3>${escapeHtml(data.colony_name)} — Turn ${data.turn}</h3>
            <div class="stat-list">
                <div class="stat-row"><span class="label">Morale</span><span class="value ${moraleCls}">${data.morale}</span></div>
                <div class="stat-row"><span class="label">Integrity</span><span class="value ${integrityCls}">${data.integrity}</span></div>
                <div class="stat-row"><span class="label">Defenses</span><span class="value">${data.defenses}</span></div>
                <div class="stat-row"><span class="label">Story Points</span><span class="value">${data.resources.story_points}</span></div>
                <div class="stat-row stat-row-clickable" onclick="openResourceCacheModal()" title="Spend 1 SP to open Resource Cache"><span class="label">Build Points</span><span class="value">${data.resources.build_points}</span></div>
                <div class="stat-row stat-row-clickable" onclick="openResourceCacheModal()" title="Spend 1 SP to open Resource Cache"><span class="label">Research Points</span><span class="value">${data.resources.research_points}</span></div>
                <div class="stat-row stat-row-clickable" onclick="openResourceCacheModal()" title="Spend 1 SP to open Resource Cache"><span class="label">Raw Materials</span><span class="value">${data.resources.raw_materials}</span></div>
                <div class="stat-row"><span class="label">Augmentation</span><span class="value">${data.resources.augmentation_points}</span></div>
                <div class="stat-row"><span class="label">Grunts</span><span class="value">${data.grunts}</span></div>
                <div class="stat-row"><span class="label">Bot</span><span class="value ${data.bot_operational ? 'positive' : 'negative'}">${data.bot_operational ? 'OK' : 'DMG'}</span></div>
                <div class="stat-row"><span class="label">Roster</span><span class="value">${data.roster_size}/${data.roster_max}</span></div>
                <div class="stat-row"><span class="label">Agenda</span><span class="value">${capitalize(data.agenda)}</span></div>
            </div>
        </div>
    `;
}

// ── Roster ──────────────────────────────────────────────────

// Store latest roster data for modal access
let _lastRosterData = null;

function renderRoster(data) {
    _lastRosterData = data;
    // Roster panel no longer rendered inline — button is in colony status panel
    const panel = document.getElementById('roster-panel');
    if (panel) panel.innerHTML = '';
    // Refresh roster modal if open
    if (document.getElementById('roster-modal')) {
        openRosterModal();
    }
}

// ── Character Backgrounds ───────────────────────────────────

function renderCharacterBackgrounds(data) {
    const display = document.getElementById('display-area');
    for (const c of data.characters) {
        const div = document.createElement('div');
        div.className = 'bg-card';
        div.innerHTML = `
            <h4>${escapeHtml(c.name)}${c.title ? ' — ' + escapeHtml(c.title) : ''}</h4>
            <div class="role">${capitalize(c.char_class)}${c.role ? ' / ' + escapeHtml(c.role) : ''}</div>
            ${c.narrative ? `<div class="narrative">${escapeHtml(c.narrative)}</div>` : ''}
        `;
        display.appendChild(div);
    }
}

// ── Turn Summary ────────────────────────────────────────────

function renderTurnSummary(events) {
    const display = document.getElementById('display-area');
    const div = document.createElement('div');
    div.className = 'turn-summary';

    let html = '<h3>Turn Summary</h3>';
    for (const e of events) {
        html += `
            <div class="event-line">
                <span class="event-icon ${e.event_type}">&#9656;</span>
                <span>${escapeHtml(e.description)}</span>
            </div>
        `;
    }

    div.innerHTML = html;
    display.appendChild(div);
    display.scrollTop = display.scrollHeight;
    checkEventsForToasts(events);
}

// ── Log Viewer ──────────────────────────────────────────────

function renderLogContent(msg) {
    const display = document.getElementById('display-area');
    display.innerHTML = '';

    const nav = document.createElement('div');
    nav.className = 'log-nav';
    nav.textContent = `Log ${msg.index}/${msg.total}`;
    display.appendChild(nav);

    const content = document.createElement('div');
    content.className = 'log-content';
    content.innerHTML = simpleMarkdown(msg.text);
    display.appendChild(content);
}

// ── Utilities ───────────────────────────────────────────────

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function humanize(str) {
    if (!str) return '';
    return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function simpleMarkdown(text) {
    // Basic markdown → HTML conversion with table support
    const lines = text.split('\n');
    const out = [];
    let inTable = false;
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];

        // Table rows
        if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
            // Skip separator rows (|---|---|)
            if (/^\|[\s\-:|]+\|$/.test(line.trim())) continue;
            const cells = line.split('|').slice(1, -1).map(c => c.trim());
            if (!inTable) {
                out.push('<table>');
                // First table row = header
                out.push('<tr>' + cells.map(c => `<th>${inlineMarkdown(c)}</th>`).join('') + '</tr>');
                inTable = true;
            } else {
                out.push('<tr>' + cells.map(c => `<td>${inlineMarkdown(c)}</td>`).join('') + '</tr>');
            }
            continue;
        }
        if (inTable) { out.push('</table>'); inTable = false; }

        // List items
        if (/^- (.+)$/.test(line.trim())) {
            if (!inList) { out.push('<ul>'); inList = true; }
            out.push(`<li>${inlineMarkdown(line.trim().slice(2))}</li>`);
            continue;
        }
        if (/^  - (.+)$/.test(line)) {
            if (!inList) { out.push('<ul>'); inList = true; }
            out.push(`<li style="margin-left:16px">${inlineMarkdown(line.trim().slice(2))}</li>`);
            continue;
        }
        if (inList) { out.push('</ul>'); inList = false; }

        // Headings
        if (line.startsWith('### ')) { out.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`); continue; }
        if (line.startsWith('## ')) { out.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`); continue; }
        if (line.startsWith('# ')) { out.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`); continue; }

        // Horizontal rule
        if (/^---+$/.test(line.trim())) { out.push('<hr>'); continue; }

        // Empty line
        if (line.trim() === '') { out.push('<br>'); continue; }

        // Regular paragraph
        out.push(`<p>${inlineMarkdown(line)}</p>`);
    }
    if (inTable) out.push('</table>');
    if (inList) out.push('</ul>');
    return out.join('\n');
}

// ── Toast Notifications ─────────────────────────────────────

function _ensureToastContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
        c = document.createElement('div');
        c.id = 'toast-container';
        c.className = 'toast-container';
        document.body.appendChild(c);
    }
    return c;
}

const TOAST_CONFIG = {
    breakthrough: { icon: '&#10070;', label: 'Breakthrough', cls: 'toast-breakthrough' },
    milestone:    { icon: '&#9733;',  label: 'Milestone',    cls: 'toast-milestone' },
    calamity:     { icon: '&#9888;',  label: 'Calamity',     cls: 'toast-calamity' },
    ancient_site: { icon: '&#10022;', label: 'Ancient Site', cls: 'toast-ancient-site' },
    slyn:         { icon: '&#9876;',  label: 'Slyn Driven Off', cls: 'toast-slyn' },
};

function showToast(variant, description, duration) {
    duration = duration || 6000;
    const cfg = TOAST_CONFIG[variant] || TOAST_CONFIG.milestone;
    const container = _ensureToastContainer();

    const el = document.createElement('div');
    el.className = `toast ${cfg.cls}`;
    el.innerHTML = `
        <span class="toast-icon">${cfg.icon}</span>
        <div class="toast-body">
            <div class="toast-title">${cfg.label}</div>
            <div class="toast-desc">${escapeHtml(description)}</div>
        </div>
    `;
    el.onclick = () => dismissToast(el);
    container.appendChild(el);

    setTimeout(() => dismissToast(el), duration);
}

function dismissToast(el) {
    if (el._dismissed) return;
    el._dismissed = true;
    el.classList.add('toast-out');
    setTimeout(() => el.remove(), 300);
}

/**
 * Scan events for notable state_changes and fire toasts.
 * Called from renderEvents() and renderTurnSummary().
 */
function checkEventsForToasts(events) {
    for (const e of events) {
        const sc = e.state_changes;
        if (!sc) continue;
        if (sc.breakthrough) {
            showToast('breakthrough', e.description);
        } else if (sc.milestone) {
            showToast('milestone', e.description);
        } else if (sc.calamity) {
            showToast('calamity', e.description);
        } else if (sc.ancient_site_sector) {
            showToast('ancient_site', e.description);
        } else if (sc.slyn_driven_off) {
            showToast('slyn', e.description);
        }
    }
}

function inlineMarkdown(text) {
    return text
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
}
