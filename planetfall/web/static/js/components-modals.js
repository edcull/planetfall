/**
 * Planetfall Web UI — Modal opener functions.
 *
 * Provides: openRosterModal, openResearchModal, openArmoryModal, openBuildingsModal,
 * openAncientSignsModal, openMilestonesModal, openConditionsModal, openLifeformsModal,
 * openEnemiesModal, openAugmentationsModal, openArtifactsModal, openCalamitiesModal,
 * openMoraleModal, openRosterCharEdit, openColonyLog, openColonyLogModal,
 * and their render/cache functions + helpers.
 *
 * Depends on: components.js (openModal, escapeHtml, capitalize, _lastColonyData, _lastRosterData)
 */

// ── Roster Card Builder (shared) ────────────────────────────

/**
 * Build HTML for a single roster character card.
 * @param {Object} c - Character data object
 * @param {Object} [opts] - Options
 * @param {boolean} [opts.showEdit] - Show edit button (default true)
 * @param {boolean} [opts.highlightXp] - Highlight XP chip when > 4 (default false)
 * @param {boolean} [opts.compact] - Hide background/narrative (default false)
 * @param {string}  [opts.extraHtml] - Extra HTML appended inside the card
 */
function buildRosterCardHtml(c, opts = {}) {
    const showEdit = opts.showEdit !== false;
    const highlightXp = opts.highlightXp || false;
    const compact = opts.compact || false;

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
    const xpHighlight = (highlightXp && c.xp > 4) ? ' exp-xp-chip exp-xp-ready' : '';

    let html = `
        <div class="roster-card${isSickBay ? ' roster-card-sick' : ''}" data-char-name="${safeName}">
            <div class="roster-card-header">
                ${titlePrefix}
                <div class="roster-card-name">${safeName}</div>
                ${c.role ? `<div class="roster-card-role">${escapeHtml(c.role)}</div>` : ''}
                <div class="roster-card-class">${capitalize(c.char_class)}${c.level != null ? ' ' + c.level : ''}</div>
                ${showEdit ? `<button class="btn-edit-char" onclick="openRosterCharEdit(${JSON.stringify(c.name).replace(/"/g, '&quot;')})" title="Edit">&#9998;</button>` : ''}
            </div>
            <div class="roster-card-stats">
                <div class="stat-chip"><span class="label">React</span><span class="val">${c.reactions}</span></div>
                <div class="stat-chip"><span class="label">Speed</span><span class="val">${c.speed}"</span></div>
                <div class="stat-chip"><span class="label">Combat</span><span class="val">+${c.combat_skill}</span></div>
                <div class="stat-chip"><span class="label">Tough</span><span class="val">${c.toughness}</span></div>
                <div class="stat-chip"><span class="label">Savvy</span><span class="val">+${c.savvy}</span></div>
                <div class="stat-chip${xpHighlight}"><span class="label">XP</span><span class="val">${c.xp}</span></div>
                <div class="stat-chip"><span class="label">KP</span><span class="val">${c.kill_points}</span></div>
            </div>
            <div class="roster-card-info">
                <div>Status: ${status}&nbsp;&nbsp;Loyalty: ${capitalize(c.loyalty)}</div>
                ${c.equipment && c.equipment.length > 0 ? `<div>Equipment: ${c.equipment.map(escapeHtml).join(', ')}</div>` : ''}
                ${c.upgrades && c.upgrades.length > 0 ? `<div>Upgrades: ${c.upgrades.map(escapeHtml).join(', ')}</div>` : ''}
            </div>
            ${compact ? '' : bgSection}
            ${compact ? '' : (c.narrative ? `<div class="roster-card-bg">${escapeHtml(c.narrative)}</div>` : '')}
            ${opts.extraHtml || ''}
        </div>
    `;
    return html;
}

// ── Roster Modal ────────────────────────────────────────────

function openRosterModal(opts = {}) {
    if (!_lastRosterData) return;

    const colonyData = _lastColonyData || {};
    const grunts = colonyData.grunts || 0;
    const botOk = colonyData.bot_operational;

    let bodyHtml = '';

    // Recovery messages box (step 1)
    const recoveryMsgs = opts.recoveryMessages || [];
    if (recoveryMsgs.length > 0) {
        const allReady = recoveryMsgs.length === 1 && recoveryMsgs[0].includes('All crew available');
        const boxClass = allReady ? 'recovery-box recovery-box-ok' : 'recovery-box';
        bodyHtml += `<div class="${boxClass}">
            <div class="recovery-box-title">Sick Bay Report</div>
            ${recoveryMsgs.map(m => `<div class="recovery-box-msg">${escapeHtml(m)}</div>`).join('')}
        </div>`;
    }

    // Replacement messages box (step 13)
    const replacementMsgs = opts.replacementMessages || [];
    if (replacementMsgs.length > 0) {
        const isFull = replacementMsgs.some(m => m.includes('Roster full'));
        const boxClass = isFull ? 'recovery-box recovery-box-ok' : 'recovery-box';
        bodyHtml += `<div class="${boxClass}">
            <div class="recovery-box-title">Replacements</div>
            ${replacementMsgs.map(m => `<div class="recovery-box-msg">${escapeHtml(m)}</div>`).join('')}
        </div>`;
    }

    bodyHtml += `
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
        bodyHtml += buildRosterCardHtml(c);
    }

    openModal('roster-modal', 'Colony Roster', bodyHtml);
}

// ── Theory Card Builder (shared) ────────────────────────────

/**
 * Build HTML for a single theory card.
 * Handles both sidebar data (t.invested, t.completed) and step 14 data (t.invested_rp).
 * @param {Object} t - Theory data object
 * @param {Object} [opts] - Options
 * @param {string}  [opts.extraHtml] - Extra HTML appended inside the card
 */
function buildTheoryCardHtml(t, opts = {}) {
    const invested = t.invested ?? t.invested_rp ?? 0;
    const cost = t.rp_cost || 0;
    const completed = t.completed ?? (invested >= cost);
    const locked = t.prerequisite_met === false;
    const pct = cost > 0 ? Math.min(100, Math.round((invested / cost) * 100)) : 0;
    const statusCls = completed ? 'tt-completed' : (invested > 0 ? 'tt-in-progress' : (locked ? 'tt-locked' : 'tt-available'));

    let s = `<div class="tt-theory ${statusCls}">`;
    s += `<div class="tt-theory-header">`;
    s += `<span class="tt-theory-name">${completed ? '&#10003; ' : ''}${escapeHtml(t.name)}</span>`;
    s += `<span class="tt-theory-rp">${invested}/${cost} RP</span>`;
    s += `</div>`;

    if (invested > 0 || completed) {
        s += `<div class="progress-bar" style="margin: 4px 0 6px;"><div class="progress-fill" style="width:${pct}%;background:${completed ? 'var(--accent-green)' : 'var(--accent-yellow)'};"></div></div>`;
    }

    if (locked && t.prerequisite_name) {
        s += `<div class="tt-prereq">Requires: ${escapeHtml(humanize(t.prerequisite_name))}</div>`;
    }

    // Applications
    if (t.applications && t.applications.length > 0) {
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

    if (opts.extraHtml) {
        s += opts.extraHtml;
    }

    s += `</div>`;
    return s;
}

// ── Research Modal ──────────────────────────────────────────

function openResearchModal() {
    if (!_lastColonyData) return;

    const theories = _lastColonyData.tech_tree || [];
    const primary = theories.filter(t => !t.is_secondary);
    const secondary = theories.filter(t => t.is_secondary);

    const rp = _lastColonyData.resources ? _lastColonyData.resources.research_points : 0;

    let bodyHtml = `
            <div class="research-rp-box">
                <span class="research-rp-label">Research Points Available</span>
                <span class="research-rp-value">${rp} RP</span>
            </div>
    `;

    if (theories.length === 0) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">No research data available.</div>';
    }

    if (primary.length > 0) {
        bodyHtml += '<h4 class="tt-section-header">Primary Theories</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const t of primary) bodyHtml += buildTheoryCardHtml(t);
        bodyHtml += '</div>';
    }

    if (secondary.length > 0) {
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Secondary Theories</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const t of secondary) bodyHtml += buildTheoryCardHtml(t);
        bodyHtml += '</div>';
    }

    openModal('research-modal', 'Research', bodyHtml, { maxWidth: '800px' });
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
    const data = _lastArmoryData || {};
    const weapons = data.weapons || [];
    const gruntUpgrades = data.grunt_upgrades || [];
    const standard = weapons.filter(w => w.tier === 'standard');
    const tier1 = weapons.filter(w => w.tier === 'tier_1');
    const tier2 = weapons.filter(w => w.tier === 'tier_2');

    let bodyHtml = '';

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
            s += `<div class="wpn-prereq">Requires: ${escapeHtml(humanize(w.prerequisite))}</div>`;
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
            s += `<div class="tt-prereq">Requires: ${escapeHtml(humanize(g.prerequisite))}</div>`;
        }
        s += `</div>`;
        return s;
    }

    if (standard.length > 0) {
        bodyHtml += '<h4 class="armory-tier-header">Standard Weapons</h4>';
        bodyHtml += '<div class="armory-grid">';
        for (const w of standard) bodyHtml += renderWeapon(w);
        bodyHtml += '</div>';
    }

    if (tier1.length > 0) {
        const t1Unlocked = tier1.some(w => w.available);
        const t1Badge = t1Unlocked
            ? '<span class="armory-unlocked-badge">Unlocked</span>'
            : '<span class="armory-locked-badge">&#128274; Locked — Requires Advanced Manufacturing Plant</span>';
        bodyHtml += `<h4 class="armory-tier-header">Tier 1 Upgrades ${t1Badge}</h4>`;
        bodyHtml += '<div class="armory-grid">';
        for (const w of tier1) bodyHtml += renderWeapon(w);
        bodyHtml += '</div>';
    }

    if (tier2.length > 0) {
        const t2Unlocked = tier2.some(w => w.available);
        const t2Badge = t2Unlocked
            ? '<span class="armory-unlocked-badge">Unlocked</span>'
            : '<span class="armory-locked-badge">&#128274; Locked — Requires High-Tech Manufacturing Plant</span>';
        bodyHtml += `<h4 class="armory-tier-header">Tier 2 Upgrades ${t2Badge}</h4>`;
        bodyHtml += '<div class="armory-grid">';
        for (const w of tier2) bodyHtml += renderWeapon(w);
        bodyHtml += '</div>';
    }

    if (gruntUpgrades.length > 0) {
        bodyHtml += '<h4 class="armory-tier-header">Grunt Upgrades</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const g of gruntUpgrades) bodyHtml += renderGruntUpgrade(g);
        bodyHtml += '</div>';
    }

    if (weapons.length === 0 && gruntUpgrades.length === 0) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">No armory data available.</div>';
    }

    openModal('armory-modal', 'Campaign Armory', bodyHtml, { maxWidth: '850px' });
}

// ── Buildings Modal ─────────────────────────────────────────

function openBuildingsModal() {
    if (!_lastColonyData) return;

    const built = _lastColonyData.buildings_built || [];
    const all = _lastColonyData.buildings_available || [];
    const available = all.filter(b => b.available);
    const locked = all.filter(b => b.locked);

    const bp = _lastColonyData.resources ? _lastColonyData.resources.build_points : 0;
    const rm = _lastColonyData.resources ? _lastColonyData.resources.raw_materials : 0;

    let bodyHtml = `
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
            s += `<div class="tt-prereq">Requires: ${escapeHtml(humanize(b.prerequisite))}</div>`;
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
        bodyHtml += '<h4 class="tt-section-header">Constructed</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const b of built) bodyHtml += renderBuilding({...b, built: true});
        bodyHtml += '</div>';
    }

    // Available to build
    if (available.length > 0) {
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Available to Build</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const b of available) bodyHtml += renderBuilding(b);
        bodyHtml += '</div>';
    }

    // Locked (research needed)
    if (locked.length > 0) {
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Locked (Research Required)</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const b of locked) bodyHtml += renderBuilding(b);
        bodyHtml += '</div>';
    }

    if (built.length === 0 && available.length === 0 && locked.length === 0) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">No building data available.</div>';
    }

    openModal('buildings-modal', 'Colony Buildings', bodyHtml, { maxWidth: '800px' });
}

// ── Ancient Signs Modal ─────────────────────────────────────

let _lastAncientSignsData = null;

function renderAncientSigns(data) {
    _lastAncientSignsData = data;
}

function openAncientSignsModal() {
    const data = _lastAncientSignsData || {};
    const signs = data.ancient_signs_count || 0;
    const missionData = data.mission_data_count || 0;
    const breakthroughs = data.breakthroughs || [];
    const btCount = data.breakthroughs_count || 0;
    const activeSites = data.active_sites || [];
    const exploredSites = data.explored_sites || [];

    // Resource counters
    let bodyHtml = `
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Signs Found</span>
                    <span class="resource-box-value">${signs}</span>
                </div>
                <div class="resource-box-item">
                    <span class="resource-box-label">Mission Data</span>
                    <span class="resource-box-value">${missionData}</span>
                </div>
            </div>
    `;

    // Breakthrough tracker (1-4) with effects
    const btEffects = [
        '2 Ancient Sites placed on the map',
        '4 sectors explored, +2 Resources each',
        '2 sectors marked for Investigation',
        'Final discovery — roll D100',
    ];
    // Map breakthrough data by index for details
    const btByIndex = {};
    for (const b of breakthroughs) {
        if (b.id === 'first_breakthrough') btByIndex[0] = b;
        else if (b.id === 'second_breakthrough') btByIndex[1] = b;
        else if (b.id === 'third_breakthrough') btByIndex[2] = b;
        else btByIndex[3] = b;  // 4th breakthrough (variable)
    }

    bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Breakthroughs</h4>';
    bodyHtml += '<div class="breakthrough-list">';
    const btLabels = ['1st', '2nd', '3rd', '4th'];
    for (let i = 0; i < 4; i++) {
        const done = i < btCount;
        const cls = done ? 'bt-row bt-done' : 'bt-row';
        const icon = done ? '&#10003;' : (i + 1);
        const detail = btByIndex[i];
        const effect = done && detail ? escapeHtml(detail.description) : btEffects[i];
        bodyHtml += `<div class="${cls}">
            <span class="bt-num">${icon}</span>
            <div class="bt-info">
                <span class="bt-label">${btLabels[i]} Breakthrough${done && detail ? ': ' + escapeHtml(detail.name) : ''}</span>
                <span class="bt-effect">${effect}</span>
            </div>
        </div>`;
    }
    bodyHtml += '</div>';

    // Ancient Sites
    if (activeSites.length > 0 || exploredSites.length > 0) {
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Ancient Sites</h4>';
        bodyHtml += '<div class="tt-grid">';

        // Active (unexplored) sites
        for (const s of activeSites) {
            bodyHtml += `<div class="tt-theory tt-available">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">${escapeHtml(s.name)}</span>
                    <span class="tt-theory-rp" style="color: var(--accent-yellow);">Unexplored</span>
                </div>
                <div class="tt-apps"><div class="tt-app"><span class="tt-app-desc" style="font-size:11px;">Sector ${s.sector_id} — Send a Delve mission to explore</span></div></div>
            </div>`;
        }

        // Explored sites with findings
        for (const s of exploredSites) {
            bodyHtml += `<div class="tt-theory tt-completed">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">&#10003; ${escapeHtml(s.name)}</span>
                    <span class="tt-theory-rp" style="color: var(--accent-green);">Explored</span>
                </div>
                <div class="tt-apps"><div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">Sector ${s.sector_id} — ${escapeHtml(s.finding || 'Explored')}</span></div></div>
            </div>`;
        }

        bodyHtml += '</div>';
    }

    // Artifacts section
    const artData = _lastArtifactsData || {};
    const artifacts = artData.artifacts || [];

    if (artifacts.length > 0) {
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Artifacts</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const art of artifacts) {
            const typeTag = art.artifact_type === 'single_use' ? '<span class="wpn-trait">Single-Use</span>'
                : art.artifact_type === 'equipment' ? '<span class="wpn-trait">Equipment</span>'
                : '<span class="wpn-trait">Colony Item</span>';
            const assignedTo = art.assigned_to ? `<div class="tt-prereq">Assigned to: ${escapeHtml(art.assigned_to)}</div>` : '';
            const usedLabel = art.used ? '<span style="color: var(--text-dim);">(Used)</span>' : '';

            bodyHtml += `<div class="tt-theory tt-completed">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">${escapeHtml(art.name)} ${usedLabel}</span>
                    ${typeTag}
                </div>
                <div class="tt-apps"><div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(art.description)}</span></div></div>
                ${assignedTo}
            </div>`;
        }
        bodyHtml += '</div>';
    }

    if (btCount === 0 && activeSites.length === 0 && exploredSites.length === 0 && artifacts.length === 0 && signs === 0 && missionData === 0) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">No discoveries yet. Investigate sectors to find Ancient Signs and Mission Data.</div>';
    }

    openModal('ancient-signs-modal', 'Discoveries', bodyHtml, { maxWidth: '700px' });
}

// ── Milestones Modal ────────────────────────────────────────

let _lastMilestonesData = null;

function renderMilestones(data) {
    _lastMilestonesData = data;
}

function openMilestonesModal() {
    const data = _lastMilestonesData || {};
    const completed = data.milestones_completed || 0;
    const total = 7;

    let bodyHtml = `
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Milestones Completed</span>
                    <span class="resource-box-value">${completed} / ${total}</span>
                </div>
            </div>
            <div class="progress-bar" style="height:10px;border-radius:5px;"><div class="progress-fill" style="width:${Math.round(completed/total*100)}%;background:var(--accent-magenta);border-radius:5px;"></div></div>
    `;

    // Milestone markers
    bodyHtml += '<div class="milestone-track">';
    for (let i = 1; i <= total; i++) {
        const cls = i <= completed ? 'milestone-dot milestone-done' : 'milestone-dot';
        const label = i === 7 ? 'End Game' : 'Milestone ' + i;
        bodyHtml += `<div class="${cls}" title="${label}"><span>${i}</span></div>`;
    }
    bodyHtml += '</div>';

    if (data.effects && data.effects.length > 0) {
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:16px;">Milestone Effects</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const eff of data.effects) {
            const done = eff.milestone <= completed;
            bodyHtml += `<div class="tt-theory ${done ? 'tt-completed' : 'tt-locked'}">
                <div class="tt-theory-header"><span class="tt-theory-name">${done ? '&#10003; ' : ''}Milestone ${eff.milestone}</span></div>
                <div class="tt-apps">`;
            for (const desc of (eff.descriptions || [])) {
                bodyHtml += `<div class="tt-app ${done ? 'tt-app-unlocked' : 'tt-app-locked'}"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(desc)}</span></div>`;
            }
            bodyHtml += `</div></div>`;
        }
        bodyHtml += '</div>';
    }

    // Debug controls
    bodyHtml += `<div style="margin-top:16px;text-align:center;display:flex;gap:8px;justify-content:center;align-items:center;flex-wrap:wrap;">
        <button class="btn btn-secondary" onclick="debugAddMilestone()" style="font-size:12px;padding:4px 12px;opacity:0.7;">Test Milestone (+1)</button>
        <span style="opacity:0.5;font-size:12px;">|</span>
        <label style="font-size:12px;opacity:0.7;">Set Step:</label>
        <input type="number" id="debug-step-input" min="0" max="18" value="0" style="width:50px;font-size:12px;padding:2px 4px;background:#1a1a2e;color:#e0e0e0;border:1px solid #444;border-radius:4px;">
        <button class="btn btn-secondary" onclick="debugSetStep()" style="font-size:12px;padding:4px 12px;opacity:0.7;">Set</button>
    </div>`;

    openModal('milestones-modal', 'Milestones', bodyHtml, { maxWidth: '700px' });
}

function debugAddMilestone() {
    if (window._ws && window._ws.readyState === WebSocket.OPEN) {
        window._ws.send(JSON.stringify({ type: 'debug_add_milestone' }));
    }
}

function debugSetStep() {
    const input = document.getElementById('debug-step-input');
    const step = parseInt(input?.value || '0', 10);
    if (window._ws && window._ws.readyState === WebSocket.OPEN) {
        window._ws.send(JSON.stringify({ type: 'debug_set_step', step }));
    }
}

// ── Conditions Modal ─────────────────────────────────────────

let _lastConditionsData = null;

function renderConditions(data) {
    _lastConditionsData = data;
}

function openConditionsModal() {
    const data = _lastConditionsData || {};
    const slots = data.slots || [];

    let bodyHtml = `
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
            bodyHtml += `<tr class="d100-row-filled"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry">${desc}</td></tr>`;
        } else {
            bodyHtml += `<tr class="d100-row-empty"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry" style="color:var(--text-dim);font-style:italic;">—</td></tr>`;
        }
    }

    // If no slots data, show 10 empty slots
    if (slots.length === 0) {
        const defaultRanges = [[1,18],[19,32],[33,44],[45,54],[55,64],[65,73],[74,82],[83,89],[90,95],[96,100]];
        for (let i = 0; i < 10; i++) {
            const rangeStr = String(defaultRanges[i][0]).padStart(2, '0') + '–' + String(defaultRanges[i][1]).padStart(2, '0');
            bodyHtml += `<tr class="d100-row-empty"><td class="d100-range">${rangeStr}</td><td class="d100-num">${i+1}</td><td class="d100-entry" style="color:var(--text-dim);font-style:italic;">—</td></tr>`;
        }
    }

    bodyHtml += `</tbody></table>`;

    openModal('conditions-modal', 'Campaign Conditions', bodyHtml, { maxWidth: '700px' });
}

// ── Lifeforms Modal ─────────────────────────────────────────

let _lastLifeformsData = null;

function renderLifeforms(data) {
    _lastLifeformsData = data;
}

function openLifeformsModal() {
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

    let bodyHtml = `
            <table class="d100-table">
                <thead>
                    <tr><th>D100</th><th>#</th><th>Entry</th></tr>
                </thead>
                <tbody>
    `;

    for (const slot of slots) {
        const rangeStr = String(slot.d100_low).padStart(2, '0') + '–' + String(slot.d100_high).padStart(2, '0');
        const lf = slot.entry;
        if (lf && lf.name) {
            let desc = `<strong>${escapeHtml(lf.name)}</strong>`;
            let stats = [`Spd ${lf.mobility}"`, `CS +${lf.combat_skill}`, `T ${lf.toughness}`];
            if (lf.strike_damage) stats.push(`Dmg +${lf.strike_damage}`);
            if (lf.armor_save) stats.push(`Arm ${lf.armor_save}+`);
            if (lf.kill_points > 1) stats.push(`KP ${lf.kill_points}`);
            const tips = (typeof SPECIAL_RULE_TIPS !== 'undefined') ? SPECIAL_RULE_TIPS : {};
            desc += ` <span class="lf-stats">${stats.join(' | ')}</span>`;
            if (lf.weapons && lf.weapons.length) {
                desc += `<br><span class="lf-weapons">${lf.weapons.map(w => {
                    const wKey = w.toLowerCase().replace(/\s+/g, '_');
                    const wTip = tips[wKey] || '';
                    if (wTip) {
                        return `<span class="wpn-trait has-tooltip" data-tooltip="${escapeHtml(wTip)}">${escapeHtml(w)}</span>`;
                    }
                    return escapeHtml(w);
                }).join(', ')}</span>`;
            }
            // Collect all abilities/traits into a single line
            const allTraits = [];
            if (lf.dodge) allTraits.push('dodge');
            if (lf.partially_airborne) allTraits.push('partially_airborne');
            if (lf.special_rules) {
                for (const r of lf.special_rules) {
                    if (!allTraits.includes(r)) allTraits.push(r);
                }
            }
            if (allTraits.length) {
                const traitSpans = allTraits.map(r => {
                    const label = r.replace(/_/g, ' ');
                    const tip = tips[r] || '';
                    return `<span class="wpn-trait epc-rule${tip ? ' has-tooltip' : ''}" ${tip ? `data-tooltip="${escapeHtml(tip)}"` : ''}>${escapeHtml(label)}</span>`;
                }).join(' ');
                desc += `<br><span class="lf-special">${traitSpans}</span>`;
            }
            if (lf.specimen_collected) {
                desc += ` <span class="lf-specimen">&#9733; Specimen</span>`;
                if (lf.bio_analysis_result) {
                    desc += ` <span class="lf-bio">(${escapeHtml(lf.bio_analysis_result.replace(/_/g, ' '))})</span>`;
                }
            }
            bodyHtml += `<tr class="d100-row-filled"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry">${desc}</td></tr>`;
        } else {
            bodyHtml += `<tr class="d100-row-empty"><td class="d100-range">${rangeStr}</td><td class="d100-num">${slot.index}</td><td class="d100-entry" style="color:var(--text-dim);font-style:italic;">—</td></tr>`;
        }
    }

    bodyHtml += `</tbody></table>`;

    openModal('lifeforms-modal', 'Lifeform Encounters', bodyHtml, { maxWidth: '800px' });
}

// ── Enemies Modal ───────────────────────────────────────────

let _lastEnemiesData = null;

function renderEnemies(data) {
    _lastEnemiesData = data;
}

function openEnemiesModal() {
    const data = _lastEnemiesData || {};
    const tactical = data.tactical_enemies || [];
    const slyn = data.slyn || {};

    let bodyHtml = '';

    // Slyn status
    bodyHtml += `<div class="resource-box">
        <div class="resource-box-item">
            <span class="resource-box-label">Slyn</span>
            <span class="resource-box-value ${slyn.active ? '' : 'negative'}">${slyn.active ? 'Active' : 'Driven Off'}</span>
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
        bodyHtml += '<h4 class="tt-section-header" style="margin-top:12px;">Tactical Enemies</h4>';
        bodyHtml += '<div class="tt-grid">';
        for (const te of tactical) {
            const statusCls = te.defeated ? 'tt-completed' : 'tt-available';
            const profile = te.profile || {};
            bodyHtml += `<div class="tt-theory ${statusCls}">
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
        bodyHtml += '</div>';
    }

    if (tactical.length === 0 && !slyn.active) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px; margin-top: 12px;">No tactical enemies encountered yet.</div>';
    }

    openModal('enemies-modal', 'Enemies', bodyHtml, { maxWidth: '800px' });
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
    const data = _lastAugmentationsData || {};
    const ap = data.augmentation_points != null ? data.augmentation_points : (_lastColonyData ? _lastColonyData.resources.augmentation_points : 0);
    const nextCost = data.next_cost || '?';
    const ownedCount = data.owned_count || 0;
    const boughtThisTurn = data.bought_this_turn || false;
    const augmentations = data.augmentations || [];

    let bodyHtml = `
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
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">Augmentation options become available through Genetic Advancement research.</div>';
    }

    for (const aug of augmentations) {
        const statusCls = aug.owned ? 'tt-completed' : 'tt-available';
        const milestoneTag = aug.is_milestone ? ' <span class="bld-milestone">Milestone</span>' : '';

        bodyHtml += `
            <div class="tt-theory ${statusCls}">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">${aug.owned ? '&#10003; ' : ''}${escapeHtml(aug.name)}${milestoneTag}</span>
                </div>
                <div class="tt-apps"><div class="tt-app ${aug.owned ? 'tt-app-unlocked' : 'tt-app-locked'}"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(aug.description)}</span></div></div>
            </div>`;
    }

    bodyHtml += `</div>`;

    openModal('augmentations-modal', 'Augmentations', bodyHtml, { maxWidth: '750px' });
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
    const data = _lastArtifactsData || {};
    const artifacts = data.artifacts || [];

    let bodyHtml = `<div class="tech-tree">`;

    if (artifacts.length === 0) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">No artifacts discovered yet. Search Ancient Sites to find alien artifacts.</div>';
    }

    for (const art of artifacts) {
        const typeTag = art.artifact_type === 'single_use' ? '<span class="wpn-trait">Single-Use</span>'
            : art.artifact_type === 'equipment' ? '<span class="wpn-trait">Equipment</span>'
            : '<span class="wpn-trait">Colony Item</span>';
        const assignedTo = art.assigned_to ? `<div class="tt-prereq">Assigned to: ${escapeHtml(art.assigned_to)}</div>` : '';
        const usedLabel = art.used ? '<span style="color: var(--text-dim);">(Used)</span>' : '';

        bodyHtml += `
            <div class="tt-theory tt-completed">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">${escapeHtml(art.name)} ${usedLabel}</span>
                    ${typeTag}
                </div>
                <div class="tt-apps"><div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(art.description)}</span></div></div>
                ${assignedTo}
            </div>`;
    }

    bodyHtml += `</div>`;

    openModal('artifacts-modal', 'Artifacts', bodyHtml, { maxWidth: '750px' });
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
    const data = _lastCalamitiesData || {};
    const points = data.calamity_points || 0;
    const events = data.calamity_events || [];

    let bodyHtml = `
            <div class="resource-box">
                <div class="resource-box-item">
                    <span class="resource-box-label">Calamity Points</span>
                    <span class="resource-box-value">${points}</span>
                </div>
            </div>`;

    if (events.length === 0) {
        bodyHtml += '<div style="color: var(--text-dim); padding: 12px;">No calamity events yet.</div>';
    }

    for (const evt of events) {
        bodyHtml += `
            <div class="tt-theory tt-completed">
                <div class="tt-theory-header">
                    <span class="tt-theory-name">Turn ${evt.turn}: ${escapeHtml(evt.name)}</span>
                </div>
                <div class="tt-apps"><div class="tt-app tt-app-unlocked"><span class="tt-app-icon">&#8226;</span><span class="tt-app-desc" style="font-size:11px;">${escapeHtml(evt.description)}</span></div></div>
            </div>`;
    }

    openModal('calamities-modal', 'Calamities', bodyHtml, { maxWidth: '700px' });
}

// ── Morale ──────────────────────────────────────────────────

let _lastMoraleData = null;

function renderMorale(data) {
    _lastMoraleData = data;
    // Auto-open modal when morale change data arrives (step 11)
    if (data.change) {
        openMoraleModal();
    } else if (document.getElementById('morale-modal')) {
        openMoraleModal();
    }
}

function openMoraleModal() {
    const data = _lastMoraleData || {};
    const morale = data.morale != null ? data.morale : (_lastColonyData ? _lastColonyData.morale : 0);
    const politicalUpheaval = data.political_upheaval || 0;
    const inCrisis = data.in_crisis || false;
    const change = data.change || null;

    const moraleCls = morale >= 0 ? 'positive' : 'negative';

    let bodyHtml = '';

    // Morale change pill (shown during step 11)
    if (change) {
        const delta = change.new - change.old;
        const pillCls = delta > 0 ? 'morale-pill-positive' : (delta < 0 ? 'morale-pill-negative' : 'morale-pill-neutral');
        const sign = delta > 0 ? '+' : '';
        bodyHtml += `
            <div class="morale-change-box">
                <span class="morale-change-old">${change.old}</span>
                <span class="morale-change-arrow">&rarr;</span>
                <span class="morale-change-new">${change.new}</span>
                <span class="morale-pill ${pillCls}">${sign}${delta}</span>
            </div>
            <div class="morale-change-desc">${escapeHtml(change.description)}</div>`;
    }

    bodyHtml += `
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

            <div style="color: var(--text-dim); padding: 8px 12px; font-size: 0.85em;">
                Morale decreases by 1 each turn, by 1 per battle casualty, and by 1 per point of colony damage.
                At -10 or worse, a Morale Incident occurs (morale resets to 0).
            </div>`;

    openModal('morale-modal', 'Colony Morale', bodyHtml, { maxWidth: '750px' });

    // Clear change data so sidebar re-opens don't show stale pill
    if (_lastMoraleData) delete _lastMoraleData.change;
}

// ── Colony Log (sidebar trigger) ────────────────────────────

function openColonyLog() {
    // If we have a websocket, request the log from the server
    if (window._ws && window._ws.readyState === 1) {
        window._ws.send(JSON.stringify({ type: 'request_log' }));
    }
}

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


// ── Resource Cache Modal (out-of-band SP spend) ───────────
function openResourceCacheModal() {
    const data = _lastColonyData;
    if (!data) return;

    const sp = data.resources.story_points;
    if (sp < 1) {
        openModal('rc-modal', 'Resource Cache', `
            <div style="padding: 20px; text-align: center; color: var(--text-dim)">
                <p>Not enough Story Points (${sp} SP available, 1 required).</p>
            </div>
        `);
        return;
    }

    // Show confirmation before spending
    openModal('rc-modal', 'Resource Cache', `
        <div class="rc-modal-body">
            <p>Spend <strong>1 Story Point</strong> to open a Resource Cache?</p>
            <p>Roll 2D6, take the highest die — allocate that many points across
            Build Points, Research Points, and Raw Materials.</p>
            <div class="rc-sp-info">Current: ${sp} SP → ${sp - 1} SP after spending</div>
            <div class="rc-modal-actions">
                <button class="btn" onclick="document.getElementById('rc-modal').remove()">Cancel</button>
                <button class="btn btn-primary" onclick="_doResourceCacheRoll()">Open Cache (1 SP)</button>
            </div>
        </div>
    `);
}

function _doResourceCacheRoll() {
    if (window._ws && window._ws.readyState === 1) {
        window._ws.send(JSON.stringify({ type: 'resource_cache_request' }));
        // Update modal to show rolling state
        const modal = document.querySelector('#rc-modal .modal-body');
        if (modal) {
            modal.innerHTML = `
                <div style="padding: 40px; text-align: center">
                    <div class="loading-spinner"></div>
                    <p style="margin-top: 16px; color: var(--text-dim)">Rolling dice...</p>
                </div>
            `;
        }
    }
}

function _handleResourceCacheRolled(msg) {
    // Server rolled dice — show allocation UI in the modal
    const budget = msg.budget;
    const dice = msg.dice || [];
    const spRemaining = msg.sp_remaining;
    let bp = 0, rp = 0, rm = 0;

    const modal = document.querySelector('#rc-modal .modal-body');
    if (!modal) return;

    function remaining() { return budget - bp - rp - rm; }

    function render() {
        modal.innerHTML = `
            <div class="rc-modal-body">
                <div class="rc-dice-display">
                    <div class="rc-dice-pair">
                        ${dice.map(d => `<span class="rc-die">${d}</span>`).join('')}
                    </div>
                    <div class="rc-budget-display">
                        Budget: <span class="rc-budget-num">${budget}</span>
                    </div>
                </div>
                <div class="rc-remaining ${remaining() === 0 ? 'rc-zero' : ''}">
                    ${remaining()} point${remaining() !== 1 ? 's' : ''} to allocate
                </div>
                <div class="rc-resources">
                    ${_rcModalRow('Build Points', 'bp', bp, 'var(--accent-orange, #f0a030)')}
                    ${_rcModalRow('Research Points', 'rp', rp, 'var(--accent-cyan, #40d0d0)')}
                    ${_rcModalRow('Raw Materials', 'rm', rm, 'var(--accent-green, #40c040)')}
                </div>
                <div class="rc-modal-actions">
                    <button class="btn btn-primary rc-confirm-btn">Confirm</button>
                </div>
            </div>
        `;

        // Wire buttons
        modal.querySelectorAll('.rc-btn-minus').forEach(btn => {
            btn.onclick = () => {
                const key = btn.dataset.key;
                if (key === 'bp' && bp > 0) bp--;
                else if (key === 'rp' && rp > 0) rp--;
                else if (key === 'rm' && rm > 0) rm--;
                render();
            };
        });
        modal.querySelectorAll('.rc-btn-plus').forEach(btn => {
            btn.onclick = () => {
                if (remaining() <= 0) return;
                const key = btn.dataset.key;
                if (key === 'bp') bp++;
                else if (key === 'rp') rp++;
                else if (key === 'rm') rm++;
                render();
            };
        });
        modal.querySelector('.rc-confirm-btn').onclick = () => {
            if (window._ws && window._ws.readyState === 1) {
                window._ws.send(JSON.stringify({
                    type: 'resource_cache_allocate',
                    bp, rp, rm, budget,
                }));
            }
            // Close modal
            const overlay = document.getElementById('rc-modal');
            if (overlay) overlay.remove();
        };
    }

    function _rcModalRow(label, key, val, color) {
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
}

function _handleResourceCacheResult(msg) {
    if (!msg.success) {
        // Show error — modal might already be closed
        return;
    }
    // Colony status is refreshed by the server automatically
}
