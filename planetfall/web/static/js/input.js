/**
 * Planetfall Web UI — Input form generators.
 *
 * Each input type creates a UI in #input-area, sends back the response,
 * then clears itself.
 *
 * This file contains the router (renderInput), basic input renderers
 * (select, confirm, number, checkbox, text, pause), shared utilities,
 * and campaign-phase screens (mission result, experience, research,
 * building, narrative modal, sector select).
 *
 * Combat inputs are in input-combat.js.
 * Setup inputs are in input-setup.js.
 */

// ── Shared: Figure profile card ─────────────────────────────
function buildFigureProfileHtml(f) {
    let html = `<div class="afp-header">
        <span class="afp-name">${escapeHtml(f.name)}</span>`;
    if (f.label) html += `<span class="afp-label">${escapeHtml(f.label)}</span>`;
    html += `<span class="afp-class">${escapeHtml(f.char_class || '')}</span>
    </div>`;
    html += '<div class="afp-stats">';
    html += `<span class="stat-chip"><span class="label">Spd</span><span class="val">${f.speed}"</span></span>`;
    html += `<span class="stat-chip"><span class="label">React</span><span class="val">${f.reactions}</span></span>`;
    html += `<span class="stat-chip"><span class="label">CS</span><span class="val">+${f.combat_skill}</span></span>`;
    html += `<span class="stat-chip"><span class="label">T</span><span class="val">${f.toughness}</span></span>`;
    html += `<span class="stat-chip"><span class="label">Sav</span><span class="val">+${f.savvy}</span></span>`;
    if (f.armor_save) {
        html += `<span class="stat-chip"><span class="label">Arm</span><span class="val">${f.armor_save}+</span></span>`;
    }
    html += '</div>';
    if (f.weapon_name) {
        let wParts = [f.weapon_name];
        wParts.push(`Range ${f.weapon_range}"`);
        wParts.push(`Shots ${f.weapon_shots}`);
        if (f.weapon_damage) wParts.push(`Dmg +${f.weapon_damage}`);
        if (f.weapon_traits && f.weapon_traits.length) wParts.push(f.weapon_traits.join(', '));
        html += `<div class="afp-weapon">${escapeHtml(wParts.join(' | '))}</div>`;
    }
    if (f.statuses && f.statuses.length) {
        html += `<div class="afp-statuses">${f.statuses.map(s => escapeHtml(s)).join(' | ')}</div>`;
    }
    return html;
}

function appendFigureProfile(area, f) {
    const profile = document.createElement('div');
    profile.className = 'action-figure-profile';
    profile.innerHTML = buildFigureProfileHtml(f);
    area.appendChild(profile);
}

function renderInput(msg) {
    const area = document.getElementById('input-area');

    switch (msg.input_type) {
        case 'select':
            renderSelect(area, msg);
            break;
        case 'confirm':
            renderConfirm(area, msg);
            break;
        case 'number':
            renderNumber(area, msg);
            break;
        case 'checkbox':
            renderCheckbox(area, msg);
            break;
        case 'text':
            renderText(area, msg);
            break;
        case 'pause':
            renderPause(area, msg);
            break;
        case 'mission_result':
            renderMissionResult(area, msg);
            break;
        case 'experience':
            renderExperienceScreen(area, msg);
            break;
        case 'research_spend':
            renderResearchSpending(area, msg);
            break;
        case 'building_spend':
            renderBuildingSpending(area, msg);
            break;
        case 'narrative_modal':
            renderNarrativeModal(area, msg);
            break;
        case 'info_modal':
            renderInfoModal(msg);
            break;
        case 'roster_editor':
            renderRosterEditor(msg);
            break;
        case 'colony_setup':
            renderColonySetup(msg);
            break;
        case 'colony_ready':
            renderColonyReady(msg);
            break;
        case 'mission_select':
            renderMissionSelect(area, msg);
            break;
        case 'sector_select':
            renderSectorSelect(area, msg);
            break;
        case 'weapon_select':
            renderWeaponSelect(area, msg);
            break;
        case 'figure_select':
            renderFigureSelect(area, msg);
            break;
        case 'deployment':
            renderDeployment(area, msg);
            break;
        case 'lock_and_load':
            renderLockAndLoad(area, msg);
            break;
        case 'deploy_zone':
            renderDeployZone(area, msg);
            break;
        case 'deploy_zones_batch':
            renderDeployZonesBatch(area, msg);
            break;
        case 'zone_select':
            renderZoneSelect(area, msg);
            break;
        case 'movement':
            renderMovement(area, msg);
            break;
        case 'action_select':
            renderActionSelect(area, msg);
            break;
        case 'reaction_assign':
            renderReactionDiceUI(msg.data, msg);
            break;
        case 'reroll_offer':
            renderRerollOffer(area, msg);
            break;
        case 'resource_cache':
            renderResourceCache(area, msg);
            break;
        case 'reroll_choice':
            renderRerollChoice(area, msg);
            break;
        default:
            console.warn('Unknown input type:', msg.input_type);
    }

    // Scroll input into view
    area.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function clearInput() {
    document.getElementById('input-area').innerHTML = '';
    _activeShootTargets = [];
    _activeShootResponseId = null;
}

// ── Select ──────────────────────────────────────────────────

function renderSelect(area, msg) {
    area.innerHTML = '';

    // Between-turns menu: render as bottom bar with Commence Turn button
    if (msg.message === 'Between turns:') {
        _renderBetweenTurnsBar(area, msg);
        return;
    }

    // Combat mode selection: render as cards
    if (msg.message === 'Combat mode?') {
        _renderCombatModeCards(area, msg);
        return;
    }

    if (msg.active_figure) appendFigureProfile(area, msg.active_figure);

    if (msg.message) {
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        prompt.textContent = msg.message;
        area.appendChild(prompt);
    }

    // Check if choices reference character names — render as roster cards if so
    const rosterChars = _lastRosterData ? _lastRosterData.characters : [];
    const charMap = {};
    for (const c of rosterChars) { charMap[c.name] = c; }

    // Match choices to characters: exact name match or choice containing a character name
    const charChoices = [];  // { choice, char, subtitle }
    const otherChoices = [];
    for (const choice of msg.choices) {
        if (charMap[choice]) {
            charChoices.push({ choice, char: charMap[choice], subtitle: '' });
        } else {
            // Check if choice contains a character name
            const matched = rosterChars.find(c => choice.includes(c.name));
            if (matched) {
                const subtitle = choice.replace(matched.name, '').replace(/^\s*[-—]\s*/, '').trim();
                charChoices.push({ choice, char: matched, subtitle });
            } else {
                otherChoices.push(choice);
            }
        }
    }

    const hasCharCards = charChoices.length > 0 && rosterChars.length > 0;

    if (hasCharCards) {
        const list = document.createElement('div');
        list.className = 'crew-select-grid';

        for (const { choice, char: c, subtitle } of charChoices) {
            const card = document.createElement('div');
            card.className = 'crew-select-card';
            const extraHtml = subtitle ? `<div class="crew-select-subtitle">${escapeHtml(subtitle)}</div>` : '';
            card.innerHTML = buildRosterCardHtml(c, { showEdit: false, compact: true, extraHtml });
            card.onclick = () => {
                clearInput();
                appendMessage(`> ${choice}`, 'dim');
                sendResponse(msg.id, choice);
            };
            list.appendChild(card);
        }

        area.appendChild(list);

        // Non-character choices (e.g. "Decline — lose 2 Morale") as regular buttons below
        if (otherChoices.length > 0) {
            const otherList = document.createElement('div');
            otherList.className = 'choice-list';
            for (const choice of otherChoices) {
                const btn = document.createElement('button');
                btn.className = 'choice-item';
                btn.textContent = choice;
                btn.onclick = () => {
                    clearInput();
                    appendMessage(`> ${choice}`, 'dim');
                    sendResponse(msg.id, choice);
                };
                otherList.appendChild(btn);
            }
            area.appendChild(otherList);
        }

        const first = list.querySelector('.crew-select-card');
        if (first) first.focus();
    } else {
        const list = document.createElement('div');
        list.className = 'choice-list';

        let cardCount = 0;
        for (const choice of msg.choices) {
            const btn = document.createElement('button');
            // Parse "Title — description" pattern into a card layout
            const dashMatch = choice.match(/^(.+?)\s*[—–]\s*(.+)$/);
            if (dashMatch) {
                btn.className = 'choice-card';
                btn.innerHTML = `<div class="choice-card-title">${escapeHtml(dashMatch[1].trim())}</div><div class="choice-card-desc">${escapeHtml(dashMatch[2].trim())}</div>`;
                cardCount++;
            } else {
                btn.className = 'choice-item';
                btn.textContent = choice;
            }
            btn.onclick = () => {
                clearInput();
                appendMessage(`> ${choice}`, 'dim');
                sendResponse(msg.id, choice);
            };
            list.appendChild(btn);
        }

        // If all choices are cards (4+), use grid layout
        if (cardCount === msg.choices.length && cardCount >= 4) {
            list.classList.add('choice-grid');
        }

        area.appendChild(list);

        // Focus first choice for keyboard nav
        const first = list.querySelector('.choice-card, .choice-item');
        if (first) first.focus();
    }
}

function _renderBetweenTurnsBar(area, msg) {
    // Store state so the steps sidebar can also show a Commence Turn button
    setBetweenTurnsState(msg);

    const bar = document.createElement('div');
    bar.className = 'commence-turn-bar';

    // Start Day button — current_turn already incremented by step 18
    const nextTurn = (_lastColonyData && _lastColonyData.turn) ? _lastColonyData.turn : '?';
    const commenceBtn = document.createElement('button');
    commenceBtn.className = 'btn-commence';
    commenceBtn.innerHTML = `&#9654; Start Day ${nextTurn}`;
    commenceBtn.onclick = () => {
        clearBetweenTurnsState();
        clearInput();
        sendResponse(msg.id, 'Continue to next turn');
    };
    bar.appendChild(commenceBtn);

    // Save and quit button
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn-secondary-action';
    saveBtn.textContent = 'Save & Quit';
    saveBtn.onclick = () => {
        clearBetweenTurnsState();
        clearInput();
        sendResponse(msg.id, 'Save and quit');
    };
    bar.appendChild(saveBtn);

    area.appendChild(bar);
}

function _renderCombatModeCards(area, msg) {
    const COMBAT_MODE_INFO = {
        'Interactive (AI combat)': {
            icon: '&#9876;',
            desc: 'The AI handles enemy actions and resolves combat automatically. You make tactical decisions for your crew.',
        },
        'Manual (tabletop)': {
            icon: '&#9998;',
            desc: 'Play out combat on your physical tabletop. Enter the results manually when done.',
        },
    };

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.textContent = 'Battle Resolution:';
    area.appendChild(prompt);

    const grid = document.createElement('div');
    grid.className = 'mission-select-grid';

    for (const choice of msg.choices) {
        const info = COMBAT_MODE_INFO[choice] || { icon: '&#9656;', desc: '' };
        const card = document.createElement('div');
        card.className = 'mission-select-card';
        card.tabIndex = 0;
        card.innerHTML = `
            <div class="mission-card-name">${info.icon} ${escapeHtml(choice)}</div>
            <div class="mission-card-desc">${info.desc}</div>
        `;
        card.onclick = () => {
            clearInput();
            appendMessage(`> ${choice}`, 'dim');
            sendResponse(msg.id, choice);
        };
        card.onkeydown = (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
        };
        grid.appendChild(card);
    }

    area.appendChild(grid);
    const first = grid.querySelector('.mission-select-card');
    if (first) first.focus();
}

// ── Confirm ─────────────────────────────────────────────────

function renderConfirm(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.textContent = msg.message;
    area.appendChild(prompt);

    const btnGroup = document.createElement('div');
    btnGroup.style.display = 'flex';
    btnGroup.style.gap = '8px';

    const yesBtn = document.createElement('button');
    yesBtn.className = 'btn btn-success';
    yesBtn.textContent = 'Yes';
    yesBtn.onclick = () => {
        clearInput();
        sendResponse(msg.id, true);
    };

    const noBtn = document.createElement('button');
    noBtn.className = 'btn btn-danger';
    noBtn.textContent = 'No';
    noBtn.onclick = () => {
        clearInput();
        sendResponse(msg.id, false);
    };

    btnGroup.appendChild(yesBtn);
    btnGroup.appendChild(noBtn);
    area.appendChild(btnGroup);

    // Focus default
    if (msg.default) yesBtn.focus(); else noBtn.focus();
}

// ── Number ──────────────────────────────────────────────────

function renderNumber(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.textContent = `${msg.message} (${msg.min}–${msg.max})`;
    area.appendChild(prompt);

    const wrapper = document.createElement('div');
    wrapper.className = 'number-input';

    const input = document.createElement('input');
    input.type = 'number';
    input.min = msg.min;
    input.max = msg.max;
    input.value = msg.min;
    input.id = '_num_input';

    const submitBtn = document.createElement('button');
    submitBtn.className = 'btn btn-primary';
    submitBtn.textContent = 'OK';

    const submit = () => {
        let val = parseInt(input.value, 10);
        if (isNaN(val)) val = msg.min;
        val = Math.max(msg.min, Math.min(msg.max, val));
        clearInput();
        appendMessage(`> ${val}`, 'dim');
        sendResponse(msg.id, val);
    };

    submitBtn.onclick = submit;
    input.onkeydown = (e) => { if (e.key === 'Enter') submit(); };

    wrapper.appendChild(input);
    wrapper.appendChild(submitBtn);
    area.appendChild(wrapper);
    input.focus();
}

// ── Checkbox ────────────────────────────────────────────────

function renderCheckbox(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.textContent = msg.message;
    area.appendChild(prompt);

    const list = document.createElement('div');
    const selected = new Set();

    for (const choice of msg.choices) {
        const item = document.createElement('label');
        item.className = 'checkbox-item';

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = choice;
        cb.onchange = () => {
            if (cb.checked) {
                selected.add(choice);
                item.classList.add('checked');
            } else {
                selected.delete(choice);
                item.classList.remove('checked');
            }
        };

        const label = document.createElement('span');
        label.textContent = choice;

        item.appendChild(cb);
        item.appendChild(label);
        list.appendChild(item);
    }

    area.appendChild(list);

    const submitBtn = document.createElement('button');
    submitBtn.className = 'btn btn-primary';
    submitBtn.textContent = 'Confirm';
    submitBtn.style.marginTop = '8px';
    submitBtn.onclick = () => {
        const vals = Array.from(selected);
        clearInput();
        appendMessage(`> ${vals.join(', ') || '(none)'}`, 'dim');
        sendResponse(msg.id, vals);
    };
    area.appendChild(submitBtn);
}

// ── Text ────────────────────────────────────────────────────

function renderText(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.textContent = msg.message;
    area.appendChild(prompt);

    const wrapper = document.createElement('div');
    wrapper.className = 'text-input';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = msg.default || '';
    input.placeholder = msg.default || '';

    const submitBtn = document.createElement('button');
    submitBtn.className = 'btn btn-primary';
    submitBtn.textContent = 'OK';

    const submit = () => {
        const val = input.value || msg.default || '';
        clearInput();
        appendMessage(`> ${val}`, 'dim');
        sendResponse(msg.id, val);
    };

    submitBtn.onclick = submit;
    input.onkeydown = (e) => { if (e.key === 'Enter') submit(); };

    wrapper.appendChild(input);
    wrapper.appendChild(submitBtn);
    area.appendChild(wrapper);
    input.focus();
    input.select();
}

// ── Pause ───────────────────────────────────────────────────

function renderPause(area, msg) {
    area.innerHTML = '';

    const btn = document.createElement('button');
    btn.className = 'btn btn-continue';
    btn.textContent = msg.message || 'Continue';
    btn.onclick = () => {
        clearInput();
        sendResponse(msg.id, true);
    };
    area.appendChild(btn);
    btn.focus();
}

// ── Mission Result Overlay ──────────────────────────────────

function renderMissionResult(area, msg) {
    area.innerHTML = '';

    const overlay = document.createElement('div');
    overlay.className = 'mission-result-overlay';

    const isSuccess = msg.success;
    const banner = document.createElement('div');
    banner.className = `mission-result-banner ${isSuccess ? 'mission-success' : 'mission-failure'}`;

    const title = document.createElement('div');
    title.className = 'mission-result-title';
    title.textContent = msg.title || (isSuccess ? 'MISSION SUCCESS' : 'MISSION FAILED');
    banner.appendChild(title);

    if (msg.detail) {
        const detail = document.createElement('div');
        detail.className = 'mission-result-detail';
        detail.textContent = msg.detail;
        banner.appendChild(detail);
    }

    if (msg.summary && msg.summary.length > 0) {
        const summary = document.createElement('div');
        summary.className = 'mission-result-summary';
        for (const line of msg.summary) {
            const p = document.createElement('div');
            p.className = 'mission-summary-line';
            p.textContent = line;
            summary.appendChild(p);
        }
        banner.appendChild(summary);
    }

    const btn = document.createElement('button');
    btn.className = 'btn btn-primary mission-result-btn';
    btn.textContent = 'Continue';
    btn.onclick = () => {
        overlay.remove();
        clearInput();
        sendResponse(msg.id, true);
    };
    banner.appendChild(btn);

    overlay.appendChild(banner);
    area.appendChild(overlay);
    btn.focus();
}

// ── Mission Select (cards) ──────────────────────────────────

function renderMissionSelect(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.textContent = msg.prompt || 'Choose a mission:';
    area.appendChild(prompt);

    const grid = document.createElement('div');
    grid.className = 'mission-select-grid';

    for (const m of msg.missions) {
        const card = document.createElement('div');
        card.className = 'mission-select-card';
        card.tabIndex = 0;
        card.innerHTML = `
            <div class="mission-card-name">${escapeHtml(m.name)}</div>
            <div class="mission-card-desc">${escapeHtml(m.description)}</div>
            <div class="mission-card-rewards">${escapeHtml(m.rewards)}</div>
        `;
        card.onclick = () => {
            clearInput();
            sendResponse(msg.id, m.value !== undefined ? m.value : m.index);
        };
        card.onkeydown = (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
        };
        grid.appendChild(card);
    }

    area.appendChild(grid);
    const first = grid.querySelector('.mission-select-card');
    if (first) first.focus();
}

// ── Sector Select (map-based) ───────────────────────────────

function renderSectorSelect(area, msg) {
    area.innerHTML = '';

    if (msg.message) {
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        prompt.textContent = msg.message + ' (click a sector on the map)';
        area.appendChild(prompt);
    }

    // Derive button label from message (e.g. "Investigate which sector?" → "Investigate This Sector")
    const verb = (msg.message || '').split(' ')[0] || 'Select';
    const btnLabel = verb + ' This Sector';

    // Enable selection mode on the map
    enableMapSelection(msg.valid_ids, (sectorId) => {
        clearInput();
        appendMessage(`> Sector ${sectorId}`, 'dim');
        sendResponse(msg.id, sectorId);
    }, btnLabel);
}

// ── Experience Screen ───────────────────────────────────────

function renderExperienceScreen(area, msg) {
    console.log('[EXP] renderExperienceScreen called, msg:', JSON.stringify(msg).slice(0, 500));
    try { return _renderExperienceScreenInner(area, msg); } catch(e) { console.error('[EXP] Error:', e); area.innerHTML = `<div style="color:red">Experience screen error: ${e.message}</div>`; }
}
function _renderExperienceScreenInner(area, msg) {
    area.innerHTML = '';

    // Remove existing modal if any
    const existing = document.getElementById('experience-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'experience-modal';
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content exp-modal';

    let html = `
        <div class="modal-header">
            <h2>Experience Progression</h2>
            <button class="modal-close exp-continue-btn">&#10005;</button>
        </div>
        <div class="modal-body">
    `;

    // --- XP Gained Box ---
    html += '<div class="exp-rules-box">';
    html += '<div class="exp-rules-title">EXPERIENCE GAINED</div>';
    html += '<div class="exp-rules-list">';
    html += '<div class="exp-rule-row"><span class="exp-rule-val">+1</span><span class="exp-rule-text">Participated in the battle</span><span class="exp-rule-note">Every eligible character</span></div>';
    html += '<div class="exp-rule-row"><span class="exp-rule-val">+1</span><span class="exp-rule-text">Did not become a casualty</span><span class="exp-rule-note">Every eligible character</span></div>';
    html += '<div class="exp-rule-row"><span class="exp-rule-val">+1</span><span class="exp-rule-text">Directly killed an enemy Boss or Leader</span><span class="exp-rule-note">Once per battle</span></div>';
    html += '</div>';

    // Per-character XP awards
    if (msg.xp_awards && msg.xp_awards.length > 0) {
        html += '<div class="exp-awards">';
        for (const a of msg.xp_awards) {
            const cls = a.xp > 0 ? 'exp-award-positive' : 'exp-award-zero';
            html += `<div class="exp-award-row ${cls}">`;
            html += `<span class="exp-award-name">${escapeHtml(a.name)}</span>`;
            html += `<span class="exp-award-gain">+${a.xp} XP</span>`;
            html += `<span class="exp-award-reason">${escapeHtml(a.reasons)}</span>`;
            html += `<span class="exp-award-total">Total: ${a.total_xp} XP</span>`;
            html += '</div>';
        }
        html += '</div>';
    }
    html += '</div>';

    // --- Civvy Heroic Promotion ---
    if (msg.civvy_promotion) {
        const cp = msg.civvy_promotion;
        const cls = cp.promoted ? 'exp-civvy-success' : 'exp-civvy-fail';
        html += `<div class="exp-civvy-box ${cls}">`;
        html += '<div class="exp-civvy-title">CIVVY HEROIC PROMOTION</div>';
        html += `<div class="exp-civvy-roll">Rolled ${cp.roll} (2D6) — ${cp.promoted ? 'Promoted to grunt roster! (+1 grunt)' : 'Not promoted (need 10+)'}</div>`;
        html += '</div>';
    }

    // --- Full Roster Cards (reuses sidebar roster card layout) ---
    // Build an XP award lookup for quick access
    const xpAwardMap = {};
    if (msg.xp_awards) {
        for (const a of msg.xp_awards) xpAwardMap[a.name] = a;
    }

    for (const c of msg.characters) {
        const canAdvance = c.xp >= 5;
        const award = xpAwardMap[c.name];

        // Build per-card extra content: XP gain badge + advancement button
        let extra = '';
        if (award) {
            const gainCls = award.xp > 0 ? 'exp-gain-positive' : 'exp-gain-zero';
            extra += `<div class="exp-card-gain ${gainCls}">+${award.xp} XP <span class="exp-card-gain-reason">${escapeHtml(award.reasons)}</span></div>`;
        }
        if (canAdvance) {
            extra += `<button class="btn btn-accent exp-advance-btn" data-char="${escapeHtml(c.name)}">Advancement (5 XP)</button>`;
        }

        html += buildRosterCardHtml(c, {
            showEdit: false,
            highlightXp: true,
            extraHtml: extra,
        });
    }

    // Continue button inside modal
    html += '<div class="exp-modal-footer"><button class="btn btn-primary exp-continue-btn">Continue</button></div>';

    html += '</div>'; // modal-body

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Wire up advancement buttons
    modal.querySelectorAll('.exp-advance-btn').forEach(btn => {
        btn.onclick = () => openAdvancementModal(msg, btn.dataset.char);
    });

    // Wire up continue/close buttons
    const doClose = () => {
        overlay.remove();
        clearInput();
        sendResponse(msg.id, {action: 'done'});
    };
    modal.querySelectorAll('.exp-continue-btn').forEach(btn => {
        btn.onclick = doClose;
    });

    // Escape to close
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            doClose();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);

    // Auto-open advancement modal if returning from an advancement action
    if (msg.last_advancement) {
        openAdvancementModal(msg, msg.last_advancement.character, msg.last_advancement.description, msg.last_advancement.trade);
    }
}

function openAdvancementModal(msg, charName, resultDesc, tradeInfo) {
    const existing = document.getElementById('advancement-modal');
    if (existing) existing.remove();

    const char = msg.characters.find(c => c.name === charName);
    if (!char) return;

    const overlay = document.createElement('div');
    overlay.id = 'advancement-modal';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content adv-modal';

    const titlePart = char.title ? `<span class="roster-card-title">${escapeHtml(char.title)}</span> ` : '';
    const rolePart = char.role ? `<span class="roster-card-role">${escapeHtml(char.role)}</span> ` : '';
    const classPart = `<span class="exp-char-class">${capitalize(char.char_class)}${char.level != null ? ' ' + char.level : ''}</span>`;

    let html = `
        <div class="modal-header">
            <h2>Advancement</h2>
            <button class="modal-close" onclick="document.getElementById('advancement-modal').remove()">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="adv-char-identity">
                ${titlePart}<span class="exp-char-name">${escapeHtml(charName)}</span> ${rolePart}${classPart}
            </div>`;

    // Show result banner if returning from an advancement
    if (resultDesc) {
        let bannerExtra = '';
        if (tradeInfo) {
            const statLabels = {reactions:'Reactions',combat_skill:'Combat Skill',speed:'Speed',toughness:'Toughness',savvy:'Savvy',kill_points:'Kill Points'};
            const tradeLabel = statLabels[tradeInfo.trade_stat] || tradeInfo.trade_stat;
            bannerExtra = `<button class="btn btn-sm adv-trade-btn" data-rolled-stat="${tradeInfo.rolled_stat}" data-rolled-bonus="${tradeInfo.rolled_bonus}" data-trade-stat="${tradeInfo.trade_stat}">Trade for ${escapeHtml(tradeLabel)} instead</button>`;
        }
        html += `<div class="adv-result-banner">${escapeHtml(resultDesc)}${bannerExtra}</div>`;
    }

    const canRoll = char.xp >= 5;
    const xpChipClass = canRoll ? 'exp-xp-ready' : '';

    html += `<div class="adv-char-stats">
                <div class="stat-chip"><span class="label">React</span><span class="val">${char.reactions}</span></div>
                <div class="stat-chip"><span class="label">Speed</span><span class="val">${char.speed}"</span></div>
                <div class="stat-chip"><span class="label">Combat</span><span class="val">+${char.combat_skill}</span></div>
                <div class="stat-chip"><span class="label">Tough</span><span class="val">${char.toughness}</span></div>
                <div class="stat-chip"><span class="label">Savvy</span><span class="val">+${char.savvy}</span></div>
                <div class="stat-chip ${xpChipClass}"><span class="label">XP</span><span class="val">${char.xp}</span></div>
            </div>

            <div class="adv-section${canRoll ? '' : ' adv-section-disabled'}">
                <div class="adv-section-title">ROLL ADVANCEMENT <span class="adv-cost">(Cost: 5 XP)</span></div>
                <div class="adv-table">
                    <div class="adv-table-header">
                        <span class="adv-col-roll">D100</span>
                        <span class="adv-col-ability">Ability</span>
                        <span class="adv-col-detail">Advance</span>
                    </div>
                    <div class="adv-table-row"><span class="adv-col-roll">01-15</span><span class="adv-col-ability">Speed</span><span class="adv-col-detail">First: +2", then +1" (max 8")</span></div>
                    <div class="adv-table-row"><span class="adv-col-roll">16-35</span><span class="adv-col-ability">Reactions</span><span class="adv-col-detail">+1 each (max 6). Scientists may trade for Savvy.</span></div>
                    <div class="adv-table-row"><span class="adv-col-roll">36-55</span><span class="adv-col-ability">Combat Skill</span><span class="adv-col-detail">+1 each (max +5). Scouts may trade for Reactions.</span></div>
                    <div class="adv-table-row"><span class="adv-col-roll">56-75</span><span class="adv-col-ability">Toughness</span><span class="adv-col-detail">+1 each (max 6)</span></div>
                    <div class="adv-table-row"><span class="adv-col-roll">76-90</span><span class="adv-col-ability">Savvy</span><span class="adv-col-detail">+1 each (max +5). Troopers may trade for Toughness.</span></div>
                    <div class="adv-table-row"><span class="adv-col-roll">91-00</span><span class="adv-col-ability">Kill Points</span><span class="adv-col-detail">+1 KP (max 3)</span></div>
                </div>
                <button class="btn btn-accent adv-roll-btn"${canRoll ? '' : ' disabled'}>Roll D100 (5 XP)</button>
            </div>

            <div class="adv-section">
                <div class="adv-section-title">BUY ADVANCEMENT</div>
                <div class="adv-buy-table">`;

    const buyItems = [
        {stat: 'reactions', label: 'Reactions', cost: 7, max: 6, current: char.reactions, display: char.reactions},
        {stat: 'combat_skill', label: 'Combat Skill', cost: 7, max: 5, current: char.combat_skill, display: '+' + char.combat_skill},
        {stat: 'speed', label: 'Speed', cost: 5, max: 8, current: char.speed, display: char.speed + '"'},
        {stat: 'toughness', label: 'Toughness', cost: 6, max: 6, current: char.toughness, display: char.toughness},
        {stat: 'savvy', label: 'Savvy', cost: 5, max: 5, current: char.savvy, display: '+' + char.savvy},
    ];

    for (const item of buyItems) {
        const atMax = item.current >= item.max;
        const canAfford = char.xp >= item.cost;
        const disabled = atMax || !canAfford;
        html += `<div class="adv-buy-row${disabled ? ' adv-buy-disabled' : ''}">`;
        html += `<span class="adv-buy-stat">${item.label}</span>`;
        html += `<span class="adv-buy-current">${item.display}</span>`;
        html += `<span class="adv-buy-cost">${item.cost} XP</span>`;
        html += `<span class="adv-buy-max">max ${item.max}</span>`;
        if (atMax) {
            html += `<span class="adv-buy-maxed">MAXED</span>`;
        } else {
            html += `<button class="btn btn-sm adv-buy-btn" data-stat="${item.stat}"${disabled ? ' disabled' : ''}>Buy</button>`;
        }
        html += '</div>';
    }

    html += `</div>
            </div>

            <div class="adv-section">
                <div class="adv-section-title">ALTERNATIVE OPTIONS <span class="adv-cost">(Cost: 5 XP)</span></div>
                <div class="adv-alt-options">`;

    // Loyalty option
    const isLoyal = char.loyalty === 'loyal';
    const altDisabled = !canRoll;  // need 5 XP for any alternative
    html += `<div class="adv-alt-row${isLoyal || altDisabled ? ' adv-buy-disabled' : ''}">`;
    html += `<span class="adv-alt-desc">Increase Loyalty to Loyal</span>`;
    if (isLoyal) {
        html += `<span class="adv-buy-maxed">ALREADY LOYAL</span>`;
    } else {
        html += `<button class="btn btn-sm adv-alt-btn" data-choice="loyalty"${altDisabled ? ' disabled' : ''}>Spend 5 XP</button>`;
    }
    html += '</div>';

    // Scientist: 3 RP
    if (char.char_class === 'scientist') {
        html += `<div class="adv-alt-row${altDisabled ? ' adv-buy-disabled' : ''}">`;
        html += `<span class="adv-alt-desc">Gain 3 Research Points (Scientist)</span>`;
        html += `<button class="btn btn-sm adv-alt-btn" data-choice="research_points"${altDisabled ? ' disabled' : ''}>Spend 5 XP</button>`;
        html += '</div>';
    }

    // Scout: 3 RM
    if (char.char_class === 'scout') {
        html += `<div class="adv-alt-row${altDisabled ? ' adv-buy-disabled' : ''}">`;
        html += `<span class="adv-alt-desc">Gain 3 Raw Materials (Scout)</span>`;
        html += `<button class="btn btn-sm adv-alt-btn" data-choice="raw_materials"${altDisabled ? ' disabled' : ''}>Spend 5 XP</button>`;
        html += '</div>';
    }

    html += `</div>
            </div>
        </div>
    `;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Wire up Roll button
    modal.querySelector('.adv-roll-btn').onclick = () => {
        overlay.remove();
        clearInput();
        sendResponse(msg.id, {action: 'roll', character: charName});
    };

    // Wire up Buy buttons
    modal.querySelectorAll('.adv-buy-btn').forEach(btn => {
        btn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'buy', character: charName, stat: btn.dataset.stat});
        };
    });

    // Wire up Trade button (if present)
    const tradeBtn = modal.querySelector('.adv-trade-btn');
    if (tradeBtn) {
        tradeBtn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {
                action: 'trade', character: charName,
                rolled_stat: tradeBtn.dataset.rolledStat,
                rolled_bonus: parseInt(tradeBtn.dataset.rolledBonus),
                trade_stat: tradeBtn.dataset.tradeStat,
            });
        };
    }

    // Wire up Alternative buttons
    modal.querySelectorAll('.adv-alt-btn').forEach(btn => {
        btn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'alternate', character: charName, choice: btn.dataset.choice});
        };
    });

    // Escape to close
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}

// ── Research Spending Modal ─────────────────────────────────

function renderResearchSpending(area, msg) {
    area.innerHTML = '';

    const existing = document.getElementById('research-spend-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'research-spend-modal';
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '800px';

    const rp = msg.rp_available || 0;
    const theories = msg.theories || [];
    const apps = msg.applications || [];
    const rpGained = msg.rp_gained || 0;
    const lastAction = msg.last_action_desc || '';

    // Build apps-by-theory lookup for unlock buttons
    const appsByTheory = {};
    for (const a of apps) {
        if (!appsByTheory[a.theory]) appsByTheory[a.theory] = {apps: [], cost: a.cost};
        appsByTheory[a.theory].apps.push(a);
    }

    let html = `
        <div class="modal-header">
            <h2>Research</h2>
            <button class="modal-close rs-done-btn">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="research-rp-box">
                <span class="research-rp-label">Research Points Available</span>
                <span class="research-rp-value">${rp} RP</span>
            </div>`;

    if (rpGained > 0) {
        html += `<div class="rs-gained">+${rpGained} Research Points gained this turn</div>`;
    }

    if (lastAction) {
        html += `<div class="adv-result-banner">${escapeHtml(lastAction)}</div>`;
    }

    // Theories — sorted: completed first, then by name
    if (theories.length > 0) {
        const sortedTheories = [...theories].sort((a, b) => {
            const aInv = a.invested_rp ?? a.invested ?? 0;
            const bInv = b.invested_rp ?? b.invested ?? 0;
            const aComplete = aInv >= (a.rp_cost || 0);
            const bComplete = bInv >= (b.rp_cost || 0);
            if (aComplete && !bComplete) return -1;
            if (!aComplete && bComplete) return 1;
            return 0;
        });

        html += '<h4 class="tt-section-header">Theories</h4>';
        html += '<div class="tt-grid">';
        for (const t of sortedTheories) {
            const invested = t.invested_rp ?? t.invested ?? 0;
            const cost = t.rp_cost || 0;
            const remaining = cost - invested;
            const completed = invested >= cost;

            // Build action buttons for this theory
            let buttonsHtml = '<div class="rs-theory-actions">';
            if (!completed && remaining > 0) {
                const canBuy = rp >= remaining;
                buttonsHtml += `<button class="btn btn-sm btn-accent rs-invest-btn" data-theory="${escapeHtml(t.id)}" data-amount="${remaining}"${canBuy ? '' : ' disabled'}>Complete Theory (${remaining} RP)</button>`;
            }
            const theoryApps = appsByTheory[t.name];
            if (completed && theoryApps && theoryApps.apps.length > 0) {
                const canAfford = rp >= theoryApps.cost;
                buttonsHtml += `<button class="btn btn-sm rs-app-btn" data-theory="${escapeHtml(t.name)}"${canAfford ? '' : ' disabled'}>Unlock Application (${theoryApps.cost} RP)</button>`;
            } else if (!completed) {
                buttonsHtml += `<button class="btn btn-sm rs-app-btn" disabled>Unlock Application</button>`;
            }
            buttonsHtml += '</div>';

            html += buildTheoryCardHtml(t, { extraHtml: buttonsHtml });
        }
        html += '</div>';
    }

    // Bio-analysis — per-specimen
    const specimens = msg.bio_specimens || [];
    if (specimens.length > 0) {
        html += '<h4 class="tt-section-header" style="margin-top:16px;">Bio-Analysis</h4>';
        html += '<div class="rs-other">';
        for (const spec of specimens) {
            if (spec.analyzed) {
                html += `<div class="rs-app-row rs-bio-done">`;
                html += `<span class="rs-app-theory">${escapeHtml(spec.name)}</span>`;
                html += `<span class="rs-app-count">&#10003; Analyzed</span>`;
                html += `</div>`;
            } else {
                const canAfford = rp >= 3;
                html += `<div class="rs-app-row${canAfford ? '' : ' adv-buy-disabled'}">`;
                html += `<span class="rs-app-theory">${escapeHtml(spec.name)}</span>`;
                html += `<span class="rs-app-count">Specimen available</span>`;
                html += `<span class="rs-app-cost">3 RP</span>`;
                html += `<button class="btn btn-sm rs-bio-btn" data-lifeform="${escapeHtml(spec.name)}"${canAfford ? '' : ' disabled'}>Analyze</button>`;
                html += `</div>`;
            }
        }
        html += '</div>';
    }

    // Done button
    html += '<div class="exp-modal-footer"><button class="btn btn-primary rs-done-btn">Done</button></div>';

    html += '</div>'; // modal-body

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Wire up invest buttons
    modal.querySelectorAll('.rs-invest-btn').forEach(btn => {
        btn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'invest', theory_id: btn.dataset.theory, amount: parseInt(btn.dataset.amount)});
        };
    });

    // Wire up app unlock buttons
    modal.querySelectorAll('.rs-app-btn').forEach(btn => {
        btn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'unlock_app', theory_name: btn.dataset.theory});
        };
    });

    // Wire up bio-analysis buttons
    modal.querySelectorAll('.rs-bio-btn').forEach(btn => {
        btn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'bio_analysis', lifeform_name: btn.dataset.lifeform});
        };
    });

    // Wire up done/close buttons
    const doDone = () => {
        overlay.remove();
        clearInput();
        sendResponse(msg.id, {action: 'done'});
    };
    modal.querySelectorAll('.rs-done-btn').forEach(btn => {
        btn.onclick = doDone;
    });
}

function renderBuildingSpending(area, msg) {
    area.innerHTML = '';

    const existing = document.getElementById('building-spend-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'building-spend-modal';
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '800px';

    const bp = msg.bp_available || 0;
    const rm = msg.rm_available || 0;
    const bpGained = msg.bp_gained || 0;
    const built = msg.built || [];
    const available = msg.available || [];
    const inProgress = msg.in_progress || {};
    const lastAction = msg.last_action_desc || '';

    let html = `
        <div class="modal-header">
            <h2>Building</h2>
            <button class="modal-close bld-done-btn">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="bld-resources">
                <div class="bld-res-box">
                    <span class="bld-res-label">Build Points</span>
                    <span class="bld-res-value">${bp} BP</span>
                </div>
                <div class="bld-res-box">
                    <span class="bld-res-label">Raw Materials</span>
                    <span class="bld-res-value">${rm} RM</span>
                </div>
            </div>`;

    if (bpGained > 0) {
        html += `<div class="rs-gained">+${bpGained} Build Points gained this turn</div>`;
    }

    if (lastAction) {
        html += `<div class="adv-result-banner">${escapeHtml(lastAction)}</div>`;
    }

    // Built buildings (at top)
    if (built.length > 0) {
        html += '<div class="rs-section-title">CONSTRUCTED</div>';
        html += '<div class="bld-built">';
        for (const name of built) {
            html += `<div class="bld-built-item">&#10003; ${escapeHtml(name)}</div>`;
        }
        html += '</div>';
    }

    // Raw Materials conversion (3 RM = 1 BP)
    if (rm >= 3) {
        const maxConvert = rm;
        const bpFromRm = Math.floor(maxConvert / 3);
        html += '<div class="rs-section-title">CONVERT RAW MATERIALS</div>';
        html += '<div class="bld-convert">';
        html += `<span class="bld-convert-info">3 Raw Materials = 1 Build Point (have ${rm} RM)</span>`;
        html += `<select class="bld-convert-select" id="bld-rm-amount">`;
        for (let i = 3; i <= maxConvert; i += 3) {
            html += `<option value="${i}">${i} RM → ${Math.floor(i/3)} BP</option>`;
        }
        html += `</select>`;
        html += `<button class="btn btn-sm btn-accent bld-convert-btn">Convert</button>`;
        html += '</div>';
    }

    // In-progress buildings
    const inProgressEntries = Object.entries(inProgress);
    if (inProgressEntries.length > 0) {
        html += '<div class="rs-section-title">IN PROGRESS</div>';
        html += '<div class="bld-list">';
        for (const [bid, info] of inProgressEntries) {
            const remaining = info.total - info.invested;
            const pct = Math.round((info.invested / info.total) * 100);
            const canFinish = bp >= remaining;
            html += `<div class="bld-card">`;
            html += `<div class="bld-card-header">`;
            html += `<span class="bld-card-name">${escapeHtml(info.name)}</span>`;
            html += `<span class="bld-card-cost">${info.invested}/${info.total} BP</span>`;
            html += `</div>`;
            html += `<div class="progress-bar" style="margin:4px 0 6px;"><div class="progress-fill" style="width:${pct}%;background:var(--accent-yellow)"></div></div>`;
            html += `<span class="bld-card-remaining">${remaining} BP remaining</span>`;
            html += `<button class="btn btn-sm btn-accent bld-build-btn" data-id="${escapeHtml(bid)}" data-cost="${remaining}"${canFinish ? '' : ' disabled'}>Complete (${remaining} BP)</button>`;
            html += `</div>`;
        }
        html += '</div>';
    }

    // Available new buildings
    const newBuildings = available.filter(b => b.progress === 0);
    if (newBuildings.length > 0) {
        html += '<div class="rs-section-title">AVAILABLE BUILDINGS</div>';
        html += '<div class="bld-list">';
        for (const b of newBuildings) {
            const canAfford = bp >= b.bp_cost;
            const milestoneTag = b.is_milestone ? ' <span class="bld-milestone-tag">MILESTONE</span>' : '';
            html += `<div class="bld-card">`;
            html += `<div class="bld-card-header">`;
            html += `<span class="bld-card-name">${escapeHtml(b.name)}${milestoneTag}</span>`;
            html += `<span class="bld-card-cost">${b.bp_cost} BP</span>`;
            html += `</div>`;
            if (b.description) html += `<div class="bld-card-desc">${escapeHtml(b.description)}</div>`;
            html += `<button class="btn btn-sm btn-accent bld-build-btn" data-id="${escapeHtml(b.id)}" data-cost="${b.bp_cost}"${canAfford ? '' : ' disabled'}>Build (${b.bp_cost} BP)</button>`;
            html += `</div>`;
        }
        html += '</div>';
    }

    // Done button
    html += '<div class="exp-modal-footer"><button class="btn btn-primary bld-done-btn">Done</button></div>';

    html += '</div>'; // modal-body

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Wire up build buttons
    modal.querySelectorAll('.bld-build-btn').forEach(btn => {
        btn.onclick = () => {
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'build', building_id: btn.dataset.id, bp_amount: parseInt(btn.dataset.cost), rm_convert: 0});
        };
    });

    // Wire up convert button
    const convertBtn = modal.querySelector('.bld-convert-btn');
    if (convertBtn) {
        convertBtn.onclick = () => {
            const sel = document.getElementById('bld-rm-amount');
            const rmAmount = parseInt(sel.value);
            overlay.remove();
            clearInput();
            sendResponse(msg.id, {action: 'convert', rm_amount: rmAmount});
        };
    }

    // Wire up done/close buttons
    const doDone = () => {
        overlay.remove();
        clearInput();
        sendResponse(msg.id, {action: 'done'});
    };
    modal.querySelectorAll('.bld-done-btn').forEach(btn => {
        btn.onclick = doDone;
    });
}

function showLoadingModal(title) {
    const existing = document.getElementById('narrative-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'narrative-modal';
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content narrative-modal';
    modal.innerHTML = `
        <div class="modal-header">
            <h2>${escapeHtml(title)}</h2>
        </div>
        <div class="modal-body">
            <div class="narrative-loading"><div class="spinner"></div><p>Generating...</p></div>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

function renderInfoModal(msg) {
    // Map modal name to opener function
    const openers = {
        'enemies': typeof openEnemiesModal !== 'undefined' ? openEnemiesModal : null,
        'ancient_signs': typeof openAncientSignsModal !== 'undefined' ? openAncientSignsModal : null,
        'lifeforms': typeof openLifeformsModal !== 'undefined' ? openLifeformsModal : null,
        'conditions': typeof openConditionsModal !== 'undefined' ? openConditionsModal : null,
        'research': typeof openResearchModal !== 'undefined' ? openResearchModal : null,
        'roster': typeof openRosterModal !== 'undefined' ? openRosterModal : null,
    };
    const opener = openers[msg.modal];
    if (opener) {
        opener();
        // Find the modal that was just opened and hook its close to send response
        const modalId = msg.modal.replace(/_/g, '-') + '-modal';
        const checkClose = setInterval(() => {
            if (!document.getElementById(modalId)) {
                clearInterval(checkClose);
                sendResponse(msg.id, 'closed');
            }
        }, 200);
    } else {
        sendResponse(msg.id, 'closed');
    }
}

function renderNarrativeModal(area, msg) {
    area.innerHTML = '';

    const title = msg.title || 'Colony Log';
    const text = msg.text || '';

    // If a loading modal is already open, update it in place
    let overlay = document.getElementById('narrative-modal');
    let modal;
    if (overlay) {
        modal = overlay.querySelector('.modal-content');
    } else {
        overlay = document.createElement('div');
        overlay.id = 'narrative-modal';
        overlay.className = 'modal-overlay';
        modal = document.createElement('div');
        modal.className = 'modal-content narrative-modal';
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    const doClose = () => {
        overlay.remove();
        clearInput();
        sendResponse(msg.id, {action: 'close'});
    };

    modal.innerHTML = `
        <div class="modal-header">
            <h2>${escapeHtml(title)}</h2>
            <button class="modal-close nar-close-btn">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="colony-log-content">${simpleMarkdown(text.trim())}</div>
        </div>
    `;

    overlay.onclick = (e) => { if (e.target === overlay) doClose(); };
    modal.querySelector('.nar-close-btn').onclick = doClose;

    // ESC to close
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            doClose();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}


// ── Reroll Offer ───────────────────────────────────────────
function renderRerollOffer(area, msg) {
    area.innerHTML = '';
    const panel = document.createElement('div');
    panel.className = 'reroll-offer-panel';

    const r = msg.result;
    const effectsHtml = r.effects
        ? `<div class="ro-effects">${escapeHtml(r.effects)}</div>`
        : '';

    panel.innerHTML = `
        <div class="ro-card">
            <div class="ro-table-name">${escapeHtml(msg.table_name)}</div>
            <div class="ro-roll">Roll: ${r.roll}</div>
            <div class="ro-name">${escapeHtml(r.name)}</div>
            <div class="ro-desc">${escapeHtml(r.description)}</div>
            ${effectsHtml}
        </div>
        <div class="ro-offer">
            <span class="ro-sp-info">Spend 1 Story Point to reroll? (${msg.sp_available} SP available)</span>
            <div class="ro-buttons">
                <button class="btn btn-primary ro-btn-reroll">Reroll (1 SP)</button>
                <button class="btn ro-btn-keep">Keep Result</button>
            </div>
        </div>
    `;

    panel.querySelector('.ro-btn-reroll').onclick = () => {
        area.innerHTML = '';
        sendResponse(msg.id, true);
    };
    panel.querySelector('.ro-btn-keep').onclick = () => {
        area.innerHTML = '';
        sendResponse(msg.id, false);
    };

    area.appendChild(panel);
}


// ── Resource Cache ─────────────────────────────────────────
function renderResourceCache(area, msg) {
    const budget = msg.budget;
    const spRemaining = msg.sp_remaining;
    let bp = 0, rp = 0, rm = 0;

    area.innerHTML = '';
    const panel = document.createElement('div');
    panel.className = 'resource-cache-panel';

    function remaining() { return budget - bp - rp - rm; }

    function render() {
        panel.innerHTML = `
            <div class="rc-header">
                <h3>Resource Cache</h3>
                <span class="rc-sp-badge">${spRemaining} SP remaining</span>
            </div>
            <div class="rc-dice">
                <span class="rc-dice-label">Rolled 2D6 — Budget:</span>
                <span class="rc-budget-value">${budget}</span>
            </div>
            <div class="rc-remaining ${remaining() === 0 ? 'rc-zero' : ''}">
                ${remaining()} point${remaining() !== 1 ? 's' : ''} to allocate
            </div>
            <div class="rc-resources">
                ${_rcRow('Build Points', 'bp', bp, 'var(--accent-orange, #f0a030)')}
                ${_rcRow('Research Points', 'rp', rp, 'var(--accent-cyan, #40d0d0)')}
                ${_rcRow('Raw Materials', 'rm', rm, 'var(--accent-green, #40c040)')}
            </div>
            <button class="btn btn-primary rc-confirm" ${remaining() < 0 ? 'disabled' : ''}>
                Confirm Allocation
            </button>
        `;

        // Wire +/- buttons
        panel.querySelectorAll('.rc-btn-minus').forEach(btn => {
            btn.onclick = () => {
                const key = btn.dataset.key;
                if (key === 'bp' && bp > 0) bp--;
                else if (key === 'rp' && rp > 0) rp--;
                else if (key === 'rm' && rm > 0) rm--;
                render();
            };
        });
        panel.querySelectorAll('.rc-btn-plus').forEach(btn => {
            btn.onclick = () => {
                if (remaining() <= 0) return;
                const key = btn.dataset.key;
                if (key === 'bp') bp++;
                else if (key === 'rp') rp++;
                else if (key === 'rm') rm++;
                render();
            };
        });

        panel.querySelector('.rc-confirm').onclick = () => {
            area.innerHTML = '';
            sendResponse(msg.id, { bp, rp, rm });
        };
    }

    function _rcRow(label, key, val, color) {
        return `
            <div class="rc-row">
                <span class="rc-resource-label" style="color:${color}">${label}</span>
                <div class="rc-controls">
                    <button class="btn rc-btn-minus" data-key="${key}" ${val <= 0 ? 'disabled' : ''}>−</button>
                    <span class="rc-value">${val}</span>
                    <button class="btn rc-btn-plus" data-key="${key}" ${remaining() <= 0 ? 'disabled' : ''}>+</button>
                </div>
            </div>
        `;
    }

    render();
    area.appendChild(panel);
}


// ── Reroll Choice ──────────────────────────────────────────
function renderRerollChoice(area, msg) {
    area.innerHTML = '';
    const panel = document.createElement('div');
    panel.className = 'reroll-choice-panel';

    const optA = msg.option_a;
    const optB = msg.option_b;

    panel.innerHTML = `
        <div class="reroll-header">
            <h3>Story Point Reroll</h3>
            <span class="reroll-table-name">${escapeHtml(msg.table_name)}</span>
        </div>
        <div class="reroll-subtitle">Choose which result to keep:</div>
        <div class="reroll-cards">
            <div class="reroll-card" data-choice="a">
                <div class="reroll-card-badge">Original</div>
                <div class="reroll-card-roll">Roll: ${optA.roll}</div>
                <div class="reroll-card-name">${escapeHtml(optA.name)}</div>
                <div class="reroll-card-desc">${escapeHtml(optA.description)}</div>
            </div>
            <div class="reroll-card reroll-card-new" data-choice="b">
                <div class="reroll-card-badge">Reroll</div>
                <div class="reroll-card-roll">Roll: ${optB.roll}</div>
                <div class="reroll-card-name">${escapeHtml(optB.name)}</div>
                <div class="reroll-card-desc">${escapeHtml(optB.description)}</div>
            </div>
        </div>
    `;

    panel.querySelectorAll('.reroll-card').forEach(card => {
        card.onclick = () => {
            area.innerHTML = '';
            sendResponse(msg.id, card.dataset.choice);
        };
    });

    area.appendChild(panel);
}
