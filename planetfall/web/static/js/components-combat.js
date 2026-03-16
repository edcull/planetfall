/**
 * Planetfall Web UI — Combat display components.
 *
 * Provides: renderMissionOptions, renderCombatPhase, renderMissionSummary,
 * renderCombatLog, renderReactionRoll, and combat-specific constants.
 *
 * Depends on: components.js (escapeHtml)
 *             app.js (_currentStep, renderStepsSidebar)
 */

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
