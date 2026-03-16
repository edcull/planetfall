/**
 * Planetfall Web UI — WebSocket connection and message router.
 */

let ws = null;
let connected = false;

// ── Connection ──────────────────────────────────────────────

function connectWebSocket(initMsg) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/game`);

    window._ws = ws;

    ws.onopen = () => {
        connected = true;
        ws.send(JSON.stringify(initMsg));
        // Sync narrative preference from localStorage to server
        const stored = localStorage.getItem('narrative_disabled');
        if (stored !== null) {
            ws.send(JSON.stringify({
                type: 'update_setting',
                key: 'narrative_disabled',
                value: JSON.parse(stored),
            }));
        }
        showScreen('game');
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        routeMessage(msg);
    };

    ws.onclose = () => {
        connected = false;
        appendMessage('Connection lost.', 'error');
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

function sendResponse(id, value) {
    if (ws && connected) {
        ws.send(JSON.stringify({ type: 'input_response', id, value }));
    }
}

// ── Message Router ──────────────────────────────────────────

function routeMessage(msg) {
    switch (msg.type) {
        case 'message':
            if (msg.style === 'narrative') {
                showNarrativeModal(msg.text);
            } else if (msg.text && msg.text.includes('Generating narrative')) {
                showNarrativeLoading();
            } else {
                appendMessage(msg.text, msg.style);
            }
            break;
        case 'rule':
            renderRule(msg.text, msg.style);
            break;
        case 'clear':
            clearDisplay();
            break;
        case 'input_request':
            renderInput(msg);
            break;
        case 'show_events':
            renderEvents(msg.events);
            break;
        case 'show_colony_status':
            renderColonyStatus(msg.data);
            _syncSettingsUI(msg.data.settings);
            break;
        case 'show_map':
            _cachedMapData = msg.data;
            renderMap(msg.data);
            break;
        case 'show_roster':
            renderRoster(msg.data);
            break;
        case 'show_step_header':
            if (msg.map) _cachedMapData = msg.map;
            renderStepHeader(msg.step, msg.name, msg.colony);
            if (msg.colony) renderColonyStatus(msg.colony);
            // Show map on step 8 (combat mode choice) — cleared later by show_battlefield
            if (msg.map && msg.step === 8) renderMap(msg.map);
            // Auto-open roster modal on step 1 (Recovery) only when there are recovery messages
            if (msg.roster && msg.step === 1) {
                renderRoster(msg.roster);
                if (msg.recovery_messages && msg.recovery_messages.length > 0) {
                    openRosterModal({ recoveryMessages: msg.recovery_messages });
                }
            }
            // Update enemies sidebar data on step 4 (no modal — results shown as messages)
            if (msg.enemies && msg.step === 4) {
                renderEnemies(msg.enemies);
            }
            // Update roster sidebar data on step 13 (no modal — results shown as messages)
            if (msg.roster && msg.step === 13) {
                renderRoster(msg.roster);
            }
            break;
        case 'show_loading_modal':
            showLoadingModal(msg.title || 'Colony Log');
            break;
        case 'show_mission_options':
            renderMissionOptions(msg.options);
            break;
        case 'show_character_backgrounds':
            renderCharacterBackgrounds(msg.data);
            break;
        case 'show_turn_summary':
            renderTurnSummary(msg.events);
            break;
        case 'show_mission_briefing':
            _cachedMapData = null;  // combat replaces map
            renderMissionBriefing(msg.data);
            break;
        case 'show_battlefield':
            _cachedMapData = null;  // combat replaces map
            // Restore mission briefing data if sent with battlefield
            if (msg.mission_info && typeof setMissionBriefingData === 'function') {
                setMissionBriefingData(msg.mission_info);
            }
            renderBattlefield(msg.data);
            break;
        case 'show_combat_phase':
            renderCombatPhase(msg.phase, msg.round_number);
            break;
        case 'show_combat_log':
            renderCombatLog(msg.lines);
            break;
        case 'show_mission_summary':
            renderMissionSummary(msg.missions);
            break;
        case 'show_reaction_roll':
            renderReactionRoll(msg.data);
            break;
        case 'show_log':
            renderLogContent(msg);
            break;
        case 'colony_log':
            if (document.getElementById('log-modal')) {
                _updateLogModalContent(msg.markdown, msg.current_turn, msg.available_turns);
            } else {
                openColonyLogModal(msg.markdown, msg.current_turn, msg.available_turns);
            }
            break;
        case 'show_armory':
            renderArmory(msg.data);
            break;
        case 'show_ancient_signs':
            renderAncientSigns(msg.data);
            break;
        case 'show_milestones':
            renderMilestones(msg.data);
            break;
        case 'show_conditions':
            renderConditions(msg.data);
            break;
        case 'show_lifeforms':
            renderLifeforms(msg.data);
            break;
        case 'show_enemies':
            renderEnemies(msg.data);
            break;
        case 'show_augmentations':
            renderAugmentations(msg.data);
            break;
        case 'show_artifacts':
            renderArtifacts(msg.data);
            break;
        case 'show_calamities':
            renderCalamities(msg.data);
            break;
        case 'show_morale':
            renderMorale(msg.data);
            break;
        case 'mission_intro':
            showMissionIntroModal(msg);
            break;
        case 'game_over':
            appendMessage('Game session ended.', 'info');
            break;
        case 'error':
            appendMessage(`Error: ${msg.message}`, 'error');
            break;
        case 'debug_step_set':
            appendMessage(`Debug: ${msg.message}`, 'info');
            break;
        case 'resource_cache_rolled':
            _handleResourceCacheRolled(msg);
            break;
        case 'resource_cache_result':
            _handleResourceCacheResult(msg);
            break;
        default:
            console.warn('Unknown message type:', msg.type);
    }
}

// ── Screen Management ───────────────────────────────────────

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if (id === 'game') {
        renderStepsSidebar(_currentStep);
    }
}

// ── Narrative Modal ─────────────────────────────────────────

function showNarrativeLoading() {
    const existing = document.getElementById('narrative-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'narrative-modal';
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content narrative-modal';
    modal.innerHTML = `
        <div class="modal-header">
            <h2>Colony Log</h2>
        </div>
        <div class="modal-body narrative-loading">
            <div class="spinner"></div>
            <p>Generating narrative...</p>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

function showNarrativeModal(text) {
    const existing = document.getElementById('narrative-modal');
    if (existing) {
        // Update loading modal with content
        const body = existing.querySelector('.modal-body');
        const header = existing.querySelector('.modal-header');
        if (header && !header.querySelector('.modal-close')) {
            header.innerHTML += '<button class="modal-close" onclick="document.getElementById(\'narrative-modal\').remove()">&#10005;</button>';
        }
        if (body) {
            body.className = 'modal-body';
            body.innerHTML = `<div class="colony-log-content">${simpleMarkdown(text.trim())}</div>`;
        }
        existing.onclick = (e) => { if (e.target === existing) existing.remove(); };
    } else {
        // No loading modal — create fresh
        const overlay = document.createElement('div');
        overlay.id = 'narrative-modal';
        overlay.className = 'modal-overlay';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

        const modal = document.createElement('div');
        modal.className = 'modal-content narrative-modal';
        modal.innerHTML = `
            <div class="modal-header">
                <h2>Colony Log</h2>
                <button class="modal-close" onclick="document.getElementById('narrative-modal').remove()">&#10005;</button>
            </div>
            <div class="modal-body">
                <div class="colony-log-content">${simpleMarkdown(text.trim())}</div>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    // ESC to close
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            const m = document.getElementById('narrative-modal');
            if (m) m.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Mission Intro Modal ────────────────────────────────────

function showMissionIntroModal(msg) {
    const existing = document.getElementById('mission-intro-modal');
    if (existing) existing.remove();

    const d = msg.data;
    const overlay = document.createElement('div');
    overlay.id = 'mission-intro-modal';
    overlay.className = 'modal-overlay';

    let sectionsHtml = '';
    for (const section of (d.sections || [])) {
        if (section.heading) {
            sectionsHtml += `<h3 class="mi-heading">${escapeHtml(section.heading)}</h3>`;
        }
        if (section.body) {
            const lines = section.body.split('\n');
            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('◆ ')) {
                    sectionsHtml += `<p class="mi-bullet">${escapeHtml(trimmed.substring(2))}</p>`;
                } else if (trimmed) {
                    sectionsHtml += `<p class="mi-text">${escapeHtml(trimmed)}</p>`;
                }
            }
        }
    }

    const modal = document.createElement('div');
    modal.className = 'modal-content mission-intro-modal';
    modal.innerHTML = `
        <div class="modal-header">
            <div>
                <h2>${escapeHtml(d.title || 'Mission')}</h2>
                ${d.subtitle ? `<div class="mi-subtitle">${escapeHtml(d.subtitle)}</div>` : ''}
            </div>
        </div>
        <div class="modal-body">
            ${sectionsHtml}
        </div>
        <div class="modal-footer">
            <button class="btn btn-primary mi-begin-btn">Begin Mission</button>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const beginBtn = modal.querySelector('.mi-begin-btn');
    beginBtn.focus();
    beginBtn.onclick = () => {
        overlay.remove();
        sendResponse(msg.id, true);
    };

    // ESC to begin
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            sendResponse(msg.id, true);
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Display Helpers ─────────────────────────────────────────

function appendMessage(text, style) {
    const display = document.getElementById('display-area');
    const div = document.createElement('div');
    div.className = `msg ${style || ''}`.trim();
    div.textContent = text;
    display.appendChild(div);
    display.scrollTop = display.scrollHeight;
}

function renderRule(text, style) {
    const display = document.getElementById('display-area');
    const div = document.createElement('div');
    div.className = 'rule-divider';
    div.textContent = text;
    display.appendChild(div);
    display.scrollTop = display.scrollHeight;
}

function clearDisplay() {
    const display = document.getElementById('display-area');
    // Re-render cached map only for non-combat steps
    if (_cachedMapData && _currentStep < 7) {
        display.innerHTML = '';
        renderMap(_cachedMapData);
    } else {
        display.innerHTML = '';
    }
}

const CAMPAIGN_STEPS = {
    1: "Recovery", 2: "Repairs", 3: "Scout Reports",
    4: "Enemy Activity", 5: "Colony Events",
    6: "Mission Determination", 7: "Lock and Load",
    8: "Battle Results", 9: "Injuries",
    10: "Experience", 11: "Morale",
    12: "Tracking", 13: "Replacements",
    14: "Research", 15: "Building",
    16: "Colony Integrity", 17: "Character Event",
    18: "Update Sheet",
};

let _currentStep = 0;
let _betweenTurnsMsg = null;
let _cachedMapData = null;  // persist map across clears

function renderStepHeader(step, name, colony) {
    _currentStep = step;
    _betweenTurnsMsg = null;  // clear between-turns state when a step starts
    const header = document.getElementById('step-header');
    const dayLabel = colony ? `<span class="day-label">Day ${colony.turn}</span>` : '';
    header.innerHTML = `${dayLabel}<span class="step-label">Step ${step}: ${name}</span>`;
    renderStepsSidebar(step);

    // Clear display for battle step only (no campaign map during combat)
    if (step === 8) {
        _cachedMapData = null;
        document.getElementById('display-area').innerHTML = '';
    } else {
        const display = document.getElementById('display-area');
        display.innerHTML = '';
        if (_cachedMapData) {
            renderMap(_cachedMapData);
        }
    }
    // Messages now render in display-area, cleared by renderStepHeader above
}

function setBetweenTurnsState(msg) {
    _betweenTurnsMsg = msg;
    renderStepsSidebar(_currentStep);
}

function clearBetweenTurnsState() {
    _betweenTurnsMsg = null;
    renderStepsSidebar(_currentStep);
}

function renderStepsSidebar(activeStep) {
    const sidebar = document.getElementById('steps-sidebar');
    if (!sidebar) return;

    let html = '<div class="steps-title">Campaign Turn</div>';
    for (let i = 1; i <= 18; i++) {
        let cls = 'step-pending';
        if (i < activeStep) cls = 'step-done';
        else if (i === activeStep) cls = 'step-active';

        html += `<div class="step-item ${cls}">
            <span class="step-num">${i}</span>
            <span>${CAMPAIGN_STEPS[i]}</span>
        </div>`;
    }

    sidebar.innerHTML = html;

    // When between turns, mark step 18 (Update Sheet) as done
    if (_betweenTurnsMsg) {
        const items = sidebar.querySelectorAll('.step-item');
        if (items.length >= 18) {
            items[17].className = 'step-item step-done';
        }
    }
}

// ── Landing Page ────────────────────────────────────────────

async function loadCampaigns() {
    try {
        const resp = await fetch('/api/campaigns');
        const data = await resp.json();
        const list = document.getElementById('campaign-list');

        if (data.campaigns.length === 0) {
            list.innerHTML = '<p style="color: var(--text-dim)">No saved campaigns found.</p>';
            return;
        }

        const STEP_NAMES = {
            0:'New',1:'Recovery',2:'Repairs',3:'Scout Reports',4:'Enemy Activity',
            5:'Colony Events',6:'Mission',7:'Lock & Load',8:'Battle',
            9:'Results',10:'Experience',11:'Morale',12:'Tracking',
            13:'Replacements',14:'Research',15:'Building',16:'Integrity',
            17:'Character Event',18:'Done',
        };
        list.innerHTML = data.campaigns.map(c => {
            const stepName = STEP_NAMES[c.step] || `Step ${c.step}`;
            return `
            <div class="campaign-item">
                <div style="flex:1; cursor:pointer;" onclick="continueCampaign('${c.name}')">
                    <div class="name">${c.name}</div>
                    <div class="info">
                        Turn ${c.turn || '?'} &middot;
                        ${stepName} &middot;
                        ${c.total_size_kb || '?'} KB
                    </div>
                </div>
                <button class="btn-delete-campaign" title="Delete" onclick="event.stopPropagation(); deleteCampaign('${c.name}')">&#10005;</button>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('Failed to load campaigns:', e);
    }
}

function startNewCampaign() {
    connectWebSocket({ action: 'new' });
}

function continueCampaign(name) {
    connectWebSocket({ action: 'continue', campaign_name: name });
}

async function deleteCampaign(name) {
    if (!confirm(`Delete campaign "${name}"? This cannot be undone.`)) return;
    try {
        const resp = await fetch(`/api/campaigns/${encodeURIComponent(name)}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.deleted) {
            loadCampaigns();
        }
    } catch (e) {
        console.error('Failed to delete campaign:', e);
    }
}

// ── Mobile Sidebar Toggle ────────────────────────────────────

function toggleMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('mobile-open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    if (sidebar && sidebar.classList.contains('mobile-open') &&
        !sidebar.contains(e.target) && !toggle.contains(e.target)) {
        sidebar.classList.remove('mobile-open');
    }
});

// ── Settings Menu ──────────────────────────────────────────

function toggleSettingsMenu() {
    const dropdown = document.getElementById('settings-dropdown');
    dropdown.classList.toggle('open');
}

// Close settings dropdown when clicking outside
document.addEventListener('click', (e) => {
    const menu = document.getElementById('settings-menu');
    if (menu && !menu.contains(e.target)) {
        const dropdown = document.getElementById('settings-dropdown');
        if (dropdown) dropdown.classList.remove('open');
    }
});

function toggleNarrative(disabled) {
    localStorage.setItem('narrative_disabled', JSON.stringify(disabled));
    if (ws && connected) {
        ws.send(JSON.stringify({
            type: 'update_setting',
            key: 'narrative_disabled',
            value: disabled,
        }));
    }
}

function _syncSettingsUI(settings) {
    if (!settings) return;
    const cb = document.getElementById('setting-narrative-disabled');
    if (cb) cb.checked = !!settings.narrative_disabled;
}

// Restore narrative setting from localStorage on page load
(function _restoreNarrativeSetting() {
    const stored = localStorage.getItem('narrative_disabled');
    if (stored !== null) {
        const disabled = JSON.parse(stored);
        const cb = document.getElementById('setting-narrative-disabled');
        if (cb) cb.checked = disabled;
    }
})();

// ── Collapsible Sidebars (Desktop) ──────────────────────────

function toggleLeftSidebar() {
    const sidebar = document.getElementById('sidebar');
    const expandBtn = document.getElementById('sidebar-expand-left');
    const collapseBtn = document.getElementById('sidebar-collapse-left');
    const isCollapsed = sidebar.classList.toggle('collapsed');
    expandBtn.classList.toggle('visible', isCollapsed);
    collapseBtn.style.display = isCollapsed ? 'none' : '';
}

function toggleRightSidebar() {
    const sidebar = document.getElementById('steps-sidebar');
    const expandBtn = document.getElementById('sidebar-expand-right');
    const collapseBtn = document.getElementById('sidebar-collapse-right');
    const isCollapsed = sidebar.classList.toggle('collapsed');
    expandBtn.classList.toggle('visible', isCollapsed);
    collapseBtn.style.display = isCollapsed ? 'none' : '';
}

function toggleInfoPanel(toggleId, bodyId) {
    const toggle = document.getElementById(toggleId);
    const body = document.getElementById(bodyId);
    if (!toggle || !body) return;
    const collapsed = body.classList.toggle('panel-collapsed');
    toggle.classList.toggle('collapsed', collapsed);
    const arrow = toggle.querySelector('.toggle-arrow');
    if (arrow) arrow.textContent = collapsed ? '\u25B6' : '\u25BC';
}

// ── Init ────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', loadCampaigns);
