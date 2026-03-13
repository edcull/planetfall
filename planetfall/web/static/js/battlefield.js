/**
 * Planetfall Web UI — Battlefield grid renderer.
 *
 * Features:
 *   - Graphical terrain with icons/colors
 *   - Zone detail panel (like campaign map sector panel)
 *   - Click-to-deploy zones
 *   - Interactive reaction dice assignment
 */

// Terrain config
const TERRAIN_LABELS = {
    'open': '', 'light_cover': 'SC', 'heavy_cover': 'C',
    'high_ground': 'HG', 'impassable': 'XX',
};
const TERRAIN_NAMES = {
    'open': 'Open Ground', 'light_cover': 'Scatter Cover', 'heavy_cover': 'Cover',
    'high_ground': 'High Ground', 'impassable': 'Impassable',
};
const TERRAIN_ICONS = {
    'open': '', 'light_cover': '&#9683;', 'heavy_cover': '&#9632;',
    'high_ground': '&#9650;', 'impassable': '&#10005;',
};
const TERRAIN_DESCRIPTIONS = {
    'open': 'No cover modifier',
    'light_cover': 'Scatter: exact hit rolls are absorbed',
    'heavy_cover': 'Cover: 6+ to hit when targeted',
    'high_ground': 'High ground: negates cover (except direct cover)',
    'impassable': 'Cannot enter this zone',
};

// Store latest battlefield data for lookups
let _bfData = null;
let _bfFigureMap = {};
let _selectedZone = null;
let _missionBriefingData = null;  // cached mission info for persistent display

// ── Deployment zone selection mode ──────────────────────────
let _deploySelectMode = false;
let _deployValidZones = [];  // [{row, col, label}]
let _deployCallback = null;

function enableBattlefieldDeploySelect(validZones, callback) {
    _deploySelectMode = true;
    _deployValidZones = validZones;
    _deployCallback = callback;
    // Re-render to show deploy highlights
    if (_bfData) renderBattlefield(_bfData);
}

function disableBattlefieldDeploySelect() {
    _deploySelectMode = false;
    _deployValidZones = [];
    _deployCallback = null;
}

// ── Movement selection mode ──────────────────────────────────
let _movementSelectMode = false;
let _movementZones = [];    // [{row, col, index, move_type, terrain, figs, is_jump}]
let _movementCallback = null;

function enableBattlefieldMovementSelect(zones, callback) {
    _movementSelectMode = true;
    _movementZones = zones;
    _movementCallback = callback;
    _applyMovementHighlights();
}

function disableBattlefieldMovementSelect() {
    _movementSelectMode = false;
    _movementZones = [];
    _movementCallback = null;
    document.querySelectorAll('.bf-move-zone, .bf-dash-zone').forEach(el => {
        el.classList.remove('bf-move-zone', 'bf-dash-zone');
    });
}

function _applyMovementHighlights() {
    for (const z of _movementZones) {
        const cell = document.querySelector(`.bf-cell[data-zone="${z.row},${z.col}"]`);
        if (cell) {
            cell.classList.add(z.move_type === 'dash' ? 'bf-dash-zone' : 'bf-move-zone');
        }
    }
}

// ── Zone selection mode (movement, etc.) ─────────────────────
let _zoneSelectMode = false;
let _zoneSelectValid = [];  // [{row, col, index, label}]
let _zoneSelectCallback = null;

function enableBattlefieldZoneSelect(validZones, callback) {
    _zoneSelectMode = true;
    _zoneSelectValid = validZones;
    _zoneSelectCallback = callback;
    // Highlight valid zones on current battlefield
    _applyZoneSelectHighlights();
}

function disableBattlefieldZoneSelect() {
    _zoneSelectMode = false;
    _zoneSelectValid = [];
    _zoneSelectCallback = null;
    // Remove highlights
    document.querySelectorAll('.bf-zone-selectable').forEach(el => el.classList.remove('bf-zone-selectable'));
}

function _applyZoneSelectHighlights() {
    for (const z of _zoneSelectValid) {
        const cell = document.querySelector(`.bf-cell[data-zone="${z.row},${z.col}"]`);
        if (cell) cell.classList.add('bf-zone-selectable');
    }
}

// ── Main Renderer ───────────────────────────────────────────

function renderBattlefield(data) {
    const display = document.getElementById('display-area');
    display.innerHTML = '';

    _bfData = data;

    // Build figure lookup: "row,col" -> [figure, ...]
    _bfFigureMap = {};
    for (const fig of data.figures) {
        const key = `${fig.zone[0]},${fig.zone[1]}`;
        if (!_bfFigureMap[key]) _bfFigureMap[key] = [];
        _bfFigureMap[key].push(fig);
    }

    // Build overlay lookup
    const overlayMap = data.overlay ? data.overlay.zones : {};

    // Deploy zone lookup
    const deployZoneSet = new Set();
    if (_deploySelectMode) {
        for (const z of _deployValidZones) {
            deployZoneSet.add(`${z.row},${z.col}`);
        }
    }

    // Container with grid + detail panel (like campaign map)
    let html = '<div class="bf-container">';
    html += `<div class="bf-grid-wrapper">`;

    // Overlay toggle buttons (only when overlays data is available)
    if (data.overlays) {
        const currentMode = data.overlay ? data.overlay.mode : null;
        html += '<div class="bf-overlay-toggles">';
        html += '<span class="bf-overlay-label">Overlay:</span>';
        for (const mode of ['movement', 'shooting', 'vision']) {
            const active = currentMode === mode ? ' active' : '';
            const icon = mode === 'movement' ? '&#9654;' : mode === 'shooting' ? '&#9678;' : '&#9673;';
            html += `<button class="bf-overlay-btn${active}" data-overlay="${mode}">${icon} ${mode.charAt(0).toUpperCase() + mode.slice(1)}</button>`;
        }
        const noneActive = !currentMode ? ' active' : '';
        html += `<button class="bf-overlay-btn${noneActive}" data-overlay="none">None</button>`;
        html += '</div>';
    }

    html += `<div class="battlefield" style="grid-template-columns: repeat(${data.cols}, 1fr);">`;

    for (let r = 0; r < data.rows; r++) {
        for (let c = 0; c < data.cols; c++) {
            const zone = data.zones[r][c];
            const key = `${r},${c}`;
            const figs = _bfFigureMap[key] || [];
            const overlayClass = overlayMap[key] ? `overlay-${overlayMap[key]}` : '';
            const isDeployZone = deployZoneSet.has(key);
            const isSelected = _selectedZone === key;

            let cellClass = `bf-cell terrain-${zone.terrain} ${overlayClass}`;
            if (isDeployZone) cellClass += ' bf-deploy-zone';
            if (isSelected) cellClass += ' bf-cell-selected';

            // Terrain icon (top-left)
            const tIcon = TERRAIN_ICONS[zone.terrain] || '';
            const terrainHtml = tIcon
                ? `<span class="bf-terrain-icon">${tIcon}</span>`
                : '';

            // Terrain label abbreviation
            const tLabel = TERRAIN_LABELS[zone.terrain] || '';
            const labelHtml = tLabel
                ? `<span class="terrain-label">${tLabel}</span>`
                : '';

            // Objective marker — star + label
            let objHtml = '';
            if (zone.has_objective) {
                const oLabel = zone.objective_label || 'OBJ';
                const isComplete = oLabel.includes('✓');
                const cls = isComplete ? 'bf-objective obj-complete' : 'bf-objective';
                objHtml = `<span class="${cls}" title="${escapeHtml(oLabel)}"><span class="obj-star">&#9733;</span><span class="obj-label">${escapeHtml(oLabel)}</span></span>`;
            }

            // Figures
            let figsHtml = '';
            if (figs.length > 0) {
                figsHtml = '<div class="figures">';
                for (const fig of figs) {
                    let figClass = `bf-fig ${fig.color}`;
                    if (fig.is_contact) figClass += ' contact';
                    if (fig.is_active) figClass += ' active-fig';
                    if (fig.is_highlighted) figClass += ' highlighted';
                    // Contacts use radar icon, normal figures use label
                    const figContent = fig.is_contact
                        ? '&#9432;'  // circled info / radar blip
                        : escapeHtml(fig.label);
                    figsHtml += `<span class="${figClass}" title="${escapeHtml(fig.name)}">${figContent}</span>`;
                }
                figsHtml += '</div>';
            }

            // Coordinate
            const coordHtml = `<span class="bf-coord">${r},${c}</span>`;

            // Deploy indicator
            const deployHtml = isDeployZone ? '<span class="bf-deploy-marker">&#9654;</span>' : '';

            html += `<div class="${cellClass}" data-zone="${r},${c}">${terrainHtml}${labelHtml}${objHtml}${figsHtml}${coordHtml}${deployHtml}</div>`;
        }
    }

    html += '<svg class="bf-los-overlay" id="bf-los-overlay"></svg>';
    html += '</div>';  // close battlefield grid
    html += '</div>';  // close bf-grid-wrapper

    // Right panel: mission info (persistent) + zone detail (on click)
    if (_missionBriefingData) {
        html += '<button class="info-panel-toggle" id="combat-info-toggle" onclick="toggleInfoPanel(\'combat-info-toggle\',\'bf-mission-panel\')"><span class="toggle-arrow">&#9660;</span> Mission Info</button>';
        html += '<div class="mission-info-panel" id="bf-mission-panel">';
        // Zone detail area (above mission info, shown when zone clicked)
        html += '<div class="bf-detail-panel" id="bf-detail-panel"></div>';
        html += '<div class="bf-mission-info-divider"></div>';
        // Use current battlefield zones for live objective progress
        const liveData = Object.assign({}, _missionBriefingData, { battlefield: data });
        html += _buildMissionInfoHtml(liveData);
        html += '</div>';
    } else {
        html += '<div class="bf-detail-panel" id="bf-detail-panel"><div class="bf-detail-empty">Click a zone to view details</div></div>';
    }

    html += '</div>';  // close bf-container

    // Legend (full width below map + info panel)
    html += '<div class="bf-legend-box">';
    html += buildLegend(data);
    html += '</div>';

    display.innerHTML = html;

    // Wire click handlers
    display.querySelectorAll('.bf-cell[data-zone]').forEach(cell => {
        cell.addEventListener('click', (e) => {
            e.stopPropagation();
            const zoneKey = cell.dataset.zone;

            // If in deploy mode and this is a valid zone, trigger callback
            if (_deploySelectMode) {
                const [r, c] = zoneKey.split(',').map(Number);
                const match = _deployValidZones.find(z => z.row === r && z.col === c);
                if (match && _deployCallback) {
                    _deployCallback(match);
                    return;
                }
            }

            // If in zone select mode (movement etc.), trigger callback
            if (_zoneSelectMode) {
                const [r, c] = zoneKey.split(',').map(Number);
                const match = _zoneSelectValid.find(z => z.row === r && z.col === c);
                if (match && _zoneSelectCallback) {
                    _zoneSelectCallback(match);
                    return;
                }
            }

            // If in movement select mode, show zone details with move/dash button
            if (_movementSelectMode) {
                const [r, c] = zoneKey.split(',').map(Number);
                const match = _movementZones.find(z => z.row === r && z.col === c);
                selectBattlefieldZone(zoneKey);
                if (match) {
                    _showMovementZoneAction(match);
                }
                return;
            }

            // Normal click: show zone details in panel
            selectBattlefieldZone(zoneKey);
        });
    });

    // Restore selected zone panel if still valid
    if (_selectedZone && _bfData) {
        updateZoneDetailPanel(_selectedZone);
    }

    // Wire overlay toggle buttons
    display.querySelectorAll('.bf-overlay-btn[data-overlay]').forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.overlay;
            _switchOverlay(mode === 'none' ? null : mode);
        });
    });

    // Re-apply zone select highlights if active
    if (_zoneSelectMode) {
        _applyZoneSelectHighlights();
    }
    if (_movementSelectMode) {
        _applyMovementHighlights();
    }
}

// ── Movement Zone Action ─────────────────────────────────────

function _showMovementZoneAction(zone) {
    const panel = document.getElementById('bf-detail-panel');
    if (!panel) return;

    // Remove any existing action button
    const existing = panel.querySelector('.bf-move-action');
    if (existing) existing.remove();

    const isDash = zone.move_type === 'dash';
    const label = isDash ? 'Dash here (uses action)' : 'Move here';
    const btnClass = isDash ? 'bf-move-action bf-dash-action-btn' : 'bf-move-action bf-move-action-btn';

    const btn = document.createElement('button');
    btn.className = btnClass;
    btn.textContent = label;
    btn.onclick = () => {
        if (_movementCallback) _movementCallback(zone);
    };
    panel.appendChild(btn);
}

// ── Overlay Switching ────────────────────────────────────────

function _switchOverlay(mode) {
    if (!_bfData || !_bfData.overlays) return;

    if (mode && _bfData.overlays[mode]) {
        _bfData.overlay = _bfData.overlays[mode];
    } else {
        _bfData.overlay = null;
    }
    // Re-render preserving selection state
    renderBattlefield(_bfData);
}

// ── Zone Detail Panel ───────────────────────────────────────

function selectBattlefieldZone(zoneKey) {
    // Deselect previous
    document.querySelectorAll('.bf-cell-selected').forEach(el => el.classList.remove('bf-cell-selected'));

    _selectedZone = zoneKey;

    // Highlight new
    const cell = document.querySelector(`.bf-cell[data-zone="${zoneKey}"]`);
    if (cell) cell.classList.add('bf-cell-selected');

    updateZoneDetailPanel(zoneKey);

    // Draw line from active figure to selected zone
    clearLosLine();

    // Green movement line
    if (_movementSelectMode && _bfData) {
        const [r, c] = zoneKey.split(',').map(Number);
        const isValidMove = _movementZones.some(z => z.row === r && z.col === c);
        if (isValidMove) {
            const activeFig = Object.values(_bfFigureMap).flat().find(f => f.is_active);
            if (activeFig) {
                drawLosLine(activeFig.zone, [r, c], 'move-line');
            }
        }
    }

    // Red LoS line for shoot targets
    if (_activeShootTargets && _activeShootTargets.length > 0 && _bfData) {
        const [r, c] = zoneKey.split(',').map(Number);
        const hasTarget = _activeShootTargets.some(t => {
            const fig = Object.values(_bfFigureMap).flat().find(f => f.name === t.name);
            return fig && fig.zone[0] === r && fig.zone[1] === c;
        });
        if (hasTarget) {
            const activeFig = Object.values(_bfFigureMap).flat().find(f => f.is_active);
            if (activeFig) {
                drawLosLine(activeFig.zone, [r, c]);
            }
        }
    }
}

function updateZoneDetailPanel(zoneKey) {
    const panel = document.getElementById('bf-detail-panel');
    if (!panel || !_bfData) return;

    const [r, c] = zoneKey.split(',').map(Number);
    const zone = _bfData.zones[r]?.[c];
    if (!zone) return;

    const figs = _bfFigureMap[zoneKey] || [];
    const terrainName = TERRAIN_NAMES[zone.terrain] || zone.terrain;
    const terrainIcon = TERRAIN_ICONS[zone.terrain] || '';
    const terrainDesc = TERRAIN_DESCRIPTIONS[zone.terrain] || '';

    let html = '';

    // Header
    html += `<div class="bf-detail-header">
        <h3>Zone (${r},${c})</h3>
    </div>`;

    // Terrain info
    html += `<div class="stat-list">
        <div class="stat-row"><span class="label">Terrain</span><span class="value">${terrainIcon} ${terrainName}</span></div>
    </div>`;
    if (terrainDesc) {
        html += `<div class="bf-detail-desc">${terrainDesc}</div>`;
    }

    // Objective
    if (zone.has_objective) {
        html += `<div class="bf-detail-objective">&#9733; Objective: ${escapeHtml(zone.objective_label) || 'Active'}</div>`;
    }

    // Figures
    if (figs.length > 0) {
        html += '<div class="bf-detail-divider"></div>';

        for (const fig of figs) {
            const color = figColor(fig.color);
            html += '<div class="bf-detail-fig">';
            html += `<div class="bf-detail-fig-header">
                <span class="bf-detail-fig-name" style="color:${color}">${escapeHtml(fig.name)}</span>
                <span class="bf-detail-fig-label" style="color:${color}">${escapeHtml(fig.label)}</span>
            </div>`;

            if (fig.is_contact) {
                html += '<div class="bf-detail-fig-info">&#9432; Unidentified contact — within sensor range</div>';
            } else {
                const statusLabel = fig.status !== 'active' ? ` [${fig.status}]` : '';
                html += '<div class="bf-detail-fig-stats">';
                html += `<div class="stat-chip"><span class="label">Spd</span><span class="val">${fig.speed}"</span></div>`;
                html += `<div class="stat-chip"><span class="label">CS</span><span class="val">+${fig.combat_skill}</span></div>`;
                html += `<div class="stat-chip"><span class="label">T</span><span class="val">${fig.toughness}</span></div>`;
                if (fig.weapon) {
                    html += `<span class="bf-fig-weapon-inline">${escapeHtml(fig.weapon)}</span>`;
                }
                if (fig.stun_markers > 0) {
                    html += `<span class="bf-fig-status stun">Stun x${fig.stun_markers}</span>`;
                }
                if (statusLabel) {
                    html += `<span class="bf-fig-status">${statusLabel}</span>`;
                }
                html += '</div>';

                // Shoot buttons for valid targets during action selection
                if (typeof _activeShootTargets !== 'undefined' && _activeShootTargets.length > 0) {
                    const targets = _activeShootTargets.filter(t => t.name === fig.name);
                    for (const t of targets) {
                        const aidTag = t.use_aid ? ' [Aid +1]' : '';
                        const mods = (t.modifiers && t.modifiers.length) ? ' [' + t.modifiers.join(', ') + ']' : '';
                        html += `<button class="btn-shoot-target" data-desc="${escapeHtml(t.desc)}" data-target-name="${escapeHtml(t.name)}">`
                            + `Shoot — ${t.range_label} (${t.eff_label}, ${t.shots} shot${t.shots !== 1 ? 's' : ''})${mods}${aidTag}`
                            + `</button>`;
                    }
                }
            }
            html += '</div>';
        }
    } else {
        html += '<div class="bf-detail-divider"></div>';
        html += '<div class="bf-detail-empty-zone">No units in this zone</div>';
    }


    panel.innerHTML = html;
    panel.classList.add('active');

    // Wire up shoot buttons with LoS line on hover
    panel.querySelectorAll('.btn-shoot-target').forEach(btn => {
        const targetName = btn.dataset.targetName;
        btn.onmouseenter = () => {
            // Find the active figure zone and target zone
            const activeFig = _bfData ? Object.values(_bfFigureMap).flat().find(f => f.is_active) : null;
            const targetFig = _bfData ? Object.values(_bfFigureMap).flat().find(f => f.name === targetName) : null;
            if (activeFig && targetFig) {
                drawLosLine(activeFig.zone, targetFig.zone);
            }
        };
        btn.onmouseleave = () => clearLosLine();
        btn.onclick = () => {
            clearLosLine();
            const desc = btn.dataset.desc;
            const rid = _activeShootResponseId;
            _activeShootTargets = [];
            _activeShootResponseId = null;
            clearInput();
            appendMessage(`> Shoot: ${btn.textContent}`, 'dim');
            sendResponse(rid, desc);
        };
    });
}

function drawLosLine(fromZone, toZone, lineClass) {
    const svg = document.getElementById('bf-los-overlay');
    if (!svg) return;
    const grid = svg.closest('.battlefield');
    if (!grid) return;

    // Find the center of each zone cell
    const fromCell = grid.querySelector(`[data-zone="${fromZone[0]},${fromZone[1]}"]`);
    const toCell = grid.querySelector(`[data-zone="${toZone[0]},${toZone[1]}"]`);
    if (!fromCell || !toCell) return;

    const gridRect = grid.getBoundingClientRect();
    const fromRect = fromCell.getBoundingClientRect();
    const toRect = toCell.getBoundingClientRect();

    const x1 = fromRect.left + fromRect.width / 2 - gridRect.left;
    const y1 = fromRect.top + fromRect.height / 2 - gridRect.top;
    const x2 = toRect.left + toRect.width / 2 - gridRect.left;
    const y2 = toRect.top + toRect.height / 2 - gridRect.top;

    svg.setAttribute('viewBox', `0 0 ${gridRect.width} ${gridRect.height}`);
    const cls = lineClass || 'los-line';
    svg.innerHTML = `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="${cls}"/>`;
}

function clearLosLine() {
    const svg = document.getElementById('bf-los-overlay');
    if (svg) svg.innerHTML = '';
}

function refreshZoneDetailPanel() {
    if (_selectedZone) {
        updateZoneDetailPanel(_selectedZone);
    }
}

// ── Legend ───────────────────────────────────────────────────

function buildLegend(data) {
    const seen = new Map();
    const fallen = [];
    for (const fig of data.figures) {
        if (fig.status === 'casualty') {
            fallen.push(fig);
            continue;
        }
        const cleanLabel = fig.label.replace(/[~_+]/g, '');
        if (!seen.has(cleanLabel)) {
            seen.set(cleanLabel, fig);
        }
    }

    let html = '';
    if (seen.size > 0) {
        html += '<div class="bf-legend-figs">';
        for (const [label, fig] of seen) {
            const color = figColor(fig.color);
            html += `<span class="bf-legend-item"><span style="color:${color}; font-weight:700;">${escapeHtml(label)}</span>=${escapeHtml(fig.name)}</span>`;
        }
        html += '</div>';
    }
    if (fallen.length > 0) {
        html += '<div class="bf-legend-figs">';
        for (const fig of fallen) {
            html += `<span class="bf-legend-item"><span style="color:#e55555; font-weight:700;">\u2020</span>=${escapeHtml(fig.name)} (fallen)</span>`;
        }
        html += '</div>';
    }

    // Terrain legend with visual indicators
    html += '<div class="bf-legend-terrain">';
    html += '<span class="bf-legend-item"><span class="terrain-light_cover-chip"></span>SC=Scatter Cover</span>';
    html += '<span class="bf-legend-item"><span class="terrain-heavy_cover-chip"></span>C=Cover</span>';
    html += '<span class="bf-legend-item"><span class="terrain-high_ground-chip"></span>HG=High Ground</span>';
    html += '<span class="bf-legend-item"><span class="terrain-impassable-chip"></span>XX=Impassable</span>';
    html += '</div>';

    // Objective legend — collect unique labels
    const objLabels = new Map();
    for (const row of data.zones) {
        for (const zone of row) {
            if (zone.has_objective) {
                const label = zone.objective_label || 'OBJ';
                const baseLabel = label.replace('✓', '').trim();
                if (!objLabels.has(baseLabel)) {
                    objLabels.set(baseLabel, { total: 0, complete: 0 });
                }
                objLabels.get(baseLabel).total++;
                if (label.includes('✓')) objLabels.get(baseLabel).complete++;
            }
        }
    }
    if (objLabels.size > 0) {
        html += '<div class="bf-legend-terrain">';
        for (const [label, counts] of objLabels) {
            const starColor = counts.complete === counts.total && counts.total > 0
                ? 'var(--accent-green)' : 'var(--accent-yellow)';
            html += `<span class="bf-legend-item"><span style="color:${starColor}; font-size:14px;">&#9733;</span>${escapeHtml(label)}=Objective (${counts.complete}/${counts.total})</span>`;
        }
        html += '</div>';
    }

    return html;
}

function figColor(colorClass) {
    const colors = {
        'player': '#4ade80',
        'player-fallen': '#e55555',
        'enemy': '#ef4444',
        'storm': '#eab308',
        'slyn': '#22d3ee',
        'sleeper': '#c084fc',
    };
    return colors[colorClass] || '#c9d1d9';
}

// ── Interactive Reaction Dice Assignment ─────────────────────

function renderReactionDiceUI(data, msg) {
    const area = document.getElementById('input-area');
    area.innerHTML = '';

    const dice = [...data.dice];
    const figures = data.figures;  // [{name, speed}, ...]
    const assignments = {};  // name -> die value
    let currentFigIdx = 0;

    function getAvailableDice() {
        const used = Object.values(assignments);
        const remaining = [...dice];
        for (const u of used) {
            const idx = remaining.indexOf(u);
            if (idx >= 0) remaining.splice(idx, 1);
        }
        return remaining;
    }

    function render() {
        area.innerHTML = '';

        const wrapper = document.createElement('div');
        wrapper.className = 'reaction-ui';

        // Header
        const header = document.createElement('div');
        header.className = 'reaction-header';
        header.innerHTML = '<h4>Assign Reaction Dice</h4>';
        wrapper.appendChild(header);

        // Dice pool
        const pool = document.createElement('div');
        pool.className = 'reaction-pool';
        const available = getAvailableDice();
        const poolLabel = document.createElement('div');
        poolLabel.className = 'reaction-pool-label';
        poolLabel.textContent = 'Available Dice:';
        pool.appendChild(poolLabel);

        const diceRow = document.createElement('div');
        diceRow.className = 'reaction-dice-row';
        for (const d of available) {
            const die = document.createElement('div');
            die.className = `reaction-die ${d <= figures[currentFigIdx]?.speed ? 'die-quick' : 'die-slow'}`;
            die.textContent = d;
            die.title = d <= (figures[currentFigIdx]?.speed || 0) ? 'Quick (die ≤ Reactions)' : 'Slow (die > Reactions)';
            // Click to assign to current figure
            die.addEventListener('click', () => {
                if (currentFigIdx < figures.length) {
                    assignments[figures[currentFigIdx].name] = d;
                    currentFigIdx++;
                    // Skip figures if no dice remain
                    while (currentFigIdx < figures.length && getAvailableDice().length === 0) {
                        currentFigIdx++;
                    }
                    render();
                }
            });
            diceRow.appendChild(die);
        }
        pool.appendChild(diceRow);
        wrapper.appendChild(pool);

        // Figure assignment list
        const figList = document.createElement('div');
        figList.className = 'reaction-figures';

        for (let i = 0; i < figures.length; i++) {
            const fig = figures[i];
            const assigned = assignments[fig.name];
            const isCurrent = i === currentFigIdx;

            const row = document.createElement('div');
            row.className = `reaction-fig-row ${isCurrent ? 'current' : ''} ${assigned !== undefined ? 'assigned' : ''}`;

            const info = document.createElement('div');
            info.className = 'reaction-fig-info';
            info.innerHTML = `<span class="reaction-fig-name">${escapeHtml(fig.name)}</span>
                <span class="reaction-fig-speed">Reactions ${fig.speed}</span>`;
            row.appendChild(info);

            if (assigned !== undefined) {
                const badge = document.createElement('div');
                badge.className = `reaction-die-badge ${assigned <= fig.speed ? 'die-quick' : 'die-slow'}`;
                badge.textContent = assigned;
                badge.title = 'Click to unassign';
                badge.addEventListener('click', () => {
                    delete assignments[fig.name];
                    // Reset currentFigIdx to this figure
                    currentFigIdx = i;
                    render();
                });
                row.appendChild(badge);
            } else if (isCurrent) {
                const hint = document.createElement('span');
                hint.className = 'reaction-hint';
                hint.textContent = '← click a die';
                row.appendChild(hint);
            }

            figList.appendChild(row);
        }
        wrapper.appendChild(figList);

        // Speed reference
        const ref = document.createElement('div');
        ref.className = 'reaction-ref';
        ref.innerHTML = 'Die ≤ Reactions = <span class="die-quick-text">Quick</span> &nbsp;|&nbsp; Die > Reactions = <span class="die-slow-text">Slow</span>';
        wrapper.appendChild(ref);

        // Buttons
        const btns = document.createElement('div');
        btns.className = 'reaction-buttons';

        const skipBtn = document.createElement('button');
        skipBtn.className = 'btn';
        skipBtn.textContent = 'Skip Remaining';
        skipBtn.onclick = () => {
            // Skip all unassigned figures
            currentFigIdx = figures.length;
            render();
        };
        btns.appendChild(skipBtn);

        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'btn btn-primary';
        confirmBtn.textContent = 'Confirm Assignments';
        confirmBtn.onclick = () => {
            clearInput();
            sendResponse(msg.id, assignments);
        };
        btns.appendChild(confirmBtn);

        wrapper.appendChild(btns);
        area.appendChild(wrapper);
    }

    render();
}

// ── Mission Briefing Panel ───────────────────────────────────

/** Build mission info HTML for the right panel (reusable). */
function _buildMissionInfoHtml(data) {
    let html = '';

    // Mission type header
    html += `<div class="mission-info-header">
        <h3>&#9876; ${escapeHtml(data.mission_type)}</h3>
    </div>`;

    // Enemy type badge
    if (data.enemy_type) {
        const etLabel = data.enemy_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const etClass = data.enemy_type === 'tactical' ? 'enemy-tactical' : data.enemy_type === 'slyn' ? 'enemy-slyn' : 'enemy-lifeform';
        html += `<div class="mission-enemy-badge ${etClass}">${escapeHtml(etLabel)}</div>`;
    }

    // Enemy stats
    if (data.enemy_info && data.enemy_info.length > 0) {
        html += '<div class="mission-section">';
        html += '<div class="mission-section-title">Enemy Intel</div>';
        html += '<div class="mission-enemy-stats">';
        for (const line of data.enemy_info) {
            html += `<div class="mission-enemy-line">${escapeHtml(line)}</div>`;
        }
        html += '</div></div>';
    }

    // Objectives / victory conditions + progress tracking
    if (data.victory_conditions && data.victory_conditions.length > 0) {
        html += '<div class="mission-section">';
        html += '<div class="mission-section-title">Objectives</div>';
        html += '<ul class="mission-objectives">';
        for (const vc of data.victory_conditions) {
            html += `<li>&#9733; ${escapeHtml(vc)}</li>`;
        }
        html += '</ul>';

        // Objective progress from battlefield zones
        const bf = data.battlefield;
        if (bf && bf.zones) {
            const objCounts = new Map();
            for (const row of bf.zones) {
                for (const zone of row) {
                    if (zone.has_objective) {
                        const label = zone.objective_label || 'OBJ';
                        const baseLabel = label.replace('✓', '').trim();
                        if (!objCounts.has(baseLabel)) {
                            objCounts.set(baseLabel, { total: 0, complete: 0 });
                        }
                        objCounts.get(baseLabel).total++;
                        if (label.includes('✓')) objCounts.get(baseLabel).complete++;
                    }
                }
            }
            if (objCounts.size > 0) {
                html += '<div class="mission-obj-progress">';
                for (const [label, counts] of objCounts) {
                    const pct = counts.total > 0 ? Math.round(100 * counts.complete / counts.total) : 0;
                    const done = counts.complete === counts.total && counts.total > 0;
                    const statusClass = done ? 'obj-done' : '';
                    html += `<div class="obj-progress-row ${statusClass}">`;
                    html += `<span class="obj-progress-label">${escapeHtml(label)}</span>`;
                    html += `<span class="obj-progress-bar"><span class="obj-progress-fill" style="width:${pct}%"></span></span>`;
                    html += `<span class="obj-progress-count">${counts.complete}/${counts.total}</span>`;
                    html += '</div>';
                }
                html += '</div>';
            }
        }
        html += '</div>';
    }

    // Defeat conditions
    if (data.defeat_conditions && data.defeat_conditions.length > 0) {
        html += '<div class="mission-section">';
        html += '<div class="mission-section-title">Defeat Conditions</div>';
        html += '<ul class="mission-defeat">';
        for (const dc of data.defeat_conditions) {
            html += `<li>${escapeHtml(dc)}</li>`;
        }
        html += '</ul></div>';
    }

    // Special rules
    if (data.special_rules && data.special_rules.length > 0) {
        html += '<div class="mission-section">';
        html += '<div class="mission-section-title">Special Rules</div>';
        html += '<ul class="mission-rules">';
        for (const rule of data.special_rules) {
            html += `<li>${escapeHtml(rule)}</li>`;
        }
        html += '</ul></div>';
    }

    return html;
}

function renderMissionBriefing(data) {
    _missionBriefingData = data;  // cache for persistent display
    const display = document.getElementById('display-area');
    display.innerHTML = '';

    const bf = data.battlefield;

    // Store battlefield data for zone click details
    _bfData = bf;
    _bfFigureMap = {};
    for (const fig of bf.figures) {
        const key = `${fig.zone[0]},${fig.zone[1]}`;
        if (!_bfFigureMap[key]) _bfFigureMap[key] = [];
        _bfFigureMap[key].push(fig);
    }

    let html = '<div class="mission-panel">';

    // Left: battlefield map
    html += '<div class="mission-map-section">';
    html += `<div class="battlefield" style="grid-template-columns: repeat(${bf.cols}, 1fr);">`;

    for (let r = 0; r < bf.rows; r++) {
        for (let c = 0; c < bf.cols; c++) {
            const zone = bf.zones[r][c];
            const key = `${r},${c}`;
            const figs = _bfFigureMap[key] || [];

            let cellClass = `bf-cell terrain-${zone.terrain}`;

            const tIcon = TERRAIN_ICONS[zone.terrain] || '';
            const terrainHtml = tIcon ? `<span class="bf-terrain-icon">${tIcon}</span>` : '';
            const tLabel = TERRAIN_LABELS[zone.terrain] || '';
            const labelHtml = tLabel ? `<span class="terrain-label">${tLabel}</span>` : '';
            const objHtml = zone.has_objective
                ? `<span class="bf-objective" title="${escapeHtml(zone.objective_label) || 'Objective'}">&#9733;</span>`
                : '';

            let figsHtml = '';
            if (figs.length > 0) {
                figsHtml = '<div class="figures">';
                for (const fig of figs) {
                    let figClass = `bf-fig ${fig.color}`;
                    if (fig.is_contact) figClass += ' contact';
                    const figContent = fig.is_contact ? '&#9432;' : escapeHtml(fig.label);
                    figsHtml += `<span class="${figClass}" title="${escapeHtml(fig.name)}">${figContent}</span>`;
                }
                figsHtml += '</div>';
            }

            const coordHtml = `<span class="bf-coord">${r},${c}</span>`;
            html += `<div class="${cellClass}" data-zone="${r},${c}">${terrainHtml}${labelHtml}${objHtml}${figsHtml}${coordHtml}</div>`;
        }
    }

    html += '</div>'; // close battlefield grid
    html += '</div>'; // close mission-map-section

    // Right: mission info panel
    html += '<button class="info-panel-toggle" id="briefing-info-toggle" onclick="toggleInfoPanel(\'briefing-info-toggle\',\'briefing-info-panel\')"><span class="toggle-arrow">&#9660;</span> Mission Info</button>';
    html += '<div class="mission-info-panel" id="briefing-info-panel">';
    html += _buildMissionInfoHtml(data);
    html += '</div>'; // close mission-info-panel
    html += '</div>'; // close mission-panel

    // Legend (full width below map + info panel)
    html += '<div class="bf-legend-box">';
    html += buildLegend(bf);
    html += '</div>';

    display.innerHTML = html;

    // Wire zone click handlers for detail display
    display.querySelectorAll('.bf-cell[data-zone]').forEach(cell => {
        cell.addEventListener('click', (e) => {
            e.stopPropagation();
            // Highlight clicked zone
            display.querySelectorAll('.bf-cell-selected').forEach(el => el.classList.remove('bf-cell-selected'));
            cell.classList.add('bf-cell-selected');
        });
    });
}
