/**
 * Planetfall Web UI — Input form generators.
 *
 * Each input type creates a UI in #input-area, sends back the response,
 * then clears itself.
 */

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
        case 'roster_editor':
            renderRosterEditor(msg);
            break;
        case 'colony_setup':
            renderColonySetup(msg);
            break;
        case 'colony_ready':
            renderColonyReady(msg);
            break;
        case 'sector_select':
            renderSectorSelect(area, msg);
            break;
        case 'weapon_select':
            renderWeaponSelect(area, msg);
            break;
        case 'deployment':
            renderDeployment(area, msg);
            break;
        case 'deploy_zone':
            renderDeployZone(area, msg);
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

    // Character profile card (e.g. Lock and Load weapon selection)
    if (msg.active_figure) {
        const f = msg.active_figure;
        const profile = document.createElement('div');
        profile.className = 'action-figure-profile';
        let html = `<div class="afp-header">
            <span class="afp-name">${escapeHtml(f.name)}</span>
            <span class="afp-class">${escapeHtml(f.char_class || '')}</span>
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
        profile.innerHTML = html;
        area.appendChild(profile);
    }

    if (msg.message) {
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        prompt.textContent = msg.message;
        area.appendChild(prompt);
    }

    const list = document.createElement('div');
    list.className = 'choice-list';

    for (const choice of msg.choices) {
        const btn = document.createElement('button');
        btn.className = 'choice-item';
        btn.textContent = choice;
        btn.onclick = () => {
            clearInput();
            appendMessage(`> ${choice}`, 'dim');
            sendResponse(msg.id, choice);
        };
        list.appendChild(btn);
    }

    area.appendChild(list);

    // Focus first choice for keyboard nav
    const first = list.querySelector('.choice-item');
    if (first) first.focus();
}

// ── Weapon Select (Lock and Load — weapon cards with stats) ──

function renderWeaponSelect(area, msg) {
    area.innerHTML = '';

    // Character profile card
    if (msg.active_figure) {
        const f = msg.active_figure;
        const profile = document.createElement('div');
        profile.className = 'action-figure-profile';
        let html = `<div class="afp-header">
            <span class="afp-name">${escapeHtml(f.name)}</span>
            <span class="afp-class">${escapeHtml(f.char_class || '')}</span>
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
        profile.innerHTML = html;
        area.appendChild(profile);
    }

    if (msg.message) {
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        prompt.textContent = msg.message;
        area.appendChild(prompt);
    }

    const list = document.createElement('div');
    list.className = 'weapon-list';

    for (const w of msg.weapons) {
        const btn = document.createElement('button');
        btn.className = 'weapon-card';
        if (w.tier === 'tier_1') btn.classList.add('weapon-tier1');
        if (w.tier === 'tier_2') btn.classList.add('weapon-tier2');

        let statsHtml = '';
        if (w.range > 0) statsHtml += `<span class="ws-stat"><span class="ws-label">Range</span>${w.range}"</span>`;
        else statsHtml += `<span class="ws-stat"><span class="ws-label">Range</span>Melee</span>`;
        statsHtml += `<span class="ws-stat"><span class="ws-label">Shots</span>${w.shots}</span>`;
        if (w.damage) statsHtml += `<span class="ws-stat"><span class="ws-label">Dmg</span>+${w.damage}</span>`;

        let traitsHtml = '';
        if (w.traits && w.traits.length) {
            traitsHtml = `<div class="ws-traits">${w.traits.map(t => escapeHtml(t.replace(/_/g, ' '))).join(', ')}</div>`;
        }

        btn.innerHTML = `
            <div class="ws-name">${escapeHtml(w.name)}</div>
            <div class="ws-stats">${statsHtml}</div>
            ${traitsHtml}
        `;
        btn.onclick = () => {
            clearInput();
            appendMessage(`> ${w.name}`, 'dim');
            sendResponse(msg.id, w.name);
        };
        list.appendChild(btn);
    }

    area.appendChild(list);

    const first = list.querySelector('.weapon-card');
    if (first) first.focus();
}

// ── Action Select (with shoot targets in info panel) ────────

// Global state for shoot targets available during action selection
let _activeShootTargets = [];
let _activeShootResponseId = null;

function renderActionSelect(area, msg) {
    area.innerHTML = '';

    // Store shoot targets globally for the info panel
    _activeShootTargets = msg.shoot_targets || [];
    _activeShootResponseId = msg.id;

    // Active figure profile
    if (msg.active_figure) {
        const f = msg.active_figure;
        const profile = document.createElement('div');
        profile.className = 'action-figure-profile';

        let html = `<div class="afp-header">
            <span class="afp-name">${escapeHtml(f.name)}</span>
            <span class="afp-label">${escapeHtml(f.label)}</span>
            <span class="afp-class">${escapeHtml(f.char_class)}</span>
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

        // Weapon
        let wParts = [f.weapon_name];
        wParts.push(`Range ${f.weapon_range}"`);
        wParts.push(`Shots ${f.weapon_shots}`);
        if (f.weapon_damage) wParts.push(`Dmg +${f.weapon_damage}`);
        if (f.weapon_traits && f.weapon_traits.length) wParts.push(f.weapon_traits.join(', '));
        html += `<div class="afp-weapon">${escapeHtml(wParts.join(' | '))}</div>`;

        // Statuses
        if (f.statuses && f.statuses.length) {
            html += `<div class="afp-statuses">${f.statuses.map(s => escapeHtml(s)).join(' | ')}</div>`;
        }

        profile.innerHTML = html;
        area.appendChild(profile);
    }

    if (msg.message) {
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        prompt.textContent = msg.message;
        area.appendChild(prompt);
    }

    const list = document.createElement('div');
    list.className = 'choice-list';

    for (const choice of msg.choices) {
        const btn = document.createElement('button');
        btn.className = 'choice-item';
        btn.textContent = choice;
        btn.onclick = () => {
            _activeShootTargets = [];
            _activeShootResponseId = null;
            clearInput();
            appendMessage(`> ${choice}`, 'dim');
            sendResponse(msg.id, choice);
        };
        list.appendChild(btn);
    }

    area.appendChild(list);

    // Refresh info panel to show shoot buttons if a zone with targets is selected
    if (_activeShootTargets.length > 0 && typeof refreshZoneDetailPanel === 'function') {
        refreshZoneDetailPanel();
    }

    const first = list.querySelector('.choice-item');
    if (first) first.focus();
}

function clearShootTargets() {
    _activeShootTargets = [];
    _activeShootResponseId = null;
}

function _renderBetweenTurnsBar(area, msg) {
    // Store state so the steps sidebar can also show a Commence Turn button
    setBetweenTurnsState(msg);

    const bar = document.createElement('div');
    bar.className = 'commence-turn-bar';

    // Start Day button (maps to "Continue to next turn")
    const nextTurn = (_lastColonyData && _lastColonyData.turn) ? _lastColonyData.turn + 1 : '?';
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
        appendMessage(`> Yes`, 'dim');
        sendResponse(msg.id, true);
    };

    const noBtn = document.createElement('button');
    noBtn.className = 'btn btn-danger';
    noBtn.textContent = 'No';
    noBtn.onclick = () => {
        clearInput();
        appendMessage(`> No`, 'dim');
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
    btn.className = 'btn';
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

// ── Deployment (Lock and Load) ──────────────────────────────

function renderDeployment(area, msg) {
    area.innerHTML = '';

    const available = msg.available || [];
    const maxSlots = msg.max_slots || 8;
    const gruntCount = msg.grunt_count || 0;
    const botAvailable = msg.bot_available || false;
    const charClasses = msg.char_classes || {};

    const selected = new Set();
    let grunts = 0;
    let bot = false;
    let civilians = 0;

    function getRemaining() {
        return maxSlots - selected.size - grunts - (bot ? 1 : 0) - civilians;
    }

    function render() {
        area.innerHTML = '';
        const remaining = getRemaining();

        // Header
        const header = document.createElement('div');
        header.className = 'input-prompt';
        header.textContent = `Deploy Squad (${selected.size + grunts + (bot?1:0) + civilians}/${maxSlots} slots)`;
        area.appendChild(header);

        // Character grid
        const grid = document.createElement('div');
        grid.className = 'deploy-grid';

        for (const name of available) {
            const card = document.createElement('div');
            const isSelected = selected.has(name);
            card.className = 'deploy-card' + (isSelected ? ' selected' : '');
            const cls = charClasses[name] || '';
            card.innerHTML = `<span class="deploy-name">${escapeHtml(name)}</span>${cls ? `<span class="deploy-class">${escapeHtml(cls)}</span>` : ''}`;
            card.onclick = () => {
                if (isSelected) {
                    selected.delete(name);
                } else if (getRemaining() > 0) {
                    selected.add(name);
                }
                render();
            };
            grid.appendChild(card);
        }
        area.appendChild(grid);

        // Support units row
        const support = document.createElement('div');
        support.className = 'deploy-support';

        // Grunts
        if (gruntCount > 0) {
            const maxGrunts = Math.min(gruntCount, remaining + grunts);
            const gruntRow = document.createElement('div');
            gruntRow.className = 'deploy-support-row';
            gruntRow.innerHTML = `
                <span class="deploy-support-label">Grunts (${gruntCount} available)</span>
                <div class="deploy-counter">
                    <button class="btn-counter" onclick="void(0)">−</button>
                    <span class="counter-val">${grunts}</span>
                    <button class="btn-counter" onclick="void(0)">+</button>
                </div>
            `;
            const btns = gruntRow.querySelectorAll('.btn-counter');
            btns[0].onclick = () => { if (grunts > 0) { grunts--; render(); } };
            btns[1].onclick = () => { if (grunts < maxGrunts && getRemaining() > 0) { grunts++; render(); } };
            support.appendChild(gruntRow);
        }

        // Bot
        if (botAvailable) {
            const botRow = document.createElement('div');
            botRow.className = 'deploy-support-row';
            botRow.innerHTML = `
                <span class="deploy-support-label">Security Bot</span>
                <button class="btn-toggle ${bot ? 'active' : ''}">${bot ? 'Deployed' : 'Available'}</button>
            `;
            botRow.querySelector('.btn-toggle').onclick = () => {
                if (bot) { bot = false; }
                else if (getRemaining() > 0) { bot = true; }
                render();
            };
            support.appendChild(botRow);
        }

        // Civilians
        const maxCiv = remaining + civilians;
        const civRow = document.createElement('div');
        civRow.className = 'deploy-support-row';
        civRow.innerHTML = `
            <span class="deploy-support-label">Civilian Volunteers</span>
            <div class="deploy-counter">
                <button class="btn-counter" onclick="void(0)">−</button>
                <span class="counter-val">${civilians}</span>
                <button class="btn-counter" onclick="void(0)">+</button>
            </div>
        `;
        const civBtns = civRow.querySelectorAll('.btn-counter');
        civBtns[0].onclick = () => { if (civilians > 0) { civilians--; render(); } };
        civBtns[1].onclick = () => { if (getRemaining() > 0) { civilians++; render(); } };
        support.appendChild(civRow);

        area.appendChild(support);

        // Deploy button
        const deployBtn = document.createElement('button');
        deployBtn.className = 'btn btn-primary';
        deployBtn.textContent = `Deploy Squad`;
        deployBtn.disabled = selected.size === 0;
        deployBtn.style.marginTop = '8px';
        deployBtn.onclick = () => {
            const result = {
                characters: Array.from(selected),
                grunts: grunts,
                bot: bot,
                civilians: civilians,
            };
            clearInput();
            appendMessage(`> Deployed ${selected.size} characters, ${grunts} grunts${bot ? ', bot' : ''}${civilians ? `, ${civilians} civilian${civilians>1?'s':''}` : ''}`, 'dim');
            sendResponse(msg.id, result);
        };
        area.appendChild(deployBtn);
    }

    render();
}

// ── Deploy Zone (click-on-map) ──────────────────────────────

function renderMovement(area, msg) {
    area.innerHTML = '';

    // Active figure profile
    if (msg.active_figure) {
        const f = msg.active_figure;
        const profile = document.createElement('div');
        profile.className = 'action-figure-profile';

        let html = `<div class="afp-header">
            <span class="afp-name">${escapeHtml(f.name)}</span>
            <span class="afp-label">${escapeHtml(f.label)}</span>
            <span class="afp-class">${escapeHtml(f.char_class)}</span>
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

        let wParts = [f.weapon_name];
        wParts.push(`Range ${f.weapon_range}"`);
        wParts.push(`Shots ${f.weapon_shots}`);
        if (f.weapon_damage) wParts.push(`Dmg +${f.weapon_damage}`);
        if (f.weapon_traits && f.weapon_traits.length) wParts.push(f.weapon_traits.join(', '));
        html += `<div class="afp-weapon">${escapeHtml(wParts.join(' | '))}</div>`;

        if (f.statuses && f.statuses.length) {
            html += `<div class="afp-statuses">${f.statuses.map(s => escapeHtml(s)).join(' | ')}</div>`;
        }

        profile.innerHTML = html;
        area.appendChild(profile);
    }

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.innerHTML = `Movement: <span style="color: var(--text-dim);">click a zone to move, or choose an option below</span>`;
    area.appendChild(prompt);

    // Buttons for non-zone actions
    const btnRow = document.createElement('div');
    btnRow.className = 'choice-list';
    btnRow.style.flexDirection = 'row';
    btnRow.style.flexWrap = 'wrap';
    btnRow.style.gap = '6px';

    const stayBtn = document.createElement('button');
    stayBtn.className = 'choice-item';
    stayBtn.textContent = msg.can_trooper_delay ? 'Delay Action' : 'Stay Stationary';
    stayBtn.onclick = () => {
        disableBattlefieldMovementSelect();
        clearInput();
        appendMessage('> Stay stationary', 'dim');
        sendResponse(msg.id, { type: 'stay' });
    };
    btnRow.appendChild(stayBtn);

    if (msg.can_scout_first) {
        const scoutBtn = document.createElement('button');
        scoutBtn.className = 'choice-item';
        scoutBtn.textContent = 'Take action first, then move';
        scoutBtn.onclick = () => {
            disableBattlefieldMovementSelect();
            clearInput();
            appendMessage('> Take action first', 'dim');
            sendResponse(msg.id, { type: 'scout_first' });
        };
        btnRow.appendChild(scoutBtn);
    }
    area.appendChild(btnRow);

    // Enable movement zone selection on the battlefield
    enableBattlefieldMovementSelect(msg.zones || [], (zone) => {
        disableBattlefieldMovementSelect();
        clearInput();
        const label = zone.move_type === 'dash' ? 'Dash' : 'Move';
        appendMessage(`> ${label} to (${zone.row},${zone.col})`, 'dim');
        sendResponse(msg.id, { type: zone.move_type, zone_idx: zone.index });
    });
}

function renderZoneSelect(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.innerHTML = `${escapeHtml(msg.message)} <span style="color: var(--text-dim);">— click a highlighted zone on the map</span>`;
    area.appendChild(prompt);

    // Convert zone_select data to deploy-style zones for reuse
    const validZones = (msg.valid_zones || []).map(z => ({row: z.row, col: z.col, index: z.index, label: z.label}));
    enableBattlefieldZoneSelect(validZones, (zone) => {
        disableBattlefieldZoneSelect();
        clearInput();
        appendMessage(`> ${zone.label || `Zone (${zone.row},${zone.col})`}`, 'dim');
        sendResponse(msg.id, zone.index);
    });
}

function renderDeployZone(area, msg) {
    area.innerHTML = '';

    const prompt = document.createElement('div');
    prompt.className = 'input-prompt';
    prompt.innerHTML = `${escapeHtml(msg.message)} <span style="color: var(--text-dim);">— click a highlighted zone on the map</span>`;
    area.appendChild(prompt);

    // Enable zone selection mode on the battlefield
    const validZones = msg.valid_zones || [];
    enableBattlefieldDeploySelect(validZones, (zone) => {
        disableBattlefieldDeploySelect();
        clearInput();
        appendMessage(`> Deployed to zone (${zone.row},${zone.col})`, 'dim');
        sendResponse(msg.id, { row: zone.row, col: zone.col });
    });
}

// ── Roster Editor ───────────────────────────────────────────

function renderRosterEditor(msg) {
    // Remove existing modal
    const existing = document.getElementById('roster-editor-modal');
    if (existing) existing.remove();

    const profiles = msg.class_profiles;
    const motivations = msg.motivations;
    const experiences = msg.experiences;
    const subspecies = msg.subspecies;
    let roster = JSON.parse(JSON.stringify(msg.default_roster));

    const overlay = document.createElement('div');
    overlay.id = 'roster-editor-modal';
    overlay.className = 'modal-overlay';
    // Don't close on backdrop click — this is required input

    const modal = document.createElement('div');
    modal.className = 'modal-content roster-editor';

    function render() {
        let html = `
            <div class="modal-header">
                <h2>Create Your Crew (${roster.length}/8)</h2>
                <div style="display: flex; gap: 8px;">
                    ${roster.length < 8 ? '<button class="btn btn-success" id="re-add-btn">+ Add Character</button>' : ''}
                    ${roster.length >= 1 ? '<button class="btn btn-primary" id="re-done-btn">Done &#10003;</button>' : ''}
                </div>
            </div>
            <div class="modal-body">
        `;

        for (let i = 0; i < roster.length; i++) {
            const c = roster[i];
            const p = profiles[c.char_class] || profiles['trooper'];
            const expTag = c.experienced ? ' (exp)' : '';
            const motLabel = c.motivation || 'not set';
            const priorLabel = c.prior_experience !== 'None' ? c.prior_experience : '';

            html += `
                <div class="roster-card">
                    <div class="roster-card-header">
                        <div class="roster-card-name">${escapeHtml(c.name)}</div>
                        <div class="roster-card-class">${capitalize(c.char_class)}${expTag}</div>
                        ${c.sub_species !== 'standard' ? `<div class="roster-card-title">${capitalize(c.sub_species)}</div>` : ''}
                        ${c.title ? `<div class="roster-card-title">${escapeHtml(c.title)}</div>` : ''}
                        ${c.role ? `<div class="roster-card-role">${escapeHtml(c.role)}</div>` : ''}
                    </div>
                    <div class="roster-card-stats">
                        <div class="stat-chip"><span class="label">React</span><span class="val">${p.reactions}</span></div>
                        <div class="stat-chip"><span class="label">Speed</span><span class="val">${p.speed}"</span></div>
                        <div class="stat-chip"><span class="label">Combat</span><span class="val">+${p.combat_skill}</span></div>
                        <div class="stat-chip"><span class="label">Tough</span><span class="val">${p.toughness}</span></div>
                        <div class="stat-chip"><span class="label">Savvy</span><span class="val">+${p.savvy}</span></div>
                    </div>
                    <div class="roster-card-info">
                        ${motLabel !== 'not set' ? `<div>Motivation: ${escapeHtml(motLabel)}</div>` : ''}
                        ${priorLabel ? `<div>Experience: ${escapeHtml(priorLabel)}</div>` : ''}
                    </div>
                    <div style="margin-top: 8px; display: flex; gap: 6px;">
                        <button class="btn" onclick="editRosterChar(${i})">Edit</button>
                        <button class="btn btn-danger" onclick="removeRosterChar(${i})">Remove</button>
                    </div>
                </div>
            `;
        }

        html += '</div>';
        modal.innerHTML = html;

        // Wire up buttons
        const addBtn = modal.querySelector('#re-add-btn');
        if (addBtn) addBtn.onclick = () => addRosterChar();

        const doneBtn = modal.querySelector('#re-done-btn');
        if (doneBtn) doneBtn.onclick = () => submitRoster();
    }

    // Store state in window for button callbacks
    window._rosterEditor = { roster, profiles, motivations, experiences, subspecies, render, modal, msg, overlay };

    render();
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

function addRosterChar() {
    const ed = window._rosterEditor;
    if (ed.roster.length >= 8) return;
    ed.roster.push({
        name: `Character ${ed.roster.length + 1}`,
        char_class: 'trooper',
        experienced: false,
        sub_species: 'standard',
        title: '', role: '',
        motivation: '', prior_experience: '',
        narrative_background: '',
    });
    ed.render();
    // Auto-open edit for the new character
    editRosterChar(ed.roster.length - 1);
}

function removeRosterChar(index) {
    const ed = window._rosterEditor;
    if (ed.roster.length <= 1) return;
    ed.roster.splice(index, 1);
    ed.render();
}

function editRosterChar(index) {
    const ed = window._rosterEditor;
    const c = ed.roster[index];
    const p = ed.profiles;

    // Remove existing edit modal
    const existing = document.getElementById('char-edit-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'char-edit-modal';
    overlay.className = 'modal-overlay';
    overlay.style.zIndex = '1001';

    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.style.maxWidth = '550px';

    const classOptions = ['scientist', 'scout', 'trooper'].map(cls =>
        `<option value="${cls}" ${c.char_class === cls ? 'selected' : ''}>${capitalize(cls)}</option>`
    ).join('');

    const subOptions = ed.subspecies.map(s =>
        `<option value="${s}" ${c.sub_species === s ? 'selected' : ''}>${capitalize(s)}</option>`
    ).join('');

    const motOptions = ['', ...ed.motivations].map(m =>
        `<option value="${m}" ${c.motivation === m ? 'selected' : ''}>${m || '(roll randomly)'}</option>`
    ).join('');

    const expOptions = [`<option value="" ${!c.prior_experience || c.prior_experience === 'None' ? 'selected' : ''}>(roll randomly)</option>`]
        .concat(ed.experiences.map(e =>
            `<option value="${e.name}" ${c.prior_experience === e.name ? 'selected' : ''}>${escapeHtml(e.label)}</option>`
        )).join('');
    const expDisabled = !c.experienced ? 'disabled' : '';

    modal.innerHTML = `
        <div class="modal-header">
            <h2>Edit Character</h2>
            <button class="modal-close" id="ce-cancel">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="edit-form">
                <div class="form-row">
                    <label>Name</label>
                    <input type="text" id="ce-name" value="${escapeHtml(c.name)}">
                </div>
                <div class="form-row">
                    <label>Class</label>
                    <select id="ce-class">${classOptions}</select>
                </div>
                <div class="form-row">
                    <label>Experienced</label>
                    <input type="checkbox" id="ce-exp" ${c.experienced ? 'checked' : ''}>
                </div>
                <div class="form-row">
                    <label>Sub-species</label>
                    <select id="ce-sub">${subOptions}</select>
                </div>
                <div class="form-row">
                    <label>Title <span style="color:var(--text-dim)">(optional)</span></label>
                    <input type="text" id="ce-title" value="${escapeHtml(c.title)}">
                </div>
                <div class="form-row">
                    <label>Role <span style="color:var(--text-dim)">(optional)</span></label>
                    <input type="text" id="ce-role" value="${escapeHtml(c.role)}">
                </div>
                <div class="form-row">
                    <label>Motivation</label>
                    <select id="ce-mot">${motOptions}</select>
                </div>
                <div class="form-row">
                    <label>Prior Experience</label>
                    <select id="ce-prior" ${expDisabled}>${expOptions}</select>
                </div>
                <div class="form-row">
                    <label>Background <span style="color:var(--text-dim)">(optional)</span></label>
                    <textarea id="ce-bg" rows="3">${escapeHtml(c.narrative_background)}</textarea>
                </div>
                <div id="ce-preview" class="roster-card-stats" style="margin-top: 12px;"></div>
                <div style="display: flex; gap: 8px; margin-top: 12px; justify-content: flex-end;">
                    <button class="btn" id="ce-cancel2">Cancel</button>
                    <button class="btn btn-primary" id="ce-save">Save</button>
                </div>
            </div>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Preview stats based on class + experience bonuses
    function updatePreview() {
        const cls = document.getElementById('ce-class').value;
        const prof = p[cls] || p['trooper'];
        const isExp = document.getElementById('ce-exp').checked;
        const priorSel = document.getElementById('ce-prior');
        const priorName = priorSel.value;

        // Base stats from class
        let stats = {
            reactions: prof.reactions, speed: prof.speed,
            combat_skill: prof.combat_skill, toughness: prof.toughness,
            savvy: prof.savvy,
        };

        // Apply experience bonuses
        let bonusLabel = '';
        if (isExp && priorName) {
            const exp = ed.experiences.find(e => e.name === priorName);
            if (exp && exp.effects) {
                const parts = [];
                for (const [stat, val] of Object.entries(exp.effects)) {
                    if (stat in stats) {
                        stats[stat] += val;
                        const labels = {reactions:'React',speed:'Speed',combat_skill:'Combat',toughness:'Tough',savvy:'Savvy'};
                        parts.push(`${labels[stat] || stat} +${val}`);
                    } else if (stat === 'xp') {
                        parts.push(`XP +${val}`);
                    } else if (stat === 'kill_points') {
                        parts.push(`KP +${val}`);
                    } else if (stat === 'loyalty') {
                        parts.push(`Loyalty → ${capitalize(val)}`);
                    } else if (stat === 'story_points') {
                        parts.push(`SP +${val}`);
                    }
                }
                if (parts.length) bonusLabel = `<div style="margin-top:4px;font-size:11px;color:var(--accent-yellow);">${escapeHtml(priorName)}: ${parts.join(', ')}</div>`;
            }
        }

        const preview = document.getElementById('ce-preview');
        preview.innerHTML = `
            <div class="stat-chip"><span class="label">React</span><span class="val">${stats.reactions}</span></div>
            <div class="stat-chip"><span class="label">Speed</span><span class="val">${stats.speed}"</span></div>
            <div class="stat-chip"><span class="label">Combat</span><span class="val">+${stats.combat_skill}</span></div>
            <div class="stat-chip"><span class="label">Tough</span><span class="val">${stats.toughness}</span></div>
            <div class="stat-chip"><span class="label">Savvy</span><span class="val">+${stats.savvy}</span></div>
            ${bonusLabel}
        `;
    }
    document.getElementById('ce-class').onchange = () => {
        // Update placeholder name when class changes
        const nameEl = document.getElementById('ce-name');
        const curName = nameEl.value.trim();
        if (/^(Scientist|Scout|Trooper|Character)\s+\d+$/i.test(curName)) {
            const newCls = capitalize(document.getElementById('ce-class').value);
            const num = curName.match(/\d+$/)[0];
            nameEl.value = `${newCls} ${num}`;
        }
        updatePreview();
    };
    document.getElementById('ce-prior').onchange = updatePreview;

    // Experienced checkbox toggles Prior Experience dropdown
    document.getElementById('ce-exp').onchange = () => {
        const priorSel = document.getElementById('ce-prior');
        priorSel.disabled = !document.getElementById('ce-exp').checked;
        if (!document.getElementById('ce-exp').checked) {
            priorSel.value = '';
        }
        updatePreview();
    };

    updatePreview();

    // Save
    document.getElementById('ce-save').onclick = () => {
        ed.roster[index] = {
            name: document.getElementById('ce-name').value || `Character ${index + 1}`,
            char_class: document.getElementById('ce-class').value,
            experienced: document.getElementById('ce-exp').checked,
            sub_species: document.getElementById('ce-sub').value,
            title: document.getElementById('ce-title').value,
            role: document.getElementById('ce-role').value,
            motivation: document.getElementById('ce-mot').value,
            prior_experience: document.getElementById('ce-prior').value,
            narrative_background: document.getElementById('ce-bg').value,
        };
        overlay.remove();
        ed.render();
    };

    // Cancel
    const close = () => overlay.remove();
    document.getElementById('ce-cancel').onclick = close;
    document.getElementById('ce-cancel2').onclick = close;

    // Focus name
    document.getElementById('ce-name').focus();
    document.getElementById('ce-name').select();
}

function submitRoster() {
    const ed = window._rosterEditor;
    if (ed.roster.length < 1) return;
    ed.overlay.remove();
    clearInput();
    appendMessage(`> Created ${ed.roster.length} characters`, 'dim');
    sendResponse(ed.msg.id, ed.roster);
    window._rosterEditor = null;
}

// ── Colony Setup Modal ─────────────────────────────────────

function renderColonySetup(msg) {
    const existing = document.getElementById('colony-setup-modal');
    if (existing) existing.remove();

    const profiles = msg.class_profiles;
    const motivations = msg.motivations;
    const experiences = msg.experiences;
    const subspecies = msg.subspecies;
    const agendas = msg.agendas;
    let roster = JSON.parse(JSON.stringify(msg.default_roster));

    const overlay = document.createElement('div');
    overlay.id = 'colony-setup-modal';
    overlay.className = 'modal-overlay';

    const modal = document.createElement('div');
    modal.className = 'modal-content colony-setup';

    // Store state for roster editor callbacks
    window._colonySetup = {
        roster, profiles, motivations, experiences, subspecies, agendas, msg, overlay, modal,
    };

    function renderSetup() {
        const cs = window._colonySetup;
        const agendaOptions = cs.agendas.map(a =>
            `<option value="${a.value}">${escapeHtml(a.label)}</option>`
        ).join('');

        let rosterHtml = '';
        for (let i = 0; i < cs.roster.length; i++) {
            const c = cs.roster[i];
            const p = cs.profiles[c.char_class] || cs.profiles['trooper'];
            const expTag = c.experienced ? ' <span style="color:var(--accent-yellow)">(exp)</span>' : '';

            rosterHtml += `
                <div class="setup-char-card">
                    <div class="setup-char-info">
                        <span class="setup-char-name">${escapeHtml(c.name)}</span>
                        <span class="setup-char-class">${capitalize(c.char_class)}${expTag}</span>
                        ${c.sub_species !== 'standard' ? `<span class="setup-char-sub">${capitalize(c.sub_species)}</span>` : ''}
                    </div>
                    <div class="setup-char-stats">
                        <span>R${p.reactions}</span>
                        <span>S${p.speed}"</span>
                        <span>C+${p.combat_skill}</span>
                        <span>T${p.toughness}</span>
                        <span>V+${p.savvy}</span>
                    </div>
                    <div class="setup-char-actions">
                        <button class="btn-sm" onclick="editSetupChar(${i})">Edit</button>
                        <button class="btn-sm btn-sm-danger" onclick="removeSetupChar(${i})">&#10005;</button>
                    </div>
                </div>
            `;
        }

        modal.innerHTML = `
            <div class="modal-header">
                <h2>New Colony</h2>
            </div>
            <div class="modal-body setup-body">
                <div class="setup-section">
                    <div class="setup-form">
                        <div class="form-row">
                            <label>Colony Name</label>
                            <input type="text" id="cs-colony" value="Haven">
                        </div>
                        <div class="form-row">
                            <label>Administrator</label>
                            <input type="text" id="cs-admin" value="Commander">
                        </div>
                        <div class="form-row">
                            <label>Agenda</label>
                            <select id="cs-agenda">${agendaOptions}</select>
                        </div>
                    </div>
                </div>
                <div class="setup-section">
                    <div class="setup-section-header">
                        <h3>Crew (${cs.roster.length}/8)</h3>
                        ${cs.roster.length < 8 ? '<button class="btn-sm btn-sm-success" id="cs-add-char">+ Add</button>' : ''}
                    </div>
                    <div class="setup-roster">
                        ${rosterHtml}
                    </div>
                </div>
                <div style="display: flex; justify-content: flex-end; padding-top: 8px;">
                    <button class="btn btn-primary" id="cs-launch" ${cs.roster.length < 1 ? 'disabled' : ''}>Launch Colony &#9654;</button>
                </div>
            </div>
        `;

        // Wire buttons
        const addBtn = modal.querySelector('#cs-add-char');
        if (addBtn) addBtn.onclick = () => addSetupChar();

        const launchBtn = modal.querySelector('#cs-launch');
        if (launchBtn) launchBtn.onclick = () => submitColonySetup();
    }

    window._colonySetup.render = renderSetup;
    renderSetup();
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

function addSetupChar() {
    const cs = window._colonySetup;
    if (cs.roster.length >= 8) return;
    cs.roster.push({
        name: `Character ${cs.roster.length + 1}`,
        char_class: 'trooper',
        experienced: false,
        sub_species: 'standard',
        title: '', role: '',
        motivation: '', prior_experience: '',
        narrative_background: '',
    });
    cs.render();
    editSetupChar(cs.roster.length - 1);
}

function removeSetupChar(index) {
    const cs = window._colonySetup;
    if (cs.roster.length <= 1) return;
    cs.roster.splice(index, 1);
    cs.render();
}

function editSetupChar(index) {
    // Reuse the same edit modal as roster editor
    const cs = window._colonySetup;
    // Temporarily set up _rosterEditor for editRosterChar to use
    window._rosterEditor = {
        roster: cs.roster,
        profiles: cs.profiles,
        motivations: cs.motivations,
        experiences: cs.experiences,
        subspecies: cs.subspecies,
        render: cs.render,
        modal: cs.modal,
        msg: cs.msg,
        overlay: cs.overlay,
    };
    editRosterChar(index);
}

function submitColonySetup() {
    const cs = window._colonySetup;
    if (cs.roster.length < 1) return;

    const colonyName = document.getElementById('cs-colony').value || 'Haven';
    const result = {
        campaign_name: colonyName,
        colony_name: colonyName,
        admin_name: document.getElementById('cs-admin').value || 'Commander',
        agenda: document.getElementById('cs-agenda').value,
        roster: cs.roster,
    };

    // Transform modal to loading state
    cs.modal.innerHTML = `
        <div class="modal-header"><h2>Generating Colony...</h2></div>
        <div class="modal-body" style="align-items: center; justify-content: center; padding: 60px 20px;">
            <div class="loading-spinner"></div>
            <div style="color: var(--text-dim); margin-top: 20px; text-align: center;">
                Creating backgrounds and generating names...
            </div>
        </div>
    `;
    window._colonyLoading = cs.overlay;

    clearInput();
    appendMessage(`> Colony "${result.colony_name}" — ${cs.roster.length} crew`, 'dim');
    sendResponse(cs.msg.id, result);
    window._colonySetup = null;
}

// ── Colony Ready (loading → roster) ────────────────────────

function renderColonyReady(msg) {
    window._colonyReadyMsg = msg;

    // Use existing loading modal or create new one
    let overlay = window._colonyLoading;
    let modal;

    if (overlay) {
        modal = overlay.querySelector('.modal-content');
    } else {
        overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        modal = document.createElement('div');
        modal.className = 'modal-content';
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    let html = `
        <div class="modal-header">
            <h2>Colony Roster</h2>
        </div>
        <div class="modal-body">
    `;

    for (const c of msg.characters) {
        // Experience stat bonuses display
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

        const titlePrefix = c.title ? `<span class="roster-card-title">${escapeHtml(c.title)}</span>` : '';
        const charIdx = msg.characters.indexOf(c);
        html += `
            <div class="roster-card">
                <div class="roster-card-header">
                    ${titlePrefix}
                    <div class="roster-card-name">${escapeHtml(c.name)}</div>
                    ${c.role ? `<div class="roster-card-role">${escapeHtml(c.role)}</div>` : ''}
                    <div class="roster-card-class">${capitalize(c.char_class)}</div>
                    <button class="btn-edit-char" onclick="editColonyReadyChar(${charIdx})" title="Edit">&#9998;</button>
                </div>
                <div class="roster-card-stats">
                    <div class="stat-chip"><span class="label">React</span><span class="val">${c.reactions}</span></div>
                    <div class="stat-chip"><span class="label">Speed</span><span class="val">${c.speed}"</span></div>
                    <div class="stat-chip"><span class="label">Combat</span><span class="val">+${c.combat_skill}</span></div>
                    <div class="stat-chip"><span class="label">Tough</span><span class="val">${c.toughness}</span></div>
                    <div class="stat-chip"><span class="label">Savvy</span><span class="val">+${c.savvy}</span></div>
                </div>
                ${bgSection}
                ${c.narrative ? `<div class="roster-card-bg">${escapeHtml(c.narrative)}</div>` : ''}
            </div>
        `;
    }

    html += `
            <div style="display: flex; justify-content: flex-end; padding-top: 8px;">
                <button class="btn btn-primary" id="cr-continue">Continue &#9654;</button>
            </div>
        </div>
    `;

    modal.innerHTML = html;

    document.getElementById('cr-continue').onclick = () => {
        overlay.remove();
        window._colonyLoading = null;
        window._colonyReadyMsg = null;
        clearInput();
        sendResponse(msg.id, true);
    };
}

function editColonyReadyChar(index) {
    const msg = window._colonyReadyMsg;
    if (!msg || !msg.characters[index]) return;
    const c = msg.characters[index];

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
            <button class="modal-close" id="crce-cancel">&#10005;</button>
        </div>
        <div class="modal-body">
            <div class="edit-form">
                <div class="form-row">
                    <label>Title <span style="color:var(--text-dim)">(optional)</span></label>
                    <input type="text" id="crce-title" value="${escapeHtml(c.title || '')}" placeholder="e.g. Sgt., Dr.">
                </div>
                <div class="form-row">
                    <label>Name</label>
                    <input type="text" id="crce-name" value="${escapeHtml(c.name)}">
                </div>
                <div class="form-row">
                    <label>Role <span style="color:var(--text-dim)">(optional)</span></label>
                    <input type="text" id="crce-role" value="${escapeHtml(c.role || '')}" placeholder="e.g. Lead researcher">
                </div>
                <div class="form-row">
                    <label>Background <span style="color:var(--text-dim)">(optional)</span></label>
                    <textarea id="crce-narrative" rows="4">${escapeHtml(c.narrative || '')}</textarea>
                </div>
                <div style="display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end;">
                    <button class="btn" id="crce-cancel2">Cancel</button>
                    <button class="btn btn-primary" id="crce-save">Save</button>
                </div>
            </div>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    document.getElementById('crce-save').onclick = () => {
        const newTitle = document.getElementById('crce-title').value.trim();
        const newName = document.getElementById('crce-name').value.trim();
        const newRole = document.getElementById('crce-role').value.trim();
        const newNarrative = document.getElementById('crce-narrative').value.trim();
        if (!newName) return;

        // Update local data and server
        const origName = c.name;
        c.title = newTitle;
        c.name = newName;
        c.role = newRole;
        c.narrative = newNarrative;

        if (window._ws && window._ws.readyState === 1) {
            window._ws.send(JSON.stringify({
                type: 'update_roster',
                character_name: origName,
                updates: { title: newTitle, name: newName, role: newRole, narrative: newNarrative },
            }));
        }

        overlay.remove();
        // Re-render the colony ready screen with updated data
        renderColonyReady(msg);
    };

    const close = () => overlay.remove();
    document.getElementById('crce-cancel').onclick = close;
    document.getElementById('crce-cancel2').onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };

    document.getElementById('crce-name').focus();
    document.getElementById('crce-name').select();
}

// ── Experience Screen ───────────────────────────────────────

function renderExperienceScreen(area, msg) {
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

    // --- XP Gained Rules Box ---
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

    // --- Character Cards (only those with 5+ XP) ---
    const advChars = msg.characters.filter(c => c.xp >= 5);
    if (advChars.length > 0) {
        html += '<div class="exp-roster-title">ELIGIBLE FOR ADVANCEMENT</div>';
    }
    html += '<div class="exp-roster">';
    for (const c of advChars) {
        html += `<div class="exp-char-card exp-can-advance" data-char-name="${escapeHtml(c.name)}">`;
        html += '<div class="exp-char-header">';
        if (c.title) html += `<span class="roster-card-title">${escapeHtml(c.title)}</span>`;
        html += `<span class="exp-char-name">${escapeHtml(c.name)}</span>`;
        if (c.role) html += `<span class="roster-card-role">${escapeHtml(c.role)}</span>`;
        html += `<span class="exp-char-class">${capitalize(c.char_class)}</span>`;
        html += '</div>';
        html += '<div class="roster-card-stats">';
        html += `<div class="stat-chip"><span class="label">React</span><span class="val">${c.reactions}</span></div>`;
        html += `<div class="stat-chip"><span class="label">Speed</span><span class="val">${c.speed}"</span></div>`;
        html += `<div class="stat-chip"><span class="label">Combat</span><span class="val">+${c.combat_skill}</span></div>`;
        html += `<div class="stat-chip"><span class="label">Tough</span><span class="val">${c.toughness}</span></div>`;
        html += `<div class="stat-chip"><span class="label">Savvy</span><span class="val">+${c.savvy}</span></div>`;
        html += `<div class="stat-chip exp-xp-chip exp-xp-ready"><span class="label">XP</span><span class="val">${c.xp}</span></div>`;
        html += `<div class="stat-chip"><span class="label">KP</span><span class="val">${c.kill_points}</span></div>`;
        html += '</div>';
        html += `<div class="exp-char-info">Status: <span style="color:var(--accent-green)">Ready</span>&nbsp;&nbsp;Loyalty: ${capitalize(c.loyalty)}</div>`;
        html += `<button class="btn btn-accent exp-advance-btn" data-char="${escapeHtml(c.name)}">Advancement (5 XP)</button>`;
        html += '</div>';
    }
    html += '</div>';

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
        openAdvancementModal(msg, msg.last_advancement.character, msg.last_advancement.description);
    }
}

function openAdvancementModal(msg, charName, resultDesc) {
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
    const classPart = `<span class="exp-char-class">${capitalize(char.char_class)}</span>`;

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
        html += `<div class="adv-result-banner">${escapeHtml(resultDesc)}</div>`;
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

    // Build apps-by-theory lookup
    const appsByTheory = {};
    for (const a of apps) {
        if (!appsByTheory[a.theory]) appsByTheory[a.theory] = {apps: [], cost: a.cost};
        appsByTheory[a.theory].apps.push(a);
    }

    // Theories - with applications inline (completed first)
    if (theories.length > 0) {
        const sortedTheories = [...theories].sort((a, b) => {
            const aComplete = (a.invested_rp || 0) >= (a.rp_cost || 0);
            const bComplete = (b.invested_rp || 0) >= (b.rp_cost || 0);
            if (aComplete && !bComplete) return -1;
            if (!aComplete && bComplete) return 1;
            return 0;
        });
        html += '<div class="rs-section-title">THEORIES</div>';
        html += '<div class="rs-theories">';
        for (const t of sortedTheories) {
            const invested = t.invested_rp || 0;
            const cost = t.rp_cost || 0;
            const remaining = cost - invested;
            const completed = invested >= cost;

            html += `<div class="rs-theory${completed ? ' rs-theory-completed' : ''}">`;
            html += `<div class="rs-theory-header">`;
            html += `<span class="rs-theory-name">${completed ? '&#10003; ' : ''}${escapeHtml(t.name)}</span>`;
            html += `<span class="rs-theory-rp">${completed ? invested + '/' + cost + ' RP' : cost + ' RP'}</span>`;
            html += `</div>`;
            // Applications list
            if (t.applications && t.applications.length > 0) {
                html += '<div class="tt-apps">';
                for (const app of t.applications) {
                    const appCls = app.unlocked ? 'tt-app-researched' : 'tt-app-locked';
                    const typeIcons = {building: '&#9632;', weapon: '&#9876;', bonus: '&#9733;', milestone: '&#9670;', grunt_upgrade: '&#9650;'};
                    const typeIcon = typeIcons[app.type] || '&#8226;';
                    html += `<div class="tt-app ${appCls}">`;
                    html += `<span class="tt-app-icon">${typeIcon}</span>`;
                    html += `<span class="tt-app-name">${escapeHtml(app.name)}</span>`;
                    if (app.description) html += `<span class="tt-app-desc">${escapeHtml(app.description)}</span>`;
                    html += '</div>';
                }
                html += '</div>';
            }
            // Action buttons
            html += '<div class="rs-theory-actions">';
            if (!completed && remaining > 0) {
                const canBuy = rp >= remaining;
                html += `<button class="btn btn-sm btn-accent rs-invest-btn" data-theory="${escapeHtml(t.id)}" data-amount="${remaining}"${canBuy ? '' : ' disabled'}>Complete Theory (${remaining} RP)</button>`;
            }
            // Unlock application button (if theory completed and has undiscovered apps)
            const theoryApps = appsByTheory[t.name];
            if (completed && theoryApps && theoryApps.apps.length > 0) {
                const canAfford = rp >= theoryApps.cost;
                html += `<button class="btn btn-sm rs-app-btn" data-theory="${escapeHtml(t.name)}"${canAfford ? '' : ' disabled'}>Unlock Application (${theoryApps.cost} RP)</button>`;
            }
            html += '</div>';
            html += `</div>`;
        }
        html += '</div>';
    }

    // Bio-analysis — per-specimen
    const specimens = msg.bio_specimens || [];
    const unanalyzed = specimens.filter(s => !s.analyzed);
    if (specimens.length > 0) {
        html += '<div class="rs-section-title">BIO-ANALYSIS</div>';
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
