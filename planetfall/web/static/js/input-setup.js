/**
 * Planetfall Web UI — Setup input renderers.
 *
 * Handles roster editing, colony setup, and colony-ready modals
 * used during campaign creation and setup phases.
 *
 * Depends on: app.js (sendResponse, appendMessage, escapeHtml, capitalize),
 *             input.js (clearInput)
 */

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

    if (msg.colony_description) {
        const descParas = msg.colony_description.split(/\n\n+/).filter(p => p.trim());
        const descHtml = descParas.map(p => `<p style="margin:0 0 10px;">${escapeHtml(p.trim())}</p>`).join('');
        html += `<div class="roster-card-bg" style="margin-bottom:16px;padding:12px;border-left:3px solid var(--accent-cyan);font-style:italic;">${descHtml}</div>`;
    }

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
