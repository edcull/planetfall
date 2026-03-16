/**
 * Planetfall Web UI — Combat input renderers.
 *
 * Handles weapon selection, action selection, deployment, movement,
 * zone selection, and deploy-zone inputs during combat.
 *
 * Depends on: app.js (sendResponse, appendMessage, escapeHtml),
 *             components.js (setBetweenTurnsState, etc.),
 *             battlefield.js (enableBattlefield*, disableBattlefield*),
 *             input.js (clearInput, appendFigureProfile, buildFigureProfileHtml)
 */

// ── Global state for shoot targets during action selection ──
let _activeShootTargets = [];
let _activeShootResponseId = null;

function clearShootTargets() {
    _activeShootTargets = [];
    _activeShootResponseId = null;
}

// ── Weapon Select (Lock and Load — weapon cards with stats) ──

function renderWeaponSelect(area, msg) {
    area.innerHTML = '';

    if (msg.active_figure) appendFigureProfile(area, msg.active_figure);

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

function renderActionSelect(area, msg) {
    area.innerHTML = '';

    // Store shoot targets globally for the info panel
    _activeShootTargets = msg.shoot_targets || [];
    _activeShootResponseId = msg.id;

    if (msg.active_figure) appendFigureProfile(area, msg.active_figure);

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

// ── Deployment (Lock and Load) ──────────────────────────────

function renderDeployment(area, msg) {
    area.innerHTML = '';

    const available = msg.available || [];
    const maxSlots = msg.max_slots || 8;
    const gruntCount = msg.grunt_count || 0;
    const botAvailable = msg.bot_available || false;
    const charClasses = msg.char_classes || {};
    const charProfiles = msg.char_profiles || {};

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
            const p = charProfiles[name];
            let cardHtml = `<span class="deploy-name">${escapeHtml(name)}</span>`;
            if (cls) cardHtml += `<span class="deploy-class">${escapeHtml(cls)}</span>`;
            if (p) {
                cardHtml += '<div class="deploy-stats">';
                cardHtml += `<span class="stat-chip sm"><span class="label">Spd</span><span class="val">${p.speed}"</span></span>`;
                cardHtml += `<span class="stat-chip sm"><span class="label">React</span><span class="val">${p.reactions}</span></span>`;
                cardHtml += `<span class="stat-chip sm"><span class="label">CS</span><span class="val">+${p.combat_skill}</span></span>`;
                cardHtml += `<span class="stat-chip sm"><span class="label">T</span><span class="val">${p.toughness}</span></span>`;
                cardHtml += `<span class="stat-chip sm"><span class="label">Sav</span><span class="val">+${p.savvy}</span></span>`;
                cardHtml += '</div>';
                if (p.equipment && p.equipment.length) {
                    cardHtml += `<div class="deploy-equip">${p.equipment.map(e => escapeHtml(e)).join(', ')}</div>`;
                }
            }
            card.innerHTML = cardHtml;
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

// ── Lock and Load (combined deployment + weapon loadout) ────

function renderLockAndLoad(area, msg) {
    area.innerHTML = '';

    const available = msg.available || [];
    const maxSlots = msg.max_slots || 8;
    const gruntCount = msg.grunt_count || 0;
    const botAvailable = msg.bot_available || false;
    const charProfiles = msg.char_profiles || {};
    const weapons = msg.weapons || [];
    const compat = msg.compatibility || {};
    const forcedGrunts = msg.forced_grunts != null ? msg.forced_grunts : null;

    // State
    const selected = new Set();
    let grunts = forcedGrunts != null ? Math.min(forcedGrunts, gruntCount) : 0;
    let bot = false;
    let civilians = 0;
    const weaponLoadout = {};  // key -> weapon name
    let draggingWeapon = null; // weapon name currently being dragged
    // Fireteam LMG: which grunt index (global) has the LMG in each fireteam
    // lmgSlot[teamIdx] = global grunt index, or -1 for none
    const lmgSlot = { 0: -1, 1: -1 };

    function getFireteams() {
        if (grunts <= 0) return [];
        if (grunts <= 4) return [{ name: 'Fireteam Alpha', start: 0, size: grunts, idx: 0 }];
        const half = Math.floor(grunts / 2);
        return [
            { name: 'Fireteam Alpha', start: 0, size: half, idx: 0 },
            { name: 'Fireteam Bravo', start: half, size: grunts - half, idx: 1 },
        ];
    }

    function getRemaining() {
        // Forced grunts don't count against character slots
        const gruntSlots = forcedGrunts != null ? 0 : grunts;
        return maxSlots - selected.size - gruntSlots - (bot ? 1 : 0) - civilians;
    }

    function canUse(charClass, weaponName) {
        const list = compat[charClass];
        return list && list.includes(weaponName);
    }

    function buildStatChips(p) {
        return `<div class="deploy-stats">
            <span class="stat-chip sm"><span class="label">Spd</span><span class="val">${p.speed || 0}"</span></span>
            <span class="stat-chip sm"><span class="label">React</span><span class="val">${p.reactions || 0}</span></span>
            <span class="stat-chip sm"><span class="label">CS</span><span class="val">+${p.combat_skill || 0}</span></span>
            <span class="stat-chip sm"><span class="label">T</span><span class="val">${p.toughness || 0}</span></span>
            <span class="stat-chip sm"><span class="label">Sav</span><span class="val">+${p.savvy || 0}</span></span>
        </div>`;
    }

    // Map class to display label and color
    const classLabels = {
        civilian: 'Standard', scientist: 'Scientist', scout: 'Scout',
        trooper: 'Trooper', grunt: 'Grunt',
    };
    const classColors = {
        civilian: 'var(--text-secondary)', scientist: 'var(--accent-magenta)',
        scout: 'var(--accent-green)', trooper: 'var(--accent-red)',
        grunt: 'var(--accent-yellow)',
    };

    function makeDropTarget(el, key, charClass, isActive) {
        el.addEventListener('dragover', (e) => {
            if (!isActive()) return;
            const wpn = draggingWeapon;
            if (!wpn) return;
            e.preventDefault();
            el.classList.remove('drag-over', 'drag-over-bad');
            if (canUse(charClass, wpn)) {
                el.classList.add('drag-over');
            } else {
                el.classList.add('drag-over-bad');
            }
        });
        el.addEventListener('dragleave', () => {
            el.classList.remove('drag-over', 'drag-over-bad');
        });
        el.addEventListener('drop', (e) => {
            e.preventDefault();
            el.classList.remove('drag-over', 'drag-over-bad');
            if (!isActive()) return;
            const weaponName = e.dataTransfer.getData('text/plain');
            if (canUse(charClass, weaponName)) {
                weaponLoadout[key] = weaponName;
                render();
            }
        });
    }

    function render() {
        const existing = document.getElementById('lal-modal');
        if (existing) existing.remove();

        const gruntSlots = forcedGrunts != null ? 0 : grunts;
        const totalDeployed = selected.size + gruntSlots + (bot ? 1 : 0) + civilians;
        const gruntNote = forcedGrunts != null ? ` + ${grunts} grunts` : '';

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'lal-modal';

        const modal = document.createElement('div');
        modal.className = 'modal-content lal-modal';

        // Header
        const header = document.createElement('div');
        header.className = 'modal-header';
        header.innerHTML = `<h2>Lock and Load</h2>
            <span class="lal-slots">${totalDeployed} / ${maxSlots} slots${gruntNote}</span>`;
        modal.appendChild(header);

        const body = document.createElement('div');
        body.className = 'modal-body lal-body';

        // ─── TOP: Crew roster ───
        const crewSection = document.createElement('div');
        crewSection.className = 'lal-crew-section';

        crewSection.innerHTML = '<h3 class="lal-section-title">Available Crew</h3>';
        const grid = document.createElement('div');
        grid.className = 'lal-roster-grid';

        for (const name of available) {
            const p = charProfiles[name] || {};
            const isSelected = selected.has(name);
            const card = document.createElement('div');
            card.className = 'lal-char-card' + (isSelected ? ' selected' : '');
            card.dataset.name = name;
            card.dataset.charClass = p.char_class || 'civilian';

            let equipHtml = '';
            if (p.equipment && p.equipment.length) {
                equipHtml = `<div class="lal-char-equip">${p.equipment.map(e => escapeHtml(e)).join(', ')}</div>`;
            }

            let weaponHtml = '';
            if (isSelected && weaponLoadout[name]) {
                weaponHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag">${escapeHtml(weaponLoadout[name])}</span></div>`;
            } else if (isSelected) {
                weaponHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag empty">Drop weapon here</span></div>`;
            }

            card.innerHTML = `
                <div class="lal-char-header">
                    <span class="lal-char-name">${escapeHtml(name)}</span>
                    <span class="lal-char-class">${escapeHtml((p.char_class || '').charAt(0).toUpperCase() + (p.char_class || '').slice(1))}</span>
                </div>
                ${buildStatChips(p)}
                ${equipHtml}
                ${weaponHtml}
            `;

            card.addEventListener('click', () => {
                if (isSelected) {
                    selected.delete(name);
                    delete weaponLoadout[name];
                } else if (getRemaining() > 0) {
                    selected.add(name);
                }
                render();
            });
            makeDropTarget(card, name, p.char_class || 'civilian', () => isSelected);
            grid.appendChild(card);
        }
        crewSection.appendChild(grid);

        // Support units controls row
        const supportRow = document.createElement('div');
        supportRow.className = 'lal-support-row';

        // Grunts counter
        if (gruntCount > 0 || forcedGrunts != null) {
            const gruntDiv = document.createElement('div');
            gruntDiv.className = 'lal-support-unit';
            if (forcedGrunts != null) {
                // Forced grunts: locked, not adjustable
                gruntDiv.innerHTML = `
                    <span class="lal-support-label">Grunts <span class="lal-support-avail">(fireteam — required)</span></span>
                    <div class="deploy-counter">
                        <span class="counter-val">${grunts}</span>
                    </div>
                `;
            } else {
                const maxGrunts = Math.min(gruntCount, getRemaining() + grunts);
                gruntDiv.innerHTML = `
                    <span class="lal-support-label">Grunts <span class="lal-support-avail">(${gruntCount} avail)</span></span>
                    <div class="deploy-counter">
                        <button class="btn-counter">−</button>
                        <span class="counter-val">${grunts}</span>
                        <button class="btn-counter">+</button>
                    </div>
                `;
                const btns = gruntDiv.querySelectorAll('.btn-counter');
                btns[0].onclick = () => { if (grunts > 0) { grunts--; render(); } };
                btns[1].onclick = () => { if (grunts < maxGrunts && getRemaining() > 0) { grunts++; render(); } };
            }
            supportRow.appendChild(gruntDiv);
        }

        // Bot toggle
        if (botAvailable) {
            const botDiv = document.createElement('div');
            botDiv.className = 'lal-support-unit';
            botDiv.innerHTML = `
                <span class="lal-support-label">Security Bot</span>
                <button class="btn-toggle ${bot ? 'active' : ''}">${bot ? 'Deployed' : 'Available'}</button>
            `;
            botDiv.querySelector('.btn-toggle').onclick = () => {
                if (bot) { bot = false; delete weaponLoadout['_bot']; }
                else if (getRemaining() > 0) { bot = true; }
                render();
            };
            supportRow.appendChild(botDiv);
        }

        // Civilians counter
        const civDiv = document.createElement('div');
        civDiv.className = 'lal-support-unit';
        civDiv.innerHTML = `
            <span class="lal-support-label">Civilian Volunteers</span>
            <div class="deploy-counter">
                <button class="btn-counter">−</button>
                <span class="counter-val">${civilians}</span>
                <button class="btn-counter">+</button>
            </div>
        `;
        const civBtns = civDiv.querySelectorAll('.btn-counter');
        civBtns[0].onclick = () => { if (civilians > 0) { civilians--; render(); } };
        civBtns[1].onclick = () => { if (getRemaining() > 0) { civilians++; render(); } };
        supportRow.appendChild(civDiv);

        crewSection.appendChild(supportRow);

        // Support unit cards (deployed grunts in fireteams, bot, civilians)
        const gruntUpgrades = msg.grunt_upgrades || [];
        const gruntProfile = { speed: 4, reactions: 2, combat_skill: 0, toughness: 3, savvy: 0 };
        // Apply stat-modifying upgrades to the displayed profile
        if (gruntUpgrades.includes('survival_kit')) gruntProfile.toughness += 1;
        const GRUNT_PROFILE = gruntProfile;
        const BOT_PROFILE   = { speed: 4, reactions: 2, combat_skill: 0, toughness: 4, savvy: 0 };
        const CIVVY_PROFILE = { speed: 4, reactions: 1, combat_skill: 0, toughness: 3, savvy: 0 };

        // Grunt fireteams
        if (grunts > 0) {
            const fireteams = getFireteams();
            for (const team of fireteams) {
                const teamDiv = document.createElement('div');
                teamDiv.className = 'lal-fireteam';

                const teamLabel = document.createElement('div');
                teamLabel.className = 'lal-fireteam-label';
                teamLabel.textContent = `${team.name} (${team.size})`;
                teamDiv.appendChild(teamLabel);

                const teamGrid = document.createElement('div');
                teamGrid.className = 'lal-roster-grid';

                // Clean up LMG slot if it's out of range
                if (lmgSlot[team.idx] >= team.start + team.size || lmgSlot[team.idx] < team.start) {
                    lmgSlot[team.idx] = -1;
                }

                // LMG requires fireteam of at least 3
                const canLmg = team.size >= 3;
                if (!canLmg) {
                    lmgSlot[team.idx] = -1;
                } else if (lmgSlot[team.idx] < 0) {
                    // Auto-assign LMG to last grunt when fireteam reaches 3
                    lmgSlot[team.idx] = team.start + team.size - 1;
                }

                for (let gi = team.start; gi < team.start + team.size; gi++) {
                    const hasLmg = lmgSlot[team.idx] === gi;
                    const weaponName = hasLmg ? 'Light Machine Gun' : 'Infantry Rifle';
                    const gruntCard = document.createElement('div');
                    gruntCard.className = 'lal-char-card selected';
                    gruntCard.dataset.charClass = 'grunt';

                    // Build upgrade tags
                    const UPGRADE_LABELS = {
                        adapted_armor: 'Armor 6+',
                        survival_kit: 'Tough +1',
                        side_arms: 'Side Arms',
                        sergeant_weaponry: 'Sgt Weapon',
                        sharpshooter_sight: 'Sharpshooter',
                        ammo_packs: 'Ammo Packs',
                    };
                    let upgradeHtml = '';
                    if (gruntUpgrades.length > 0) {
                        const tags = gruntUpgrades
                            .map(u => UPGRADE_LABELS[u] || u)
                            .map(label => `<span class="lal-upgrade-tag">${escapeHtml(label)}</span>`)
                            .join('');
                        upgradeHtml = `<div class="lal-char-upgrades">${tags}</div>`;
                    }

                    gruntCard.innerHTML = `
                        <div class="lal-char-header">
                            <span class="lal-char-name">Grunt ${gi + 1}</span>
                            <span class="lal-char-class">Grunt</span>
                        </div>
                        ${buildStatChips(GRUNT_PROFILE)}
                        <div class="lal-char-weapon"><span class="lal-weapon-tag${hasLmg ? ' lal-tag-lmg' : ''}">${escapeHtml(weaponName)}</span></div>
                        ${upgradeHtml}
                    `;

                    // Click to toggle LMG (one per fireteam, requires 3+)
                    if (canLmg) {
                        const capturedGi = gi;
                        const capturedTeamIdx = team.idx;
                        gruntCard.addEventListener('click', () => {
                            if (lmgSlot[capturedTeamIdx] === capturedGi) {
                                lmgSlot[capturedTeamIdx] = -1;
                            } else {
                                lmgSlot[capturedTeamIdx] = capturedGi;
                            }
                            render();
                        });
                    }

                    teamGrid.appendChild(gruntCard);
                }

                teamDiv.appendChild(teamGrid);
                crewSection.appendChild(teamDiv);
            }
        }

        // Bot + Civilian cards
        if (bot || civilians > 0) {
            const supportGrid = document.createElement('div');
            supportGrid.className = 'lal-roster-grid';

            // Bot card
            if (bot) {
                const botCard = document.createElement('div');
                botCard.className = 'lal-char-card selected';
                botCard.dataset.charClass = 'bot';

                let wpnHtml = '';
                if (weaponLoadout['_bot']) {
                    wpnHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag">${escapeHtml(weaponLoadout['_bot'])}</span></div>`;
                } else {
                    wpnHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag empty">Drop weapon here</span></div>`;
                }

                botCard.innerHTML = `
                    <div class="lal-char-header">
                        <span class="lal-char-name">Security Bot</span>
                        <span class="lal-char-class">Bot</span>
                    </div>
                    ${buildStatChips(BOT_PROFILE)}
                    ${wpnHtml}
                `;
                makeDropTarget(botCard, '_bot', 'bot', () => true);
                supportGrid.appendChild(botCard);
            }

            // Civilian cards
            for (let ci = 0; ci < civilians; ci++) {
                const key = `_civ${ci}`;
                const civCard = document.createElement('div');
                civCard.className = 'lal-char-card selected';
                civCard.dataset.charClass = 'civvy';

                let wpnHtml = '';
                if (weaponLoadout[key]) {
                    wpnHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag">${escapeHtml(weaponLoadout[key])}</span></div>`;
                } else {
                    wpnHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag empty">Drop weapon here</span></div>`;
                }

                civCard.innerHTML = `
                    <div class="lal-char-header">
                        <span class="lal-char-name">Civilian ${ci + 1}</span>
                        <span class="lal-char-class">Civvy</span>
                    </div>
                    ${buildStatChips(CIVVY_PROFILE)}
                    ${wpnHtml}
                `;
                makeDropTarget(civCard, key, 'civvy', () => true);
                supportGrid.appendChild(civCard);
            }

            crewSection.appendChild(supportGrid);
        }

        body.appendChild(crewSection);

        // ─── BOTTOM: Arsenal (single flat list) ───
        const arsenalSection = document.createElement('div');
        arsenalSection.className = 'lal-arsenal-section';

        arsenalSection.innerHTML = '<h3 class="lal-section-title">Arsenal</h3>';

        const wpnGrid = document.createElement('div');
        wpnGrid.className = 'lal-wpn-grid';

        for (const w of weapons) {
            const card = document.createElement('div');
            let tierClass = '';
            if (w.tier === 'tier_1') tierClass = ' lal-wpn-tier1';
            if (w.tier === 'tier_2') tierClass = ' lal-wpn-tier2';
            card.className = 'lal-wpn-card' + tierClass;
            card.draggable = true;
            card.dataset.weaponName = w.name;
            card.dataset.weaponClass = w.weapon_class;

            let statsHtml = '';
            if (w.range > 0) statsHtml += `<span class="stat-chip sm"><span class="label">Rng</span><span class="val">${w.range}"</span></span>`;
            else statsHtml += `<span class="stat-chip sm"><span class="label">Rng</span><span class="val">Melee</span></span>`;
            statsHtml += `<span class="stat-chip sm"><span class="label">Shots</span><span class="val">${w.shots}</span></span>`;
            statsHtml += `<span class="stat-chip sm"><span class="label">Dmg</span><span class="val">+${w.damage || 0}</span></span>`;

            let traitsHtml = '';
            if (w.traits && w.traits.length) {
                const tips = (typeof WEAPON_TRAIT_TIPS !== 'undefined') ? WEAPON_TRAIT_TIPS : {};
                const traitSpans = w.traits.map(t => {
                    const label = t.replace(/_/g, ' ');
                    const tip = tips[label] || '';
                    return `<span class="wpn-trait${tip ? ' has-tooltip' : ''}" ${tip ? `data-tooltip="${escapeHtml(tip)}"` : ''}>${escapeHtml(label)}</span>`;
                }).join('');
                traitsHtml = `<div class="lal-wpn-traits">${traitSpans}</div>`;
            }

            const clsLabel = classLabels[w.weapon_class] || w.weapon_class;
            const clsColor = classColors[w.weapon_class] || 'var(--text-dim)';

            card.innerHTML = `
                <div class="lal-wpn-header">
                    <span class="lal-wpn-name">${escapeHtml(w.name)}</span>
                    <span class="lal-wpn-class-tag" style="color:${clsColor}">${escapeHtml(clsLabel)}</span>
                </div>
                <div class="deploy-stats">${statsHtml}</div>
                ${traitsHtml}
            `;

            card.addEventListener('dragstart', (e) => {
                draggingWeapon = w.name;
                e.dataTransfer.setData('text/plain', w.name);
                e.dataTransfer.effectAllowed = 'copy';
                card.classList.add('dragging');
                // Grey out incompatible crew cards
                overlay.querySelectorAll('.lal-char-card.selected').forEach(cc => {
                    const cls = cc.dataset.charClass;
                    if (!canUse(cls, w.name)) {
                        cc.classList.add('incompatible');
                    }
                });
            });
            card.addEventListener('dragend', () => {
                draggingWeapon = null;
                card.classList.remove('dragging');
                overlay.querySelectorAll('.lal-char-card.incompatible').forEach(cc => {
                    cc.classList.remove('incompatible');
                });
            });

            // Click to auto-assign
            card.addEventListener('click', () => {
                for (const name of selected) {
                    const p = charProfiles[name] || {};
                    const cls = p.char_class || 'civilian';
                    if (canUse(cls, w.name) && !weaponLoadout[name]) {
                        weaponLoadout[name] = w.name;
                        render();
                        return;
                    }
                }
            });

            wpnGrid.appendChild(card);
        }
        arsenalSection.appendChild(wpnGrid);
        body.appendChild(arsenalSection);

        modal.appendChild(body);

        // Footer
        const footer = document.createElement('div');
        footer.className = 'modal-footer';

        const deployBtn = document.createElement('button');
        deployBtn.className = 'btn btn-primary';
        deployBtn.textContent = `Deploy Squad (${totalDeployed})`;
        deployBtn.disabled = selected.size === 0;
        deployBtn.onclick = () => {
            const finalLoadout = {};
            for (const name of selected) {
                if (weaponLoadout[name]) finalLoadout[name] = weaponLoadout[name];
            }
            // Grunt LMG assignments per fireteam
            const fireteams = getFireteams();
            for (const team of fireteams) {
                if (lmgSlot[team.idx] >= 0) {
                    finalLoadout[`_lmg_team${team.idx}`] = String(lmgSlot[team.idx]);
                }
            }
            if (bot && weaponLoadout['_bot']) {
                finalLoadout['_bot'] = weaponLoadout['_bot'];
            }
            for (let ci = 0; ci < civilians; ci++) {
                const key = `_civ${ci}`;
                if (weaponLoadout[key]) finalLoadout[key] = weaponLoadout[key];
            }

            const result = {
                characters: Array.from(selected),
                grunts: grunts,
                bot: bot,
                civilians: civilians,
                weapon_loadout: finalLoadout,
            };
            overlay.remove();
            clearInput();
            appendMessage(`> Deployed ${selected.size} characters, ${grunts} grunts${bot ? ', bot' : ''}${civilians ? `, ${civilians} civilian${civilians>1?'s':''}` : ''}`, 'dim');
            sendResponse(msg.id, result);
        };
        footer.appendChild(deployBtn);
        modal.appendChild(footer);

        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    render();
}

// ── Movement (click-on-map) ─────────────────────────────────

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

    // Cancel: go back to figure selection
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'choice-item choice-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.onclick = () => {
        disableBattlefieldMovementSelect();
        clearInput();
        sendResponse(msg.id, { type: 'cancel' });
    };
    btnRow.appendChild(cancelBtn);

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

// ── Zone Select (click-on-map) ──────────────────────────────

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

// ── Deploy Zone (click-on-map, single figure — legacy) ──────

function renderDeployZone(area, msg) {
    area.innerHTML = '';

    if (msg.active_figure) appendFigureProfile(area, msg.active_figure);

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

// ── Deploy Zones Batch (all figures at once with cards) ─────

function renderDeployZonesBatch(area, msg) {
    area.innerHTML = '';

    const figures = msg.figures || [];
    const validZones = msg.valid_zones || [];
    const maxPerZone = msg.max_per_zone || 2;
    const sameZone = msg.same_zone || false;  // scouting/science: all in one zone

    // State: placements[name] = {row, col} or null
    const placements = {};
    // Track zone occupancy from placements
    let selectedFigure = null; // name of figure currently being placed

    function zoneKey(r, c) { return `${r},${c}`; }

    function getZoneCount(r, c) {
        const key = zoneKey(r, c);
        let count = 0;
        // Count existing capacity used (from valid_zones capacity)
        const vz = validZones.find(z => z.row === r && z.col === c);
        const baseUsed = vz ? (maxPerZone - vz.capacity) : 0;
        count += baseUsed;
        // Count our placements
        for (const name in placements) {
            const p = placements[name];
            if (p && p.row === r && p.col === c) count++;
        }
        return count;
    }

    function zoneHasRoom(r, c) {
        if (getZoneCount(r, c) >= maxPerZone) return false;
        // Same-zone constraint: once one figure is placed, others must go there
        if (sameZone) {
            const existing = Object.values(placements).find(p => p);
            if (existing && (existing.row !== r || existing.col !== c)) return false;
        }
        return true;
    }

    function allPlaced() {
        return figures.every(f => placements[f.name]);
    }

    function render() {
        area.innerHTML = '';

        // Prompt
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        if (selectedFigure) {
            prompt.innerHTML = `Deploy <strong>${escapeHtml(selectedFigure)}</strong> — <span style="color: var(--text-dim);">click a highlighted zone</span>`;
        } else {
            prompt.innerHTML = `Select a figure to deploy <span style="color: var(--text-dim);">— then click a zone on the map</span>`;
        }
        area.appendChild(prompt);

        // Figure cards
        const grid = document.createElement('div');
        grid.className = 'lal-roster-grid';

        for (const f of figures) {
            const card = document.createElement('div');
            const isPlaced = !!placements[f.name];
            const isSelected = selectedFigure === f.name;
            card.className = 'lal-char-card deploy-fig-card'
                + (isSelected ? ' selected' : '')
                + (isPlaced ? ' deployed' : '');

            let placementHtml = '';
            if (isPlaced) {
                const p = placements[f.name];
                placementHtml = `<div class="lal-char-weapon"><span class="lal-weapon-tag">Zone (${p.row},${p.col})</span></div>`;
            }

            let weaponHtml = '';
            if (f.weapon_name && f.weapon_name !== 'Unarmed') {
                weaponHtml = `<div class="lal-char-equip">${escapeHtml(f.weapon_name)}</div>`;
            }

            card.innerHTML = `
                <div class="lal-char-header">
                    <span class="lal-char-name">${escapeHtml(f.name)}</span>
                    <span class="lal-char-class">${escapeHtml(f.char_class || '')}</span>
                </div>
                <div class="deploy-stats">
                    <span class="stat-chip sm"><span class="label">Spd</span><span class="val">${f.speed}"</span></span>
                    <span class="stat-chip sm"><span class="label">React</span><span class="val">${f.reactions}</span></span>
                    <span class="stat-chip sm"><span class="label">CS</span><span class="val">+${f.combat_skill}</span></span>
                    <span class="stat-chip sm"><span class="label">T</span><span class="val">${f.toughness}</span></span>
                    <span class="stat-chip sm"><span class="label">Sav</span><span class="val">+${f.savvy}</span></span>
                </div>
                ${weaponHtml}
                ${placementHtml}
            `;

            card.onclick = () => {
                if (isSelected) {
                    // Deselect
                    selectedFigure = null;
                    disableBattlefieldDeploySelect();
                } else {
                    // Select for placement (clear previous placement if re-placing)
                    selectedFigure = f.name;
                    activateZoneSelect();
                }
                render();
            };

            grid.appendChild(card);
        }
        area.appendChild(grid);

        // Confirm button
        const btnRow = document.createElement('div');
        btnRow.style.marginTop = '8px';
        btnRow.style.display = 'flex';
        btnRow.style.gap = '8px';

        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'btn btn-primary';
        const placedCount = figures.filter(f => placements[f.name]).length;
        confirmBtn.textContent = `Confirm Deployment (${placedCount}/${figures.length})`;
        confirmBtn.disabled = !allPlaced();
        confirmBtn.onclick = () => {
            disableBattlefieldDeploySelect();
            clearInput();
            const desc = figures.map(f => {
                const p = placements[f.name];
                return `${f.name} → (${p.row},${p.col})`;
            }).join(', ');
            appendMessage(`> Deployed: ${desc}`, 'dim');
            sendResponse(msg.id, { placements });
        };
        btnRow.appendChild(confirmBtn);
        area.appendChild(btnRow);
    }

    function updateMapWithPlacements() {
        if (!_bfData) return;
        // Remove any previously injected deploy-preview figures
        _bfData.figures = _bfData.figures.filter(f => !f._deployPreview);
        // Add preview figures for each placement
        for (const f of figures) {
            const p = placements[f.name];
            if (!p) continue;
            // Name initials for label
            const parts = f.name.split(/\s+/);
            const abbrev = parts.length >= 2
                ? (parts[0][0] + parts[1][0]).toUpperCase()
                : f.name.slice(0, 2).toUpperCase();
            _bfData.figures.push({
                name: f.name,
                label: abbrev,
                side: 'player',
                zone: [p.row, p.col],
                status: 'active',
                color: 'player',
                is_contact: false,
                is_active: false,
                is_highlighted: false,
                weapon: f.weapon_name || '',
                char_class: f.char_class || '',
                speed: f.speed,
                toughness: f.toughness,
                combat_skill: f.combat_skill,
                stun_markers: 0,
                _deployPreview: true,
            });
        }
        renderBattlefield(_bfData);
    }

    function activateZoneSelect() {
        // Filter valid zones to those with room
        const available = validZones.filter(z => {
            // If this figure is already in this zone, it still has room (we'd be re-placing)
            const currentPlacement = placements[selectedFigure];
            if (currentPlacement && currentPlacement.row === z.row && currentPlacement.col === z.col) return true;
            return zoneHasRoom(z.row, z.col);
        });

        enableBattlefieldDeploySelect(available, (zone) => {
            if (!selectedFigure) return;
            // Remove old placement if re-placing
            placements[selectedFigure] = { row: zone.row, col: zone.col };
            // Auto-advance to next unplaced figure
            const nextUnplaced = figures.find(f => !placements[f.name]);
            if (nextUnplaced) {
                selectedFigure = nextUnplaced.name;
                activateZoneSelect();
            } else {
                selectedFigure = null;
                disableBattlefieldDeploySelect();
            }
            updateMapWithPlacements();
            render();
        });
    }

    // Auto-select first figure
    selectedFigure = figures.length > 0 ? figures[0].name : null;
    render();
    if (selectedFigure) activateZoneSelect();
}

// ── Figure Select (activate which figure — card-based) ──

function renderFigureSelect(area, msg) {
    area.innerHTML = '';

    const figures = msg.figures || [];

    if (msg.message) {
        const prompt = document.createElement('div');
        prompt.className = 'input-prompt';
        prompt.textContent = msg.message;
        area.appendChild(prompt);
    }

    const grid = document.createElement('div');
    grid.className = 'reaction-card-grid';

    for (const fig of figures) {
        const card = document.createElement('div');
        card.className = 'reaction-card fig-select-card';

        let headerHtml = `<div class="reaction-card-header">
            <span class="reaction-card-name">${escapeHtml(fig.name)}</span>`;
        if (fig.char_class) {
            headerHtml += `<span class="reaction-card-class">${escapeHtml(fig.char_class)}</span>`;
        }
        headerHtml += '</div>';

        let statsHtml = '<div class="reaction-card-stats">';
        if (fig.speed !== undefined) {
            statsHtml += `<span class="stat-chip sm"><span class="label">Spd</span><span class="val">${fig.speed}"</span></span>`;
        }
        if (fig.combat_skill !== undefined) {
            statsHtml += `<span class="stat-chip sm"><span class="label">CS</span><span class="val">+${fig.combat_skill}</span></span>`;
        }
        if (fig.toughness !== undefined) {
            statsHtml += `<span class="stat-chip sm"><span class="label">T</span><span class="val">${fig.toughness}</span></span>`;
        }
        statsHtml += '</div>';

        let weaponHtml = '';
        if (fig.weapon) {
            weaponHtml = `<div class="reaction-card-weapon">${escapeHtml(fig.weapon)}</div>`;
        }

        card.innerHTML = headerHtml + statsHtml + weaponHtml;

        card.onclick = () => {
            clearInput();
            appendMessage(`> ${fig.name}`, 'dim');
            sendResponse(msg.id, fig.name);
        };

        grid.appendChild(card);
    }

    area.appendChild(grid);

    // Focus first card
    const first = grid.querySelector('.reaction-card');
    if (first) first.focus();
}
