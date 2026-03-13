/**
 * Planetfall Web UI — Rendering components for display messages.
 */

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
                <button class="btn sidebar-btn" onclick="openAncientSignsModal()">Ancient Signs &#9655;</button>
                <button class="btn sidebar-btn" onclick="openArtifactsModal()">Artifacts &#9655;</button>
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

        if (s.is_colony) {
            cellClass += ' colony';
            icon = '<div class="map-icon colony-icon">&#9733;</div>';
            tooltip += ' — Colony Base';
        } else if (s.enemy_occupied_by) {
            cellClass += ' enemy';
            icon = '<div class="map-icon enemy-icon">&#9760;</div>';
            tooltip += ` — Enemy: ${s.enemy_occupied_by}`;
        } else if (s.has_investigation_site) {
            cellClass += ' investigation';
            icon = '<div class="map-icon investigation-icon">&#63;</div>';
            tooltip += ' — Investigation Site';
        } else if (s.has_ancient_site) {
            cellClass += ' ancient';
            icon = '<div class="map-icon ancient-icon">&#9670;</div>';
            tooltip += ' — Ancient Site';
        } else if (s.has_ancient_sign) {
            cellClass += ' sign';
            icon = '<div class="map-icon sign-icon">A</div>';
            tooltip += ' — Ancient Sign';
        } else if (s.status === 'exploited') {
            cellClass += ' exploited';
            icon = '<div class="map-icon exploited-icon">&#10003;</div>';
            tooltip += ' — Exploited';
        } else if (s.status === 'explored' || s.status === 'investigated') {
            cellClass += ' explored';
            icon = `<div class="map-icon explored-icon">${terrainIcons[terrain] || '&#183;'}</div>`;
            tooltip += ` — ${capitalize(s.status)}`;
            terrainLabel = ''; // icon already shows terrain
        } else {
            cellClass += ' unknown';
            icon = '';
            tooltip += ` — ${capitalize(terrain)}`;
        }

        // Sector name (truncated for cell) — only shown for explored sectors
        if (s.name) {
            nameLabel = `<div class="map-name">${escapeHtml(s.name.length > 12 ? s.name.slice(0, 11) + '…' : s.name)}</div>`;
        }

        // Resource/hazard indicators for known sectors
        let indicators = '';
        if (s.status !== 'unknown' && !s.is_colony) {
            const resBar = s.resource_level > 0 ? `<span class="map-res" title="Resources: ${s.resource_level}">${'&#9632;'.repeat(Math.min(s.resource_level, 3))}</span>` : '';
            const hazBar = s.hazard_level > 0 ? `<span class="map-haz" title="Hazard: ${s.hazard_level}">${'&#9650;'.repeat(Math.min(s.hazard_level, 3))}</span>` : '';
            if (resBar || hazBar) {
                indicators = `<div class="map-indicators">${resBar}${hazBar}</div>`;
            }
        }

        html += `
            <div class="${cellClass}" title="${escapeHtml(tooltip)}" onclick="openSectorModal(${i})">
                ${terrainLabel}
                ${icon}
                ${nameLabel}
                ${indicators}
            </div>
        `;
    }

    html += '</div>';  // close map-grid
    html += '</div>';  // close campaign-map-section

    // Right: info panel (colony status + sector details)
    html += '<button class="info-panel-toggle" id="campaign-info-toggle" onclick="toggleInfoPanel(\'campaign-info-toggle\',\'campaign-info-main\')"><span class="toggle-arrow">&#9660;</span> Colony Info</button>';
    html += '<div class="campaign-info-panel" id="campaign-info-main">';

    // Colony status (rendered from cached data)
    html += '<div id="campaign-colony-status">';
    if (_lastColonyData) {
        html += _buildColonyStatusHtml(_lastColonyData);
    }
    html += '</div>';

    // Sector detail panel
    html += '<div class="sector-detail-panel" id="sector-detail-panel"></div>';

    html += '</div>';  // close campaign-info-panel
    html += '</div>';  // close campaign-panel

    // Legend (full width below map + info panel)
    html += '<div class="bf-legend-box">';
    html += '<div class="bf-legend-terrain">';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-yellow); font-weight:700;">&#9733;</span> Colony</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--enemy-red); font-weight:700;">&#9760;</span> Enemy</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-cyan); font-weight:700;">&#63;</span> Investigation</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-magenta); font-weight:700;">&#9670;</span> Ancient Site</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-green); font-weight:700;">&#10003;</span> Exploited</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-green);">&#9632;</span> Resources</span>';
    html += '<span class="bf-legend-item"><span style="color:var(--accent-red);">&#9650;</span> Hazard</span>';
    html += '</div>';
    html += '</div>';

    display.innerHTML = html;
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
                <div class="stat-row"><span class="label">Build Points</span><span class="value">${data.resources.build_points}</span></div>
                <div class="stat-row"><span class="label">Research Points</span><span class="value">${data.resources.research_points}</span></div>
                <div class="stat-row"><span class="label">Raw Materials</span><span class="value">${data.resources.raw_materials}</span></div>
                <div class="stat-row"><span class="label">Augmentation</span><span class="value">${data.resources.augmentation_points}</span></div>
                <div class="stat-row"><span class="label">Grunts</span><span class="value">${data.grunts}</span></div>
                <div class="stat-row"><span class="label">Bot</span><span class="value ${data.bot_operational ? 'positive' : 'negative'}">${data.bot_operational ? 'OK' : 'DMG'}</span></div>
                <div class="stat-row"><span class="label">Roster</span><span class="value">${data.roster_size}/${data.roster_max}</span></div>
                <div class="stat-row"><span class="label">Agenda</span><span class="value">${capitalize(data.agenda)}</span></div>
            </div>
        </div>
    `;
}

// ── Mission Options ─────────────────────────────────────────

function renderMissionOptions(options) {
    const log = document.getElementById('message-log');
    let html = `
        <table class="mission-table">
            <tr><th>#</th><th>Mission</th><th>Details</th></tr>
    `;

    for (let i = 0; i < options.length; i++) {
        const opt = options[i];
        const name = opt.name || opt.type || '?';
        const details = opt.description || opt.rewards || '';
        html += `
            <tr>
                <td>${i + 1}</td>
                <td>${escapeHtml(name)}</td>
                <td>${escapeHtml(String(details))}</td>
            </tr>
        `;
    }

    html += '</table>';

    const container = document.createElement('div');
    container.innerHTML = html;
    log.appendChild(container);
    log.scrollTop = log.scrollHeight;
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
}

// ── Combat Phase ────────────────────────────────────────────

const PHASE_LABELS = {
    'deployment': 'Deployment',
    'reaction_roll': 'Reaction Roll',
    'quick_actions': 'Quick Actions',
    'enemy_phase': 'Enemy Actions',
    'slow_actions': 'Slow Actions',
    'end_phase': 'End Phase',
    'start_phase': 'Start Phase',
    'beacons_round': 'Beacons',
    'analysis_round': 'Analysis',
    'perimeter_round': 'Perimeter',
};

function renderCombatPhase(phase, roundNumber) {
    const header = document.getElementById('step-header');
    const label = PHASE_LABELS[phase] || phase.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    if (roundNumber > 0) {
        header.innerHTML = `<span class="step-label">Round ${roundNumber}</span><span class="phase-label">${label}</span>`;
    } else {
        header.innerHTML = `<span class="phase-label">${label}</span>`;
    }
    // During campaign combat (step 7+), mark step 8 as active
    // _currentStep is 0 during initial missions, so this won't trigger
    if (_currentStep >= 7 && _currentStep < 8) {
        _currentStep = 8;
        renderStepsSidebar(8);
    }
}

// ── Mission Summary ─────────────────────────────────────────

function renderMissionSummary(missions) {
    const display = document.getElementById('display-area');
    const div = document.createElement('div');
    div.className = 'mission-summary';

    let html = '<div class="mission-summary-title">LANDING SITE ESTABLISHED</div>';
    html += '<div class="mission-summary-list">';
    for (const m of missions) {
        const cls = m.success ? 'mission-summary-success' : 'mission-summary-failure';
        const icon = m.success ? '&#10003;' : '&#10007;';
        html += `<div class="mission-summary-row ${cls}">`;
        html += `<span class="mission-summary-icon">${icon}</span>`;
        html += `<span class="mission-summary-name">${escapeHtml(m.name)}</span>`;
        html += `<span class="mission-summary-detail">${escapeHtml(m.detail)}</span>`;
        html += '</div>';
    }
    html += '</div>';

    div.innerHTML = html;
    display.appendChild(div);
}

// ── Combat Log ──────────────────────────────────────────────

function renderCombatLog(lines) {
    const display = document.getElementById('display-area');
    const div = document.createElement('div');
    div.className = 'combat-log';
    div.innerHTML = lines.map(l => `<div class="combat-log-line">${escapeHtml(l)}</div>`).join('');
    display.appendChild(div);
    display.scrollTop = display.scrollHeight;
}

// ── Reaction Roll ───────────────────────────────────────────

function renderReactionRoll(data) {
    const display = document.getElementById('display-area');
    const div = document.createElement('div');
    div.className = 'reaction-panel';

    let html = '<h4 style="color: var(--accent-yellow); margin-bottom: 8px;">Reaction Roll</h4>';
    html += '<div class="dice-display">';
    for (const d of (data.dice || [])) {
        html += `<div class="die">${d}</div>`;
    }
    html += '</div>';

    if (data.figures) {
        html += '<div style="margin-top: 8px; font-size: 12px;">';
        for (const f of data.figures) {
            html += `<div>${escapeHtml(f.name)} (speed ${f.speed})</div>`;
        }
        html += '</div>';
    }

    div.innerHTML = html;
    display.appendChild(div);
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

// ── Roster Modal ────────────────────────────────────────────

function openRosterModal() {
    if (!_lastRosterData) return;

    // Remove existing modal if any
    const existing = document.getElementById('roster-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'roster-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';

    const colonyData = _lastColonyData || {};
    const grunts = colonyData.grunts || 0;
    const botOk = colonyData.bot_operational;

    let html = `
        <div class="modal-header">
            <h2>Colony Roster</h2>
            <button class="modal-close" onclick="document.getElementById('roster-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="roster-support-section">
                <div class="roster-support-card">
                    <div class="roster-support-header">
                        <span class="roster-support-name">Grunt Fireteams</span>
                        <span class="roster-support-value">${grunts} grunts</span>
                    </div>
                    <div class="roster-support-desc">Standard military personnel assigned to colony defense and missions.</div>
                </div>
                <div class="roster-support-card">
                    <div class="roster-support-header">
                        <span class="roster-support-name">Colony Bot</span>
                        <span class="roster-support-value ${botOk ? 'positive' : 'negative'}">${botOk ? 'Operational' : 'Damaged'}</span>
                    </div>
                    <div class="roster-support-desc">Automated support unit for colony operations and combat assistance.</div>
                </div>
            </div>
    `;

    for (const c of _lastRosterData.characters) {
        const status = c.sick_bay_turns > 0
            ? `<span class="sick">Sick Bay (${c.sick_bay_turns} turns)</span>`
            : '<span style="color: var(--accent-green)">Ready</span>';

        // Background details
        const bgParts = [];
        if (c.motivation) bgParts.push(`<div><span style="color:var(--text-dim)">Motivation:</span> ${escapeHtml(c.motivation)}</div>`);
        if (c.prior_experience) {
            let expLine = `<span style="color:var(--text-dim)">Experience:</span> ${escapeHtml(c.prior_experience)}`;
            if (c.stat_bonuses && Object.keys(c.stat_bonuses).length > 0) {
                const bonusLabels = {reactions:'React',speed:'Speed',combat_skill:'Combat',toughness:'Tough',savvy:'Savvy'};
                const parts = Object.entries(c.stat_bonuses).map(([k,v]) => `${bonusLabels[k]||k} +${v}`);
                expLine += ` <span style="color:var(--accent-yellow)">(${parts.join(', ')})</span>`;
            }
            bgParts.push(`<div>${expLine}</div>`);
        }
        const bgSection = bgParts.length ? `<div class="roster-card-background">${bgParts.join('')}</div>` : '';

        const safeName = escapeHtml(c.name);
        const titlePrefix = c.title ? `<span class="roster-card-title">${escapeHtml(c.title)}</span>` : '';
        const isSickBay = c.sick_bay_turns > 0;
        html += `
            <div class="roster-card${isSickBay ? ' roster-card-sick' : ''}" data-char-name="${safeName}">
                <div class="roster-card-header">
                    ${titlePrefix}
                    <div class="roster-card-name">${safeName}</div>
                    ${c.role ? `<div class="roster-card-role">${escapeHtml(c.role)}</div>` : ''}
                    <div class="roster-card-class">${capitalize(c.char_class)}</div>
                    <button class="btn-edit-char" onclick="openRosterCharEdit(${JSON.stringify(c.name).replace(/"/g, '&quot;')})" title="Edit">&#9998;</button>
                </div>
                <div class="roster-card-stats">
                    <div class="stat-chip"><span class="label">React</span><span class="val">${c.reactions}</span></div>
                    <div class="stat-chip"><span class="label">Speed</span><span class="val">${c.speed}"</span></div>
                    <div class="stat-chip"><span class="label">Combat</span><span class="val">+${c.combat_skill}</span></div>
                    <div class="stat-chip"><span class="label">Tough</span><span class="val">${c.toughness}</span></div>
                    <div class="stat-chip"><span class="label">Savvy</span><span class="val">+${c.savvy}</span></div>
                    <div class="stat-chip"><span class="label">XP</span><span class="val">${c.xp}</span></div>
                    <div class="stat-chip"><span class="label">KP</span><span class="val">${c.kill_points}</span></div>
                </div>
                <div class="roster-card-info">
                    <div>Status: ${status}&nbsp;&nbsp;Loyalty: ${capitalize(c.loyalty)}</div>
                    ${c.equipment && c.equipment.length > 0 ? `<div>Equipment: ${c.equipment.map(escapeHtml).join(', ')}</div>` : ''}
                    ${c.upgrades && c.upgrades.length > 0 ? `<div>Upgrades: ${c.upgrades.map(escapeHtml).join(', ')}</div>` : ''}
                </div>
                ${bgSection}
                ${c.narrative ? `<div class="roster-card-bg">${escapeHtml(c.narrative)}</div>` : ''}
            </div>
        `;
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on Escape
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Research Modal ──────────────────────────────────────────

function openResearchModal() {
    if (!_lastColonyData) return;
    const existing = document.getElementById('research-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'research-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '800px';

    const theories = _lastColonyData.tech_tree || [];
    const primary = theories.filter(t => !t.is_secondary);
    const secondary = theories.filter(t => t.is_secondary);

    const rp = _lastColonyData.resources ? _lastColonyData.resources.research_points : 0;

    let html = `
        <div class="modal-header">
            <h2>Research</h2>
            <button class="modal-close" onclick="document.getElementById('research-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="research-rp-box">
                <span class="research-rp-label">Research Points Available</span>
                <span class="research-rp-value">${rp} RP</span>
            </div>
    `;

    if (theories.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">No research data available.</div>';
    }

    function renderTheory(t) {
        const pct = t.rp_cost > 0 ? Math.min(100, Math.round((t.invested / t.rp_cost) * 100)) : 0;
        const locked = !t.prerequisite_met;
        const statusCls = t.completed ? 'tt-completed' : (t.invested > 0 ? 'tt-in-progress' : (locked ? 'tt-locked' : 'tt-available'));

        let s = `<div class="tt-theory ${statusCls}">`;
        s += `<div class="tt-theory-header">`;
        s += `<span class="tt-theory-name">${t.completed ? '&#10003; ' : ''}${escapeHtml(t.name)}</span>`;
        s += `<span class="tt-theory-rp">${t.invested}/${t.rp_cost} RP</span>`;
        s += `</div>`;

        if (t.invested > 0 || t.completed) {
            s += `<div class="progress-bar" style="margin: 4px 0 6px;"><div class="progress-fill" style="width:${pct}%;background:${t.completed ? 'var(--accent-green)' : 'var(--accent-yellow)'};"></div></div>`;
        }

        if (locked) {
            s += `<div class="tt-prereq">Requires: ${escapeHtml(t.prerequisite_name)}</div>`;
        }

        // Applications
        if (t.applications.length > 0) {
            s += `<div class="tt-apps">`;
            for (const app of t.applications) {
                const appCls = app.unlocked ? 'tt-app-unlocked' : 'tt-app-locked';
                const typeIcon = {building: '&#9632;', weapon: '&#9876;', bonus: '&#9733;', milestone: '&#9670;', grunt_upgrade: '&#9650;'}[app.type] || '&#8226;';
                const typeLabel = capitalize(app.type.replace('_', ' '));
                s += `<div class="tt-app ${appCls}">`;
                s += `<span class="tt-app-icon" title="${typeLabel}">${typeIcon}</span>`;
                s += `<span class="tt-app-name">${escapeHtml(app.name)}</span>`;
                if (app.description) {
                    s += `<span class="tt-app-desc">${escapeHtml(app.description)}</span>`;
                }
                s += `</div>`;
            }
            s += `</div>`;
        }

        s += `</div>`;
        return s;
    }

    if (primary.length > 0) {
        html += '<h4 class="tt-section-header">Primary Theories</h4>';
        html += '<div class="tt-grid">';
        for (const t of primary) html += renderTheory(t);
        html += '</div>';
    }

    if (secondary.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:16px;">Secondary Theories</h4>';
        html += '<div class="tt-grid">';
        for (const t of secondary) html += renderTheory(t);
        html += '</div>';
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Armory Modal ────────────────────────────────────────────

let _lastArmoryData = null;

// Weapon trait descriptions for tooltips
const WEAPON_TRAIT_TIPS = {
    'pistol': 'Can be fired as a sidearm: no penalty when shooting after moving',
    'critical': 'Natural 6 to hit causes +1 additional damage',
    'stabilized': '+1 to hit if the shooter did not move this round',
    'ap ammo': 'Armor-piercing: negates enemy armor save',
    'knockback': 'Target pushed 1 zone away on a hit',
    'focused': '+1 to hit at close range (within 6")',
    'stream': 'Ignores cover modifiers when shooting',
    'burning': 'Ignores armor save (armor-piercing flame)',
    'cumbersome': 'Cannot fire if the shooter moved this round',
    'hail of fire': 'Roll all shots; each hit is resolved separately',
    'melee': 'Melee weapon: used in brawling, not ranged combat',
    'flexible': 'Can be used in both ranged and melee combat',
    'area': 'Targets all figures in the zone (friend and foe)',
    'phased fire': 'Ignores cover; shots pass through terrain',
    'mind link': 'Uses Savvy instead of Combat Skill to hit',
    'civilian': 'Usable by civilians and scientists',
    'scout': 'Usable by scouts',
    'trooper': 'Usable by troopers',
    'grunt': 'Usable by grunts',
};

function renderArmory(data) {
    _lastArmoryData = data;
}

function openArmoryModal() {
    const existing = document.getElementById('armory-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'armory-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '850px';

    const data = _lastArmoryData || {};
    const weapons = data.weapons || [];
    const gruntUpgrades = data.grunt_upgrades || [];
    const standard = weapons.filter(w => w.tier === 'standard');
    const tier1 = weapons.filter(w => w.tier === 'tier_1');
    const tier2 = weapons.filter(w => w.tier === 'tier_2');

    let html = `
        <div class="modal-header">
            <h2>Campaign Armory</h2>
            <button class="modal-close" onclick="document.getElementById('armory-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
    `;

    function renderWeapon(w) {
        const locked = !w.available;
        const cls = locked ? 'wpn-locked' : 'wpn-available';
        let s = `<div class="wpn-card ${cls}">`;
        s += `<div class="wpn-header"><span class="wpn-name">${escapeHtml(w.name)}</span>`;
        if (locked) {
            s += `<span class="wpn-lock-badge">&#128274; Locked</span>`;
        }
        s += `</div>`;
        s += `<div class="wpn-stats">`;
        if (w.range_inches > 0) {
            s += `<span><span class="wpn-stat-label">Range</span> ${w.range_inches}"</span>`;
        } else {
            s += `<span><span class="wpn-stat-label">Range</span> Melee</span>`;
        }
        s += `<span><span class="wpn-stat-label">Shots</span> ${w.shots || '—'}</span>`;
        s += `<span><span class="wpn-stat-label">Dmg</span> +${w.damage_bonus}</span>`;
        s += `</div>`;
        if (w.traits && w.traits.length) {
            s += `<div class="wpn-traits">`;
            for (const t of w.traits) {
                const label = t.replace(/_/g, ' ');
                const tip = WEAPON_TRAIT_TIPS[label] || '';
                s += `<span class="wpn-trait${tip ? ' has-tooltip' : ''}" ${tip ? `data-tooltip="${escapeHtml(tip)}"` : ''}>${escapeHtml(label)}</span>`;
            }
            s += `</div>`;
        }
        if (locked && w.prerequisite) {
            s += `<div class="wpn-prereq">Requires: ${escapeHtml(w.prerequisite)}</div>`;
        }
        s += `</div>`;
        return s;
    }

    function renderGruntUpgrade(g) {
        const locked = !g.available;
        const statusCls = locked ? 'tt-locked' : 'tt-available';
        let s = `<div class="tt-theory ${statusCls}">`;
        s += `<div class="tt-theory-header"><span class="tt-theory-name">${escapeHtml(g.name)}</span></div>`;
        if (g.description) {
            s += `<div class="tt-apps"><div class="tt-app ${locked ? 'tt-app-locked' : 'tt-app-unlocked'}"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(g.description)}</span></div></div>`;
        }
        if (locked && g.prerequisite) {
            s += `<div class="tt-prereq">Requires: ${escapeHtml(g.prerequisite)}</div>`;
        }
        s += `</div>`;
        return s;
    }

    if (standard.length > 0) {
        html += '<h4 class="armory-tier-header">Standard Weapons</h4>';
        html += '<div class="armory-grid">';
        for (const w of standard) html += renderWeapon(w);
        html += '</div>';
    }

    if (tier1.length > 0) {
        const t1Unlocked = tier1.some(w => w.available);
        const t1Badge = t1Unlocked
            ? '<span class="armory-unlocked-badge">Unlocked</span>'
            : '<span class="armory-locked-badge">&#128274; Locked — Requires Advanced Manufacturing Plant</span>';
        html += `<h4 class="armory-tier-header">Tier 1 Upgrades ${t1Badge}</h4>`;
        html += '<div class="armory-grid">';
        for (const w of tier1) html += renderWeapon(w);
        html += '</div>';
    }

    if (tier2.length > 0) {
        const t2Unlocked = tier2.some(w => w.available);
        const t2Badge = t2Unlocked
            ? '<span class="armory-unlocked-badge">Unlocked</span>'
            : '<span class="armory-locked-badge">&#128274; Locked — Requires High-Tech Manufacturing Plant</span>';
        html += `<h4 class="armory-tier-header">Tier 2 Upgrades ${t2Badge}</h4>`;
        html += '<div class="armory-grid">';
        for (const w of tier2) html += renderWeapon(w);
        html += '</div>';
    }

    if (gruntUpgrades.length > 0) {
        html += '<h4 class="armory-tier-header">Grunt Upgrades</h4>';
        html += '<div class="tt-grid">';
        for (const g of gruntUpgrades) html += renderGruntUpgrade(g);
        html += '</div>';
    }

    if (weapons.length === 0 && gruntUpgrades.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">No armory data available.</div>';
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Buildings Modal ─────────────────────────────────────────

function openBuildingsModal() {
    if (!_lastColonyData) return;
    const existing = document.getElementById('buildings-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'buildings-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '800px';

    const built = _lastColonyData.buildings_built || [];
    const all = _lastColonyData.buildings_available || [];
    const available = all.filter(b => b.available);
    const locked = all.filter(b => b.locked);

    const bp = _lastColonyData.resources ? _lastColonyData.resources.build_points : 0;
    const rm = _lastColonyData.resources ? _lastColonyData.resources.raw_materials : 0;

    let html = `
        <div class="modal-header">
            <h2>Colony Buildings</h2>
            <button class="modal-close" onclick="document.getElementById('buildings-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Build Points</span>
                    <span class="resource-box-value">${bp}</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Raw Materials</span>
                    <span class="resource-box-value">${rm}</span>
                </div>
            </div>
    `;

    function renderBuilding(b) {
        const isBuilt = b.built_turn !== undefined;
        const isLocked = b.locked;
        const statusCls = isBuilt ? 'tt-completed' : (isLocked ? 'tt-locked' : 'tt-available');

        let s = `<div class="tt-theory ${statusCls}">`;
        s += `<div class="tt-theory-header">`;
        s += `<span class="tt-theory-name">${isBuilt ? '&#10003; ' : ''}${escapeHtml(b.name)}${b.is_milestone ? ' <span class="bld-milestone">Milestone</span>' : ''}</span>`;
        s += `<span class="tt-theory-rp">${b.bp_cost || ''} BP</span>`;
        s += `</div>`;

        if (b.invested_bp > 0 && !isBuilt) {
            const pct = Math.min(100, Math.round((b.invested_bp / b.bp_cost) * 100));
            s += `<div class="progress-bar" style="margin: 4px 0 6px;"><div class="progress-fill" style="width:${pct}%;background:var(--accent-cyan);"></div></div>`;
            s += `<div style="font-size:10px;color:var(--text-dim);">${b.invested_bp}/${b.bp_cost} BP invested</div>`;
        }

        if (isLocked && b.prerequisite) {
            s += `<div class="tt-prereq">Requires: ${escapeHtml(b.prerequisite)}</div>`;
        }

        if (b.description) {
            s += `<div class="tt-apps"><div class="tt-app ${isBuilt ? 'tt-app-unlocked' : 'tt-app-locked'}"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(b.description)}</span></div></div>`;
        }

        if (isBuilt && b.effects && b.effects.length > 0) {
            s += `<div class="tt-apps">`;
            for (const eff of b.effects) {
                s += `<div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#9733;</span><span class="tt-app-name">${escapeHtml(eff)}</span></div>`;
            }
            s += `</div>`;
        }

        s += `</div>`;
        return s;
    }

    // Built buildings
    if (built.length > 0) {
        html += '<h4 class="tt-section-header">Constructed</h4>';
        html += '<div class="tt-grid">';
        for (const b of built) html += renderBuilding({...b, built: true});
        html += '</div>';
    }

    // Available to build
    if (available.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:16px;">Available to Build</h4>';
        html += '<div class="tt-grid">';
        for (const b of available) html += renderBuilding(b);
        html += '</div>';
    }

    // Locked (research needed)
    if (locked.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:16px;">Locked (Research Required)</h4>';
        html += '<div class="tt-grid">';
        for (const b of locked) html += renderBuilding(b);
        html += '</div>';
    }

    if (built.length === 0 && available.length === 0 && locked.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">No building data available.</div>';
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Ancient Signs Modal ─────────────────────────────────────

let _lastAncientSignsData = null;

function renderAncientSigns(data) {
    _lastAncientSignsData = data;
}

function openAncientSignsModal() {
    const existing = document.getElementById('ancient-signs-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'ancient-signs-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '700px';

    const data = _lastAncientSignsData || {};
    const signs = data.ancient_signs_count || 0;
    const missionData = data.mission_data_count || 0;
    const breakthroughs = data.breakthroughs || [];
    const sites = data.ancient_sites || [];

    let html = `
        <div class="modal-header">
            <h2>Ancient Signs</h2>
            <button class="modal-close" onclick="document.getElementById('ancient-signs-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Signs Found</span>
                    <span class="resource-box-value">${signs}</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Mission Data</span>
                    <span class="resource-box-value">${missionData}</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Next Site At</span>
                    <span class="resource-box-value">${Math.ceil((signs + 1) / 3) * 3} signs</span>
                </div>
            </div>
    `;

    if (breakthroughs.length > 0) {
        html += '<h4 class="tt-section-header">Breakthroughs</h4>';
        html += '<div class="tt-grid">';
        for (const b of breakthroughs) {
            html += `<div class="tt-theory tt-completed">
                <div class="tt-theory-header"><span class="tt-theory-name">&#10003; ${escapeHtml(b.name)}</span></div>
                <div class="tt-apps"><div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(b.description)}</span></div></div>
            </div>`;
        }
        html += '</div>';
    }

    if (sites.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:16px;">Ancient Sites</h4>';
        html += '<div class="tt-grid">';
        for (const s of sites) {
            html += `<div class="tt-theory tt-available">
                <div class="tt-theory-header"><span class="tt-theory-name">${escapeHtml(s.name || 'Sector ' + s.sector_id)}</span><span class="tt-theory-rp">(${s.sector_id})</span></div>
            </div>`;
        }
        html += '</div>';
    }

    if (breakthroughs.length === 0 && sites.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">No ancient discoveries yet. Explore sectors to find ancient signs.</div>';
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Milestones Modal ────────────────────────────────────────

let _lastMilestonesData = null;

function renderMilestones(data) {
    _lastMilestonesData = data;
}

function openMilestonesModal() {
    const existing = document.getElementById('milestones-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'milestones-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '700px';

    const data = _lastMilestonesData || {};
    const completed = data.milestones_completed || 0;
    const total = 7;

    let html = `
        <div class="modal-header">
            <h2>Milestones</h2>
            <button class="modal-close" onclick="document.getElementById('milestones-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Milestones Completed</span>
                    <span class="resource-box-value">${completed} / ${total}</span>
                </div>
            </div>
            <div class="progress-bar" style="height:10px;border-radius:5px;"><div class="progress-fill" style="width:${Math.round(completed/total*100)}%;background:var(--accent-magenta);border-radius:5px;"></div></div>
    `;

    // Milestone markers
    html += '<div class="milestone-track">';
    for (let i = 1; i <= total; i++) {
        const cls = i <= completed ? 'milestone-dot milestone-done' : 'milestone-dot';
        const label = i === 7 ? 'End Game' : 'Milestone ' + i;
        html += `<div class="${cls}" title="${label}"><span>${i}</span></div>`;
    }
    html += '</div>';

    if (data.effects && data.effects.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:16px;">Milestone Effects</h4>';
        html += '<div class="tt-grid">';
        for (const eff of data.effects) {
            const done = eff.milestone <= completed;
            html += `<div class="tt-theory ${done ? 'tt-completed' : 'tt-locked'}">
                <div class="tt-theory-header"><span class="tt-theory-name">${done ? '&#10003; ' : ''}Milestone ${eff.milestone}</span></div>
                <div class="tt-apps">`;
            for (const desc of (eff.descriptions || [])) {
                html += `<div class="tt-app ${done ? 'tt-app-unlocked' : 'tt-app-locked'}"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(desc)}</span></div>`;
            }
            html += `</div></div>`;
        }
        html += '</div>';
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Conditions Modal ─────────────────────────────────────────

let _lastConditionsData = null;

function renderConditions(data) {
    _lastConditionsData = data;
}

function openConditionsModal() {
    const existing = document.getElementById('conditions-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'conditions-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '700px';

    const data = _lastConditionsData || {};
    const slots = data.slots || [];

    let html = `
        <div class="modal-header">
            <h2>Campaign Conditions</h2>
            <button class="modal-close" onclick="document.getElementById('conditions-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <table class="d100-table">
                <thead>
                    <tr><th>D100</th><th>#</th><th>Condition</th></tr>
                </thead>
                <tbody>
    `;

    for (const slot of slots) {
        const rangeStr = String(slot.d100_low).padStart(2, '0') + '–' + String(slot.d100_high).padStart(2, '0');
        if (slot.condition && slot.condition.name) {
            const c = slot.condition;
            let desc = `<strong>${escapeHtml(c.name)}</strong>`;
            if (c.description) desc += `: ${escapeHtml(c.description)}`;
            html += `<tr class="d100-row-filled"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry">${desc}</td></tr>`;
        } else {
            html += `<tr class="d100-row-empty"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry" style="color:var(--text-dim);font-style:italic;">—</td></tr>`;
        }
    }

    // If no slots data, show 10 empty slots
    if (slots.length === 0) {
        const defaultRanges = [[1,15],[16,30],[31,42],[43,52],[53,62],[63,72],[73,82],[83,90],[91,95],[96,100]];
        for (let i = 0; i < 10; i++) {
            const rangeStr = String(defaultRanges[i][0]).padStart(2, '0') + '–' + String(defaultRanges[i][1]).padStart(2, '0');
            html += `<tr class="d100-row-empty"><td class="d100-range">${rangeStr}</td><td class="d100-num">${i+1}</td><td class="d100-entry" style="color:var(--text-dim);font-style:italic;">—</td></tr>`;
        }
    }

    html += `</tbody></table></div>`;
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Lifeforms Modal ─────────────────────────────────────────

let _lastLifeformsData = null;

function renderLifeforms(data) {
    _lastLifeformsData = data;
}

function openLifeformsModal() {
    const existing = document.getElementById('lifeforms-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'lifeforms-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '800px';

    const data = _lastLifeformsData || {};
    const lifeforms = data.lifeforms || [];

    // Build full d100 table with 10 slots
    const slots = [];
    const defaultRanges = [
        [1,18],[19,32],[33,44],[45,54],[55,64],[65,73],[74,82],[83,89],[90,95],[96,100]
    ];
    for (let i = 0; i < 10; i++) {
        const lf = lifeforms.find(l => l.d100_low === defaultRanges[i][0]);
        slots.push({
            index: i + 1,
            d100_low: defaultRanges[i][0],
            d100_high: defaultRanges[i][1],
            entry: lf || null,
        });
    }
    // Override with actual ranges from data
    for (const lf of lifeforms) {
        const idx = slots.findIndex(s => s.d100_low === lf.d100_low);
        if (idx >= 0) {
            slots[idx].entry = lf;
            slots[idx].d100_low = lf.d100_low;
            slots[idx].d100_high = lf.d100_high;
        }
    }

    let html = `
        <div class="modal-header">
            <h2>Lifeform Encounters</h2>
            <button class="modal-close" onclick="document.getElementById('lifeforms-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <table class="d100-table">
                <thead>
                    <tr><th>D100</th><th>#</th><th>Entry</th></tr>
                </thead>
                <tbody>
    `;

    for (const slot of slots) {
        const rangeStr = String(slot.d100_low).padStart(2, '0') + '–' + String(slot.d100_high).padStart(2, '0');
        if (slot.entry) {
            const lf = slot.entry;
            let desc = `<strong>${escapeHtml(lf.name)}</strong>: Speed ${lf.mobility}", Combat +${lf.combat_skill}, Toughness ${lf.toughness}`;
            if (lf.weapons && lf.weapons.length) {
                desc += `, ${lf.weapons.map(w => escapeHtml(w)).join(', ')}`;
            }
            if (lf.special_rules && lf.special_rules.length) {
                desc += `, Special: ${lf.special_rules.map(r => escapeHtml(r.replace(/_/g, ' '))).join(', ')}`;
            }
            html += `<tr class="d100-row-filled"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry">${desc}</td></tr>`;
        } else {
            html += `<tr class="d100-row-empty"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry" style="color:var(--text-dim);font-style:italic;">—</td></tr>`;
        }
    }

    html += `</tbody></table></div>`;

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Enemies Modal ───────────────────────────────────────────

let _lastEnemiesData = null;

function renderEnemies(data) {
    _lastEnemiesData = data;
}

function openEnemiesModal() {
    const existing = document.getElementById('enemies-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'enemies-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '800px';

    const data = _lastEnemiesData || {};
    const tactical = data.tactical_enemies || [];
    const slyn = data.slyn || {};

    let html = `
        <div class="modal-header">
            <h2>Enemies</h2>
            <button class="modal-close" onclick="document.getElementById('enemies-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
    `;

    // Slyn status
    html += `<div class="resource-box">
        <div class="resource-box-item">
            <span class="resource-box-label">Slyn</span>
            <span class="resource-box-value ${slyn.active ? 'negative' : ''}">${slyn.active ? 'Active' : 'Dormant'}</span>
        </div>
        <div class="resource-box-item">
            <span class="resource-box-label">Slyn Encounters</span>
            <span class="resource-box-value">${slyn.encounters || 0}</span>
        </div>
        <div class="resource-box-item">
            <span class="resource-box-label">Slyn Victories</span>
            <span class="resource-box-value">${slyn.victories || 0}</span>
        </div>
    </div>`;

    // Tactical enemies
    if (tactical.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:12px;">Tactical Enemies</h4>';
        html += '<div class="tt-grid">';
        for (const te of tactical) {
            const statusCls = te.defeated ? 'tt-completed' : 'tt-available';
            const profile = te.profile || {};
            html += `<div class="tt-theory ${statusCls}">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">${te.defeated ? '&#10003; ' : ''}${escapeHtml(te.name)}</span>
                    <span class="tt-theory-rp">${capitalize(te.enemy_type.replace(/_/g, ' '))}</span>
                </div>
                <div class="wpn-stats" style="margin:4px 0;">
                    ${profile.speed ? `<span><span class="wpn-stat-label">Speed</span> ${profile.speed}"</span>` : ''}
                    ${profile.combat_skill !== undefined ? `<span><span class="wpn-stat-label">Combat</span> +${profile.combat_skill}</span>` : ''}
                    ${profile.toughness ? `<span><span class="wpn-stat-label">Tough</span> ${profile.toughness}</span>` : ''}
                    ${profile.panic_range ? `<span><span class="wpn-stat-label">Panic</span> ${profile.panic_range}</span>` : ''}
                </div>
                <div class="tt-apps">
                    <div class="tt-app tt-app-locked"><span class="tt-app-icon">&#9632;</span><span class="tt-app-name">Sectors: ${te.sectors.length ? te.sectors.join(', ') : 'Unknown'}</span></div>
                    <div class="tt-app tt-app-locked"><span class="tt-app-icon">&#9650;</span><span class="tt-app-name">Intel: ${te.enemy_info_count}</span></div>
                    ${te.boss_located ? '<div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#9733;</span><span class="tt-app-name">Boss Located</span></div>' : ''}
                    ${te.strongpoint_located ? '<div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#9632;</span><span class="tt-app-name">Strongpoint Located</span></div>' : ''}
                </div>
            </div>`;
        }
        html += '</div>';
    }

    if (tactical.length === 0 && !slyn.active) {
        html += '<div style="color: var(--text-dim); padding: 12px; margin-top: 12px;">No tactical enemies encountered yet.</div>';
    }

    html += '</div>';
    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Augmentations Modal ─────────────────────────────────────

let _lastAugmentationsData = null;

function renderAugmentations(data) {
    _lastAugmentationsData = data;
    // Refresh modal if open
    if (document.getElementById('augmentations-modal')) {
        openAugmentationsModal();
    }
}

function openAugmentationsModal() {
    const existing = document.getElementById('augmentations-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'augmentations-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '750px';

    const data = _lastAugmentationsData || {};
    const ap = data.augmentation_points != null ? data.augmentation_points : (_lastColonyData ? _lastColonyData.resources.augmentation_points : 0);
    const nextCost = data.next_cost || '?';
    const ownedCount = data.owned_count || 0;
    const boughtThisTurn = data.bought_this_turn || false;
    const augmentations = data.augmentations || [];

    let html = `
        <div class="modal-header">
            <h2>Augmentations</h2>
            <button class="modal-close" onclick="document.getElementById('augmentations-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Augmentation Points</span>
                    <span class="resource-box-value">${ap}</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Next Cost</span>
                    <span class="resource-box-value">${nextCost} AP</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Owned</span>
                    <span class="resource-box-value">${ownedCount}</span>
                </div>
            </div>
            ${boughtThisTurn ? '<div style="color: var(--text-dim); padding: 4px 12px; font-size: 0.85em;">Already purchased an augmentation this turn.</div>' : ''}
            <div class="tech-tree">`;

    if (augmentations.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">Augmentation options become available through Genetic Advancement research.</div>';
    }

    for (const aug of augmentations) {
        const statusCls = aug.owned ? 'tt-completed' : 'tt-available';
        const statusLabel = aug.owned ? '<span style="color: var(--accent-green);">&#10003; Owned</span>' : '';
        const milestoneTag = aug.is_milestone ? ' <span class="bld-milestone">Milestone</span>' : '';

        html += `
            <div class="tt-theory ${statusCls}">
                <div class="tt-header">
                    <span class="tt-name">${escapeHtml(aug.name)}${milestoneTag}</span>
                    ${statusLabel}
                </div>
                <div class="tt-apps">${escapeHtml(aug.description)}</div>
            </div>`;
    }

    html += `</div></div>`;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Artifacts ───────────────────────────────────────────────

let _lastArtifactsData = null;

function renderArtifacts(data) {
    _lastArtifactsData = data;
    if (document.getElementById('artifacts-modal')) {
        openArtifactsModal();
    }
}

function openArtifactsModal() {
    const existing = document.getElementById('artifacts-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'artifacts-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '750px';

    const data = _lastArtifactsData || {};
    const artifacts = data.artifacts || [];

    let html = `
        <div class="modal-header">
            <h2>Artifacts</h2>
            <button class="modal-close" onclick="document.getElementById('artifacts-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="tech-tree">`;

    if (artifacts.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">No artifacts discovered yet. Search Ancient Sites to find alien artifacts.</div>';
    }

    for (const art of artifacts) {
        const typeTag = art.artifact_type === 'single_use' ? '<span class="wpn-trait">Single-Use</span>'
            : art.artifact_type === 'equipment' ? '<span class="wpn-trait">Equipment</span>'
            : '<span class="wpn-trait">Colony Item</span>';
        const assignedTo = art.assigned_to ? `<div class="tt-prereq">Assigned to: ${escapeHtml(art.assigned_to)}</div>` : '';
        const usedLabel = art.used ? '<span style="color: var(--text-dim);">(Used)</span>' : '';

        html += `
            <div class="tt-theory tt-completed">
                <div class="tt-header">
                    <span class="tt-name">${escapeHtml(art.name)} ${usedLabel}</span>
                    ${typeTag}
                </div>
                <div class="tt-apps">${escapeHtml(art.description)}</div>
                ${assignedTo}
            </div>`;
    }

    html += `</div></div>`;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Calamities ──────────────────────────────────────────────

let _lastCalamitiesData = null;

function renderCalamities(data) {
    _lastCalamitiesData = data;
    if (document.getElementById('calamities-modal')) {
        openCalamitiesModal();
    }
}

function openCalamitiesModal() {
    const existing = document.getElementById('calamities-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'calamities-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '700px';

    const data = _lastCalamitiesData || {};
    const points = data.calamity_points || 0;
    const events = data.calamity_events || [];

    let html = `
        <div class="modal-header">
            <h2>Calamities</h2>
            <button class="modal-close" onclick="document.getElementById('calamities-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Calamity Points</span>
                    <span class="resource-box-value">${points}</span>
                </div>
            </div>`;

    if (events.length === 0) {
        html += '<div style="color: var(--text-dim); padding: 12px;">No calamity events yet.</div>';
    }

    for (const evt of events) {
        html += `
            <div class="tt-theory tt-completed">
                <div class="tt-header">
                    <span class="tt-name">Turn ${evt.turn}: ${escapeHtml(evt.name)}</span>
                </div>
                <div class="tt-apps">${escapeHtml(evt.description)}</div>
            </div>`;
    }

    html += `</div>`;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Morale ──────────────────────────────────────────────────

let _lastMoraleData = null;

function renderMorale(data) {
    _lastMoraleData = data;
    if (document.getElementById('morale-modal')) {
        openMoraleModal();
    }
}

function openMoraleModal() {
    const existing = document.getElementById('morale-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'morale-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '750px';

    const data = _lastMoraleData || {};
    const morale = data.morale != null ? data.morale : (_lastColonyData ? _lastColonyData.morale : 0);
    const politicalUpheaval = data.political_upheaval || 0;
    const inCrisis = data.in_crisis || false;
    const incidents = data.incidents || [];

    const moraleCls = morale >= 0 ? 'positive' : 'negative';

    let html = `
        <div class="modal-header">
            <h2>Colony Morale</h2>
            <button class="modal-close" onclick="document.getElementById('morale-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Morale</span>
                    <span class="resource-box-value ${moraleCls}">${morale}</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Political Upheaval</span>
                    <span class="resource-box-value ${politicalUpheaval > 0 ? 'negative' : ''}">${politicalUpheaval}</span>
                </div>
            </div>
            ${inCrisis ? '<div style="color: var(--danger); padding: 8px 12px; font-weight: bold; border: 1px solid var(--danger); margin-bottom: 12px;">CRISIS IN EFFECT — Morale fixed at 0. RP/BP/RM reduced by 1.</div>' : ''}

            <div style="color: var(--text-dim); padding: 8px 12px; font-size: 0.85em; border-bottom: 1px solid var(--panel-border); margin-bottom: 12px;">
                Morale decreases by 1 each turn, by 1 per battle casualty, and by 1 per point of colony damage.
                At -10 or worse, a Morale Incident occurs (morale resets to 0).
            </div>

            <h3 style="padding: 0 12px; color: var(--text-bright); font-size: 0.95em;">Morale Incidents</h3>
            <table class="d100-table" style="margin-top: 8px;">
                <thead>
                    <tr><th class="d100-range">D100</th><th>Incident</th><th>Description</th></tr>
                </thead>
                <tbody>
                    <tr><td class="d100-range">01-10</td><td>Loyalty Loss</td><td>Random character loses one Loyalty level</td></tr>
                    <tr><td class="d100-range">11-25</td><td>Protests</td><td>One trooper unavailable next turn (unless Pitched Battle)</td></tr>
                    <tr><td class="d100-range">26-35</td><td>Sabotage</td><td>1D6 Colony Damage (unmitigable)</td></tr>
                    <tr><td class="d100-range">36-55</td><td>Work Stoppage</td><td>-3 to BP and RP earned this turn</td></tr>
                    <tr><td class="d100-range">56-75</td><td>Colonist Demands</td><td>Assign characters to security duty (1D6+Savvy, 5+ to resolve)</td></tr>
                    <tr><td class="d100-range">76-00</td><td>Political Strife</td><td>+1 Political Upheaval, Crisis check required</td></tr>
                </tbody>
            </table>`;

    if (incidents.length > 0) {
        html += '<h3 style="padding: 12px 12px 0; color: var(--text-bright); font-size: 0.95em;">Incident History</h3>';
        for (const inc of incidents) {
            html += `
                <div class="tt-theory tt-completed">
                    <div class="tt-header">
                        <span class="tt-name">Turn ${inc.turn}: ${escapeHtml(inc.name)}</span>
                    </div>
                    <div class="tt-apps">${escapeHtml(inc.description)}</div>
                </div>`;
        }
    }

    html += `</div>`;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Colony Log (sidebar trigger) ────────────────────────────

function openColonyLog() {
    // If we have a websocket, request the log from the server
    if (window._ws && window._ws.readyState === 1) {
        window._ws.send(JSON.stringify({ type: 'request_log' }));
    }
}

// ── Sector Detail Panel ─────────────────────────────────────

let _lastMapData = null;
let _selectedSectorIndex = null;

// Sector selection mode state
let _sectorSelectMode = false;
let _sectorSelectValidIds = [];
let _sectorSelectCallback = null;
let _sectorSelectBtnLabel = 'Select This Sector';

function enableMapSelection(validIds, callback, btnLabel) {
    _sectorSelectMode = true;
    _sectorSelectValidIds = validIds;
    _sectorSelectCallback = callback;
    _sectorSelectBtnLabel = btnLabel || 'Select This Sector';

    // Add selection-mode class to map and highlight valid sectors
    const container = document.querySelector('.map-container');
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

    const container = document.querySelector('.map-container');
    if (container) container.classList.remove('selection-mode');

    document.querySelectorAll('.map-cell.selectable').forEach(el => el.classList.remove('selectable'));
    document.querySelectorAll('.map-cell.not-selectable').forEach(el => el.classList.remove('not-selectable'));
}

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
        'unknown': 'var(--text-dim)',
        'explored': 'var(--accent-cyan)',
        'exploited': 'var(--accent-green)',
        'investigated': 'var(--accent-yellow)',
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
            ${s.has_ancient_sign ? '<div style="color: var(--accent-yellow);">&#9733; Ancient Sign detected</div>' : ''}
            ${s.has_ancient_site ? '<div style="color: var(--accent-yellow);">&#9733; Ancient Site present</div>' : ''}
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

// ── Utilities ───────────────────────────────────────────────

// ── Roster character edit modal ──────────────────────────────

function openRosterCharEdit(charName) {
    if (!_lastRosterData) return;
    const c = _lastRosterData.characters.find(ch => ch.name === charName);
    if (!c) return;

    const existing = document.getElementById('char-edit-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'char-edit-modal';
    overlay.className = 'modal-overlay';
    overlay.style.zIndex = '1001';

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '550px';

    modal.innerHTML = `
        <div class="modal-header">
            <h2>Edit Character</h2>
            <button class="modal-close" id="rce-cancel">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="edit-form">
                <div class="form-row">
                    <label>Title <span style="color:var(--text-dim)">(optional)</span></label>
                    <input type="text" id="rce-title" value="${escapeHtml(c.title || '')}" placeholder="e.g. Sgt., Dr.">
                </div>
                <div class="form-row">
                    <label>Name</label>
                    <input type="text" id="rce-name" value="${escapeHtml(c.name)}">
                </div>
                <div class="form-row">
                    <label>Role <span style="color:var(--text-dim)">(optional)</span></label>
                    <input type="text" id="rce-role" value="${escapeHtml(c.role || '')}" placeholder="e.g. Lead researcher">
                </div>
                <div class="form-row">
                    <label>Background <span style="color:var(--text-dim)">(optional)</span></label>
                    <textarea id="rce-narrative" rows="4">${escapeHtml(c.narrative || '')}</textarea>
                </div>
                <div style="display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end;">
                    <button class="btn" id="rce-cancel2">Cancel</button>
                    <button class="btn btn-primary" id="rce-save">Save</button>
                </div>
            </div>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    document.getElementById('rce-save').onclick = () => {
        const newTitle = document.getElementById('rce-title').value.trim();
        const newName = document.getElementById('rce-name').value.trim();
        const newRole = document.getElementById('rce-role').value.trim();
        const newNarrative = document.getElementById('rce-narrative').value.trim();
        if (!newName) return;

        if (window._ws && window._ws.readyState === 1) {
            window._ws.send(JSON.stringify({
                type: 'update_roster',
                character_name: charName,
                updates: { title: newTitle, name: newName, role: newRole, narrative: newNarrative },
            }));
        }
        overlay.remove();
    };

    const close = () => overlay.remove();
    document.getElementById('rce-cancel').onclick = close;
    document.getElementById('rce-cancel2').onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };

    document.getElementById('rce-name').focus();
    document.getElementById('rce-name').select();
}

// ── Colony Log Modal ────────────────────────────────────────

let _logCurrentTurn = 0;
let _logAvailableTurns = [];

function openColonyLogModal(markdown, currentTurn, availableTurns) {
    _logCurrentTurn = currentTurn || 0;
    _logAvailableTurns = availableTurns || [];

    const existing = document.getElementById('log-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'log-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '700px';

    modal.innerHTML = _buildLogModalHtml(markdown);

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    _wireLogNav();

    const escHandler = (e) => {
        if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

function _buildLogModalHtml(markdown) {
    const turns = _logAvailableTurns;
    const cur = _logCurrentTurn;
    const idx = turns.indexOf(cur);
    const hasPrev = idx > 0;
    const hasNext = idx < turns.length - 1;

    let navHtml = '';
    if (turns.length > 1) {
        navHtml = `<div class="log-nav">
            <button class="log-nav-btn" id="log-prev" ${hasPrev ? '' : 'disabled'}>&#9664; Day ${hasPrev ? turns[idx - 1] : ''}</button>
            <span class="log-nav-label">Day ${cur}</span>
            <button class="log-nav-btn" id="log-next" ${hasNext ? '' : 'disabled'}>Day ${hasNext ? turns[idx + 1] : ''} &#9654;</button>
        </div>`;
    }

    return `
        <div class="modal-header">
            <h2>Colony Log</h2>
            <button class="modal-close" onclick="document.getElementById('log-modal').remove()">&#10005;</button>
        </div>
        ${navHtml}
        <div class="modal-body" id="log-modal-body">
            <div class="colony-log-content">${simpleMarkdown(markdown)}</div>
        </div>
    `;
}

function _wireLogNav() {
    const prevBtn = document.getElementById('log-prev');
    const nextBtn = document.getElementById('log-next');
    if (prevBtn) {
        prevBtn.onclick = () => {
            const idx = _logAvailableTurns.indexOf(_logCurrentTurn);
            if (idx > 0) _requestLogTurn(_logAvailableTurns[idx - 1]);
        };
    }
    if (nextBtn) {
        nextBtn.onclick = () => {
            const idx = _logAvailableTurns.indexOf(_logCurrentTurn);
            if (idx < _logAvailableTurns.length - 1) _requestLogTurn(_logAvailableTurns[idx + 1]);
        };
    }
}

function _requestLogTurn(turn) {
    if (window._ws && window._ws.readyState === 1) {
        window._ws.send(JSON.stringify({ type: 'request_log', turn: turn }));
    }
}

function _updateLogModalContent(markdown, currentTurn, availableTurns) {
    _logCurrentTurn = currentTurn || _logCurrentTurn;
    _logAvailableTurns = availableTurns || _logAvailableTurns;

    const modal = document.querySelector('#log-modal .modal-content');
    if (modal) {
        modal.innerHTML = _buildLogModalHtml(markdown);
        _wireLogNav();
    }
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

function inlineMarkdown(text) {
    return text
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
}
