/**
 * Planetfall Web UI — Campaign map rendering.
 *
 * Provides: renderMap, openSectorModal, enableMapSelection, disableMapSelection,
 * confirmSectorSelection, and map-specific helpers/state.
 *
 * Depends on: components.js (escapeHtml, capitalize, _lastColonyData, _buildColonyStatusHtml)
 */

// ── Campaign Map State ──────────────────────────────────────

let _lastMapData = null;
let _selectedSectorIndex = null;

// Sector selection mode state
let _sectorSelectMode = false;
let _sectorSelectValidIds = [];
let _sectorSelectCallback = null;
let _sectorSelectBtnLabel = 'Select This Sector';

// ── Campaign Map ────────────────────────────────────────────

function renderMap(data) {
    _lastMapData = data;
    const display = document.getElementById('display-area');
    const cols = data.cols;

    // Campaign panel: map on left, info panel on right
    let html = '<div class="campaign-panel">';

    // Left: campaign map section
    html += '<div class="campaign-map-section">';
    html += `<div class="map-grid" style="grid-template-columns: repeat(${cols}, 1fr);">`;

    // Terrain icons and labels
    const terrainIcons = {
        plains: '&#127793;', forest: '&#127794;', hills: '&#9968;',
        ruins: '&#127959;', wetlands: '&#127754;', crags: '&#9962;',
        desert: '&#127964;', tundra: '&#10052;',
    };

    for (let i = 0; i < data.sectors.length; i++) {
        const s = data.sectors[i];
        const terrain = s.terrain || 'plains';
        let cellClass = `map-cell terrain-${terrain}`;
        let icon = '';
        let nameLabel = '';
        let terrainLabel = '';
        const sectorName = s.name || `Sector ${s.sector_id}`;
        let tooltip = sectorName;

        // Always show terrain type label at top of cell
        const terrainIcon = terrainIcons[terrain] || '';
        terrainLabel = `<div class="map-terrain-label">${terrainIcon}</div>`;

        // Base status styling
        if (s.is_colony) {
            cellClass += ' colony';
            icon = '<div class="map-icon colony-icon">&#9733;</div>';
            tooltip += ' — Colony Base';
        } else if (s.enemy_occupied_by) {
            cellClass += ' enemy';
            icon = '<div class="map-icon enemy-icon">&#9760;</div>';
            tooltip += ` — Enemy: ${s.enemy_occupied_by}`;
        } else if (s.status === 'exploited') {
            cellClass += ' exploited';
            icon = '<div class="map-icon exploited-icon">&#10003;</div>';
            tooltip += ' — Exploited';
        } else if (s.status === 'explored') {
            cellClass += ' explored';
            icon = '';
            tooltip += ` — ${capitalize(s.status)}`;
        } else if (s.has_ancient_site) {
            cellClass += ' unknown ancient-site';
            icon = '';
            tooltip += ` — Ancient Site`;
        } else if (s.has_investigation_site) {
            cellClass += ' unknown investigation';
            icon = '';
            tooltip += ` — Investigation Site`;
        } else {
            cellClass += ' unknown';
            icon = '';
            tooltip += ` — ${capitalize(terrain)}`;
        }

        // Overlay icons for special sites (shown on top of status)
        let overlayIcons = '';
        if (!s.is_colony) {
            if (s.has_ancient_site) {
                overlayIcons += '<span class="map-overlay-icon ancient-icon" title="Ancient Site">&#10022;</span>';
                tooltip += ' | Ancient Site';
            }
            if (s.has_ancient_sign) {
                overlayIcons += '<span class="map-overlay-icon sign-icon" title="Ancient Sign">&#9650;</span>';
                tooltip += ' | Ancient Sign';
            }
            if (s.has_investigation_site) {
                overlayIcons += '<span class="map-overlay-icon investigation-icon" title="Investigation">&#63;</span>';
                tooltip += ' | Investigation';
            }
        }

        // Sector name (truncated for cell) — only shown for explored sectors
        if (s.name) {
            nameLabel = `<div class="map-name">${escapeHtml(s.name.length > 12 ? s.name.slice(0, 11) + '…' : s.name)}</div>`;
        }

        // Resource/hazard indicators for known sectors
        let indicators = '';
        if (s.status !== 'unexplored' && !s.is_colony) {
            const resBar = s.resource_level > 0 ? `<span class="map-res" title="Resources: ${s.resource_level}">${'&#9632;'.repeat(s.resource_level)}</span>` : '';
            const hazBar = s.hazard_level > 0 ? `<span class="map-haz" title="Hazard: ${s.hazard_level}">${'&#9650;'.repeat(s.hazard_level)}</span>` : '';
            if (resBar || hazBar) {
                indicators = `<div class="map-indicators">${resBar}${hazBar}</div>`;
            }
        }

        const overlayHtml = overlayIcons ? `<div class="map-overlays">${overlayIcons}</div>` : '';

        html += `
            <div class="${cellClass}" title="${escapeHtml(tooltip)}" onclick="openSectorModal(${i})">
                ${terrainLabel}
                ${icon}
                ${nameLabel}
                ${overlayHtml}
                ${indicators}
            </div>
        `;
    }

    html += '</div>';  // close map-grid

    // Legend (directly under the map grid)
    html += '<div class="bf-legend-box">';
    html += '<div class="bf-legend-terrain">';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-green); font-weight:700;">&#9733;</span> Colony</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--enemy-red); font-weight:700;">&#9760;</span> Enemy</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-cyan); font-weight:700;">&#63;</span> Investigation</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-yellow); font-weight:700;">&#10022;</span> Ancient Site</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-yellow); font-weight:700;">&#9650;</span> Ancient Sign</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-green); font-weight:700;">&#10003;</span> Exploited</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-green);">&#9632;</span> Resources</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-red);">&#9650;</span> Hazard</span>';
    html += '</div>';
    html += '</div>';

    html += '</div>';  // close campaign-map-section

    // Right: info panel (colony status + sector details) — collapsible header
    html += '<div class="campaign-info-panel" id="campaign-info-main">';
    html += '<div class="info-panel-header" onclick="toggleInfoPanel(\'campaign-info-toggle\',\'campaign-info-body\')">';
    html += '<span id="campaign-info-toggle"><span class="toggle-arrow">&#9660;</span></span>';
    if (_lastColonyData) {
        html += `<span class="info-panel-title">${escapeHtml(_lastColonyData.colony_name)} — Turn ${_lastColonyData.turn}</span>`;
    } else {
        html += '<span class="info-panel-title">Colony Info</span>';
    }
    html += '</div>';

    // Collapsible body
    html += '<div id="campaign-info-body">';

    // Colony status (rendered from cached data)
    html += '<div id="campaign-colony-status">';
    if (_lastColonyData) {
        html += _buildColonyStatusHtml(_lastColonyData);
    }
    html += '</div>';

    // Sector detail panel
    html += '<div class="sector-detail-panel" id="sector-detail-panel"></div>';

    html += '</div>';  // close campaign-info-body
    html += '</div>';  // close campaign-info-panel
    html += '</div>';  // close campaign-panel

    display.innerHTML = html;
}

// ── Sector Selection ────────────────────────────────────────

function enableMapSelection(validIds, callback, btnLabel) {
    _sectorSelectMode = true;
    _sectorSelectValidIds = validIds;
    _sectorSelectCallback = callback;
    _sectorSelectBtnLabel = btnLabel || 'Select This Sector';

    // Add selection-mode class to map and highlight valid sectors
    const container = document.querySelector('.campaign-map-section') || document.querySelector('.map-container');
    if (container) container.classList.add('selection-mode');

    const cells = document.querySelectorAll('.map-cell');
    if (_lastMapData) {
        for (let i = 0; i < _lastMapData.sectors.length; i++) {
            const s = _lastMapData.sectors[i];
            if (cells[i]) {
                if (validIds.includes(s.sector_id)) {
                    cells[i].classList.add('selectable');
                } else {
                    cells[i].classList.add('not-selectable');
                }
            }
        }
    }
}

function disableMapSelection() {
    _sectorSelectMode = false;
    _sectorSelectValidIds = [];
    _sectorSelectCallback = null;

    const container = document.querySelector('.campaign-map-section') || document.querySelector('.map-container');
    if (container) container.classList.remove('selection-mode');

    document.querySelectorAll('.map-cell.selectable').forEach(el => el.classList.remove('selectable'));
    document.querySelectorAll('.map-cell.not-selectable').forEach(el => el.classList.remove('not-selectable'));
}

// ── Sector Detail ───────────────────────────────────────────

function _buildSectorDetailHtml(s, index) {
    const row = Math.floor(index / _lastMapData.cols);
    const col = index % _lastMapData.cols;

    let details = '';
    if (s.is_colony) {
        details += '<div style="color: var(--accent-green); font-weight: bold;">Colony Base</div>';
    }
    if (s.enemy_occupied_by) {
        details += `<div style="color: var(--accent-red);">Enemy: ${escapeHtml(s.enemy_occupied_by)}</div>`;
    }

    const statusColor = {
        'unexplored': 'var(--text-dim)',
        'explored': 'var(--accent-cyan)',
        'exploited': 'var(--accent-green)',
    }[s.status] || 'var(--text-main)';

    const sectorName = s.name || `Sector ${s.sector_id}`;
    const terrainLabel = capitalize(s.terrain || 'unknown');

    return `
        <div class="sector-detail-header">
            <h3>${escapeHtml(sectorName)}</h3>
            <span class="sector-detail-coords">(${row},${col})</span>
        </div>
        <div class="stat-list">
            <div class="stat-row"><span class="label">Terrain</span><span class="value">${terrainLabel}</span></div>
            <div class="stat-row"><span class="label">Status</span><span class="value" style="color:${statusColor}">${capitalize(s.status)}</span></div>
            <div class="stat-row"><span class="label">Resources</span><span class="value">${s.resource_level}</span></div>
            <div class="stat-row"><span class="label">Hazard</span><span class="value">${s.hazard_level}</span></div>
        </div>
        ${details}
        <div class="sector-detail-tags">
            ${s.has_ancient_sign ? '<div style="color: var(--accent-yellow);">&#9650; Ancient Sign detected</div>' : ''}
            ${s.has_ancient_site ? '<div style="color: var(--accent-yellow);">&#10022; Ancient Site present</div>' : ''}
            ${s.has_investigation_site ? '<div style="color: var(--accent-cyan);">&#63; Investigation site</div>' : ''}
        </div>
    `;
}

function _isMobileView() {
    return window.innerWidth <= 900;
}

function openSectorModal(index) {
    if (!_lastMapData) return;
    const s = _lastMapData.sectors[index];
    if (!s) return;

    // Highlight selected cell
    document.querySelectorAll('.map-cell.selected').forEach(el => el.classList.remove('selected'));
    const cells = document.querySelectorAll('.map-cell');
    if (cells[index]) cells[index].classList.add('selected');
    _selectedSectorIndex = index;

    let html = _buildSectorDetailHtml(s, index);

    // Add Select button if in sector selection mode and this sector is valid
    if (_sectorSelectMode && _sectorSelectValidIds.includes(s.sector_id)) {
        html += `<button class="btn btn-primary sector-select-btn" onclick="confirmSectorSelection(${s.sector_id})">${escapeHtml(_sectorSelectBtnLabel)}</button>`;
    } else if (_sectorSelectMode) {
        html += `<div class="sector-not-available">Not available</div>`;
    }

    if (_isMobileView()) {
        // Show as floating tooltip near the tapped cell
        _closeSectorTooltip();
        const cell = cells[index];
        const rect = cell.getBoundingClientRect();

        const tooltip = document.createElement('div');
        tooltip.className = 'sector-tooltip';
        tooltip.id = 'sector-tooltip';
        tooltip.innerHTML = `<button class="sector-tooltip-close" onclick="_closeSectorTooltip()">&#10005;</button>${html}`;
        document.body.appendChild(tooltip);

        // Position: below the cell, centered horizontally
        const tipWidth = 260;
        let left = rect.left + rect.width / 2 - tipWidth / 2;
        left = Math.max(8, Math.min(left, window.innerWidth - tipWidth - 8));
        let top = rect.bottom + 8;
        // If it would go off-screen bottom, show above
        if (top + 200 > window.innerHeight) {
            top = rect.top - 8;
            tooltip.style.transform = 'translateY(-100%)';
        }
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    } else {
        // Desktop: use side panel
        const panel = document.getElementById('sector-detail-panel');
        if (!panel) return;
        panel.innerHTML = html;
        panel.classList.add('active');
    }
}

function confirmSectorSelection(sectorId) {
    if (_sectorSelectCallback) {
        const cb = _sectorSelectCallback;
        disableMapSelection();
        _closeSectorTooltip();
        cb(sectorId);
    }
}

function _closeSectorTooltip() {
    const existing = document.getElementById('sector-tooltip');
    if (existing) existing.remove();
}
