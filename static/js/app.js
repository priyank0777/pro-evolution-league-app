/**
 * 2v2 eFootball League Tournament Management SPA Controller
 * Pure Vanilla JavaScript + Fetch API
 */

const app = {
    token: localStorage.getItem('ef_jwt_token') || null,
    user: null,
    settings: null,
    currentView: 'dashboard',
    preferencesList: [],
    draggedPrefIndex: null,
    allMatchesCache: [],
    selectedFixtureMw: 'all',

    // -----------------------------------------------------------------------
    // Initialization & API Helper
    // -----------------------------------------------------------------------
    async init() {
        await this.fetchPublicSettings();
        if (this.token) {
            try {
                this.user = await this.api('/api/auth/me');
                this.updateNavigationUI();
                this.navigate('dashboard');
            } catch (err) {
                this.logout(false);
            }
        } else {
            this.showAuthView();
        }
    },

    async api(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const response = await fetch(endpoint, {
            ...options,
            headers,
        });

        let data = null;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        }

        if (!response.ok) {
            const detail = (data && data.detail) ? data.detail : `Request failed (${response.status})`;
            throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }
        return data;
    },

    toast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        const colors = {
            success: 'border-emerald-500/50 bg-slate-900/95 text-emerald-300',
            error: 'border-rose-500/50 bg-slate-900/95 text-rose-300',
            info: 'border-blue-500/50 bg-slate-900/95 text-blue-300',
        };
        el.className = `pointer-events-auto rounded-xl border px-4 py-3 text-xs font-semibold shadow-xl backdrop-blur transition-all duration-200 flex items-center justify-between gap-3 ${colors[type] || colors.info}`;
        el.innerHTML = `
            <span>${this.escapeHtml(message)}</span>
            <button class="text-slate-400 hover:text-white text-sm font-bold">&times;</button>
        `;
        el.querySelector('button').onclick = () => el.remove();
        container.appendChild(el);
        setTimeout(() => {
            if (el.parentNode) el.remove();
        }, 4500);
    },

    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    formatDate(isoStr) {
        if (!isoStr) return 'TBD';
        const d = new Date(isoStr);
        return d.toLocaleString(undefined, {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    },

    statusBadge(status) {
        const map = {
            pending: { label: 'Pending', cls: 'bg-slate-800 text-slate-300 border-slate-700' },
            submitted: { label: 'Awaiting Away Verification', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
            accepted: { label: 'Final (Accepted)', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
            disputed: { label: 'Disputed (Admin Review)', cls: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
            auto_drawn: { label: 'Auto-Draw (0-0 Deadline)', cls: 'bg-purple-500/15 text-purple-300 border-purple-500/30' },
        };
        const item = map[status] || { label: status, cls: 'bg-slate-800 text-slate-300 border-slate-700' };
        return `<span class="text-[11px] font-bold uppercase px-2.5 py-0.5 rounded-full border ${item.cls}">${item.label}</span>`;
    },

    // -----------------------------------------------------------------------
    // System Settings & Navigation State
    // -----------------------------------------------------------------------
    async fetchPublicSettings() {
        try {
            this.settings = await this.api('/api/settings/public');
            this.renderPhaseBanner();
        } catch (err) {
            console.error('Failed to load system settings:', err);
        }
    },

    renderPhaseBanner() {
        const s = this.settings;
        if (!s) return;

        let phaseTitle = 'Pre-Season Preparation';
        let phaseDesc = 'Waiting for Commissioner to open the next tournament phase.';
        let badgeColor = 'bg-slate-800 text-slate-300 border-slate-700';

        if (s.registration_open) {
            phaseTitle = 'Phase 1: Player Registration Open';
            phaseDesc = 'Players can sign up with their Name and eFootball Username.';
            badgeColor = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
        } else if (s.preferences_open) {
            phaseTitle = 'Phase 2: Partner Preference Ranking Open';
            phaseDesc = 'Rank all other registered players from most preferred partner (#1) to least preferred.';
            badgeColor = 'bg-blue-500/15 text-blue-400 border-blue-500/30';
        } else if (s.team_setup_open && !s.season_live) {
            phaseTitle = 'Phase 3 & 4: Matchmaking Complete — Team Setup Open';
            phaseDesc = 'Visit "My Team" to customize your Team Name and designate your Team Leader (Captain).';
            badgeColor = 'bg-amber-500/15 text-amber-400 border-amber-500/30';
        } else if (s.season_live) {
            phaseTitle = `Live Season — Matchweek ${s.current_matchweek}`;
            phaseDesc = `Round-Robin (${s.round_robin_multiplier}x) is live! Home team submits scores; Away team verifies before Friday midnight.`;
            badgeColor = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
        }

        const sub = document.getElementById('header-phase-subtitle');
        if (sub) sub.textContent = phaseTitle;

        const banner = document.getElementById('phase-banner');
        if (banner && this.user) {
            banner.classList.remove('hidden');
            const tracked = [];
            if (s.track_points) tracked.push('Total Points');
            if (s.track_goals) tracked.push('Goals');
            if (s.track_assists) tracked.push('Assists');

            banner.innerHTML = `
                <div class="flex items-center gap-3">
                    <span class="px-3 py-1 rounded-full text-xs font-extrabold uppercase border ${badgeColor}">
                        ${this.escapeHtml(phaseTitle)}
                    </span>
                    <p class="text-xs sm:text-sm text-slate-300">${this.escapeHtml(phaseDesc)}</p>
                </div>
                <div class="text-xs text-slate-400">
                    Tracked Stats: <span class="font-semibold text-slate-200">${tracked.length ? tracked.join(' • ') : 'Score Only'}</span>
                </div>
            `;
        }
    },

    updateNavigationUI() {
        const nav = document.getElementById('main-nav');
        const userArea = document.getElementById('header-user-area');

        if (!this.user) {
            nav.classList.add('hidden');
            userArea.innerHTML = '';
            document.getElementById('phase-banner').classList.add('hidden');
            return;
        }

        nav.classList.remove('hidden');
        userArea.innerHTML = `
            <div class="text-right hidden sm:block">
                <div class="text-xs font-bold text-white flex items-center justify-end gap-1.5">
                    ${this.escapeHtml(this.user.name)}
                    ${this.user.is_admin ? '<span class="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 text-[10px] uppercase">Admin</span>' : ''}
                </div>
                <div class="text-[11px] text-slate-400">@${this.escapeHtml(this.user.efootball_username)} ${this.user.team_name ? `• <span class="text-emerald-400">${this.escapeHtml(this.user.team_name)}</span>` : ''}</div>
            </div>
            <button onclick="app.logout()" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-rose-500/20 hover:text-rose-300 border border-slate-700 text-xs font-semibold text-slate-300 transition">
                Sign Out
            </button>
        `;

        // Conditional Navigation Tabs
        const prefBtn = document.getElementById('nav-preferences');
        const myTeamBtn = document.getElementById('nav-my-team');
        const adminBtn = document.getElementById('nav-admin');

        if (this.settings && this.settings.preferences_open && !this.user.is_admin) {
            prefBtn.classList.remove('hidden');
        } else {
            prefBtn.classList.add('hidden');
        }

        if (this.user.team_id) {
            myTeamBtn.classList.remove('hidden');
        } else {
            myTeamBtn.classList.add('hidden');
        }

        if (this.user.is_admin) {
            adminBtn.classList.remove('hidden');
        } else {
            adminBtn.classList.add('hidden');
        }

        this.renderPhaseBanner();
    },

    async navigate(view) {
        if (!this.user) {
            this.showAuthView();
            return;
        }

        await this.fetchPublicSettings();
        this.user = await this.api('/api/auth/me');
        this.updateNavigationUI();

        // Guard restricted tabs
        if (view === 'preferences' && (!this.settings.preferences_open || this.user.is_admin)) {
            this.toast('Partner Preferences phase is not open.', 'info');
            view = 'dashboard';
        }
        if (view === 'my-team' && !this.user.team_id) {
            this.toast('You have not been paired into a team yet.', 'info');
            view = 'dashboard';
        }
        if (view === 'admin' && !this.user.is_admin) {
            this.toast('Admin access required.', 'error');
            view = 'dashboard';
        }

        this.currentView = view;
        document.getElementById('view-auth').classList.add('hidden');
        document.querySelectorAll('.spa-view').forEach(el => el.classList.add('hidden'));

        const activeSection = document.getElementById(`view-${view}`);
        if (activeSection) activeSection.classList.remove('hidden');

        // Highlight active nav tab
        document.querySelectorAll('.nav-btn').forEach(btn => {
            if (btn.dataset.nav === view) {
                btn.classList.add('bg-emerald-500', 'text-slate-950', 'font-bold');
                btn.classList.remove('text-slate-300', 'hover:bg-slate-800');
            } else {
                btn.classList.remove('bg-emerald-500', 'text-slate-950', 'font-bold');
                btn.classList.add('text-slate-300', 'hover:bg-slate-800');
            }
        });

        // Trigger view loader
        if (view === 'dashboard') await this.loadDashboard();
        else if (view === 'preferences') await this.loadPreferences();
        else if (view === 'my-team') await this.loadMyTeam();
        else if (view === 'fixtures') await this.loadAllFixtures();
        else if (view === 'standings') await this.loadStandings();
        else if (view === 'teams') await this.loadTeamDirectory();
        else if (view === 'leaderboard') await this.loadLeaderboard();
        else if (view === 'admin') await this.loadAdminDashboard();
    },

    // -----------------------------------------------------------------------
    // 1. Authentication View
    // -----------------------------------------------------------------------
    showAuthView() {
        document.querySelectorAll('.spa-view').forEach(el => el.classList.add('hidden'));
        document.getElementById('view-auth').classList.remove('hidden');
        this.updateNavigationUI();
        this.switchAuthTab('login');
    },

    switchAuthTab(mode) {
        const loginForm = document.getElementById('form-login');
        const regForm = document.getElementById('form-register');
        const loginBtn = document.getElementById('tab-login-btn');
        const regBtn = document.getElementById('tab-register-btn');
        const closedNotice = document.getElementById('register-closed-notice');
        const regSubmitBtn = document.getElementById('reg-submit-btn');

        if (mode === 'login') {
            loginForm.classList.remove('hidden');
            regForm.classList.add('hidden');
            loginBtn.className = 'py-2 text-sm font-semibold rounded-lg bg-emerald-500 text-slate-950 transition';
            regBtn.className = 'py-2 text-sm font-semibold rounded-lg text-slate-400 hover:text-white transition';
        } else {
            loginForm.classList.add('hidden');
            regForm.classList.remove('hidden');
            regBtn.className = 'py-2 text-sm font-semibold rounded-lg bg-emerald-500 text-slate-950 transition';
            loginBtn.className = 'py-2 text-sm font-semibold rounded-lg text-slate-400 hover:text-white transition';

            if (this.settings && !this.settings.registration_open) {
                closedNotice.classList.remove('hidden');
                regSubmitBtn.disabled = true;
                regSubmitBtn.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                closedNotice.classList.add('hidden');
                regSubmitBtn.disabled = false;
                regSubmitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }
    },

    async handleLogin(e) {
        e.preventDefault();
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;

        try {
            const res = await this.api('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({ efootball_username: username, password }),
            });
            this.token = res.access_token;
            localStorage.setItem('ef_jwt_token', this.token);
            this.user = res.user;
            this.toast(`Welcome back, ${this.user.name}!`, 'success');
            this.updateNavigationUI();
            this.navigate(this.user.is_admin ? 'admin' : 'dashboard');
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    async handleRegister(e) {
        e.preventDefault();
        const name = document.getElementById('reg-name').value.trim();
        const username = document.getElementById('reg-username').value.trim();
        const password = document.getElementById('reg-password').value;

        try {
            const res = await this.api('/api/auth/register', {
                method: 'POST',
                body: JSON.stringify({ name, efootball_username: username, password }),
            });
            this.token = res.access_token;
            localStorage.setItem('ef_jwt_token', this.token);
            this.user = res.user;
            this.toast('Account registered! Welcome to the 2v2 eFootball League.', 'success');
            this.updateNavigationUI();
            this.navigate('dashboard');
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    logout(notify = true) {
        this.token = null;
        this.user = null;
        localStorage.removeItem('ef_jwt_token');
        if (notify) this.toast('Signed out.', 'info');
        this.showAuthView();
    },

    // -----------------------------------------------------------------------
    // 2. User Dashboard View
    // -----------------------------------------------------------------------
    async loadDashboard() {
        const cardsEl = document.getElementById('dashboard-summary-cards');
        const listEl = document.getElementById('dashboard-fixtures-list');

        cardsEl.innerHTML = `
            <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
                <p class="text-xs font-bold uppercase tracking-wider text-slate-400">Player Profile</p>
                <p class="text-lg font-extrabold text-white mt-1">${this.escapeHtml(this.user.name)}</p>
                <p class="text-xs text-emerald-400 font-mono-num mt-0.5">@${this.escapeHtml(this.user.efootball_username)}</p>
            </div>
            <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
                <p class="text-xs font-bold uppercase tracking-wider text-slate-400">Assigned 2v2 Team</p>
                <p class="text-lg font-extrabold text-white mt-1">${this.user.team_name ? this.escapeHtml(this.user.team_name) : 'Not Paired Yet'}</p>
                <p class="text-xs text-slate-400 mt-0.5">
                    ${this.user.team_id ? `<button onclick="app.navigate('my-team')" class="text-emerald-400 hover:underline font-semibold">Manage My Team &rarr;</button>` : 'Waiting for Admin matchmaking'}
                </p>
            </div>
            <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
                <p class="text-xs font-bold uppercase tracking-wider text-slate-400">Active Matchweek</p>
                <p class="text-lg font-extrabold text-white mt-1">Matchweek ${this.settings ? this.settings.current_matchweek : 1}</p>
                <p class="text-xs text-slate-400 mt-0.5">
                    ${this.settings && this.settings.preferences_open && !this.user.is_admin
                        ? `<button onclick="app.navigate('preferences')" class="text-blue-400 hover:underline font-semibold">Submit Partner Preferences &rarr;</button>`
                        : 'Friday-to-Friday Weekly Cycle'}
                </p>
            </div>
        `;

        try {
            const myMatches = await this.api('/api/matches/my-current');
            if (!myMatches.length) {
                listEl.innerHTML = `
                    <div class="rounded-xl border border-slate-800/80 bg-slate-950/60 p-8 text-center">
                        <p class="text-sm font-semibold text-slate-300">No active fixtures found for your team in Matchweek ${this.settings.current_matchweek}.</p>
                        <p class="text-xs text-slate-500 mt-1">Check "All Fixtures" to browse the full season schedule or wait for the Admin to generate fixtures.</p>
                    </div>
                `;
                return;
            }

            listEl.innerHTML = myMatches.map(m => this.renderMatchCard(m, true)).join('');
        } catch (err) {
            listEl.innerHTML = `<p class="text-xs text-rose-400">${this.escapeHtml(err.message)}</p>`;
        }
    },

    renderMatchCard(m, showActionButtons = false) {
        const isHome = this.user && this.user.team_id === m.home_team_id;
        const isAway = this.user && this.user.team_id === m.away_team_id;
        const hasScore = m.home_score !== null && m.away_score !== null;

        let actionHtml = '';
        if (showActionButtons && this.user) {
            if (isHome && (m.status === 'pending' || m.status === 'submitted')) {
                actionHtml = `
                    <button onclick='app.openScoreModal(${JSON.stringify(m)}, "home_submit")'
                        class="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition shadow-lg shadow-emerald-500/20">
                        ${m.status === 'submitted' ? 'Update Submitted Score' : 'Submit Score & Stats'}
                    </button>
                `;
            } else if (isAway && m.status === 'submitted') {
                actionHtml = `
                    <button onclick='app.openVerifyModal(${JSON.stringify(m)})'
                        class="px-4 py-2 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs transition shadow-lg shadow-amber-400/20">
                        Verify / Dispute Score
                    </button>
                `;
            } else if (isAway && m.status === 'pending') {
                actionHtml = `<span class="text-xs text-slate-400 italic">Waiting for Home team to submit score</span>`;
            }
        }

        const statsHtml = m.player_stats && m.player_stats.length
            ? `
                <div class="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    ${m.player_stats.map(st => `
                        <div class="flex items-center justify-between rounded-lg bg-slate-950/70 px-3 py-1.5 border border-slate-800/60">
                            <span class="font-medium text-slate-300">${this.escapeHtml(st.user_name)} <span class="text-slate-500">@${this.escapeHtml(st.efootball_username)}</span></span>
                            <span class="font-mono-num text-slate-200 flex items-center gap-2">
                                ${this.settings.track_points ? `<span class="text-emerald-400 font-bold">${st.total_points} pts</span>` : ''}
                                ${this.settings.track_goals ? `<span>⚽ ${st.goals}</span>` : ''}
                                ${this.settings.track_assists ? `<span>🅰️ ${st.assists}</span>` : ''}
                            </span>
                        </div>
                    `).join('')}
                </div>
            `
            : '';

        return `
            <div class="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 sm:p-5 transition hover:border-slate-700">
                <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-extrabold uppercase px-2.5 py-0.5 rounded bg-slate-800 text-emerald-400">MW ${m.matchweek}</span>
                        ${this.statusBadge(m.status)}
                    </div>
                    <div class="text-xs text-slate-400">
                        Deadline: <span class="text-slate-300 font-medium">${this.formatDate(m.deadline)}</span>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-7 items-center gap-4 py-2">
                    <!-- Home Team -->
                    <div class="md:col-span-3 flex flex-col md:items-end text-left md:text-right">
                        <div class="flex items-center gap-2 md:flex-row-reverse">
                            <span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">HOME</span>
                            <span class="font-bold text-base text-white">${this.escapeHtml(m.home_team_name)}</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5">
                            ${m.home_players.map(p => `${this.escapeHtml(p.name)} (@${this.escapeHtml(p.efootball_username)})`).join(' & ')}
                        </p>
                    </div>

                    <!-- Score Pill -->
                    <div class="md:col-span-1 flex items-center justify-center">
                        <div class="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 font-mono-num text-xl font-extrabold text-white tracking-wider">
                            ${hasScore ? `${m.home_score} - ${m.away_score}` : 'vs'}
                        </div>
                    </div>

                    <!-- Away Team -->
                    <div class="md:col-span-3 flex flex-col md:items-start text-left">
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">AWAY</span>
                            <span class="font-bold text-base text-white">${this.escapeHtml(m.away_team_name)}</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5">
                            ${m.away_players.map(p => `${this.escapeHtml(p.name)} (@${this.escapeHtml(p.efootball_username)})`).join(' & ')}
                        </p>
                    </div>
                </div>

                ${statsHtml}

                ${actionHtml ? `<div class="mt-4 pt-3 border-t border-slate-800 flex justify-end">${actionHtml}</div>` : ''}
            </div>
        `;
    },

    // -----------------------------------------------------------------------
    // 3. Partner Preferences View (Drag-and-Drop + Up/Down Buttons)
    // -----------------------------------------------------------------------
    async loadPreferences() {
        const container = document.getElementById('preferences-list');
        try {
            this.preferencesList = await this.api('/api/preferences');
            this.renderPreferencesList();
        } catch (err) {
            container.innerHTML = `<p class="text-xs text-rose-400">${this.escapeHtml(err.message)}</p>`;
        }
    },

    renderPreferencesList() {
        const container = document.getElementById('preferences-list');
        if (!this.preferencesList.length) {
            container.innerHTML = `
                <div class="rounded-xl border border-slate-800 bg-slate-950 p-6 text-center text-sm text-slate-400">
                    No other players are registered yet.
                </div>
            `;
            return;
        }

        container.innerHTML = this.preferencesList.map((item, idx) => `
            <div draggable="true"
                data-index="${idx}"
                ondragstart="app.onPrefDragStart(event, ${idx})"
                ondragover="app.onPrefDragOver(event)"
                ondragleave="app.onPrefDragLeave(event)"
                ondrop="app.onPrefDrop(event, ${idx})"
                ondragend="app.onPrefDragEnd(event)"
                class="pref-item flex items-center justify-between gap-4 p-3.5 rounded-xl border border-slate-800 bg-slate-950/90 hover:border-slate-700 cursor-grab active:cursor-grabbing">
                <div class="flex items-center gap-3.5">
                    <span class="w-8 h-8 rounded-lg flex items-center justify-center font-mono-num font-extrabold text-xs ${idx === 0 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300'}">
                        #${idx + 1}
                    </span>
                    <div>
                        <p class="font-bold text-sm text-white">${this.escapeHtml(item.name)}</p>
                        <p class="text-xs text-slate-400 font-mono-num">@${this.escapeHtml(item.efootball_username)}</p>
                    </div>
                </div>
                <div class="flex items-center gap-1.5">
                    <button type="button" onclick="app.movePreference(${idx}, -1)" ${idx === 0 ? 'disabled' : ''}
                        class="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-bold text-slate-300 disabled:opacity-30">
                        &uarr;
                    </button>
                    <button type="button" onclick="app.movePreference(${idx}, 1)" ${idx === this.preferencesList.length - 1 ? 'disabled' : ''}
                        class="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-bold text-slate-300 disabled:opacity-30">
                        &darr;
                    </button>
                </div>
            </div>
        `).join('');
    },

    movePreference(index, delta) {
        const target = index + delta;
        if (target < 0 || target >= this.preferencesList.length) return;
        const temp = this.preferencesList[index];
        this.preferencesList[index] = this.preferencesList[target];
        this.preferencesList[target] = temp;
        this.renderPreferencesList();
    },

    onPrefDragStart(e, index) {
        this.draggedPrefIndex = index;
        e.currentTarget.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    },

    onPrefDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('drag-over');
    },

    onPrefDragLeave(e) {
        e.currentTarget.classList.remove('drag-over');
    },

    onPrefDrop(e, dropIndex) {
        e.preventDefault();
        e.currentTarget.classList.remove('drag-over');
        if (this.draggedPrefIndex === null || this.draggedPrefIndex === dropIndex) return;
        const moved = this.preferencesList.splice(this.draggedPrefIndex, 1)[0];
        this.preferencesList.splice(dropIndex, 0, moved);
        this.draggedPrefIndex = null;
        this.renderPreferencesList();
    },

    onPrefDragEnd(e) {
        e.currentTarget.classList.remove('dragging');
        document.querySelectorAll('.pref-item').forEach(el => el.classList.remove('drag-over'));
    },

    async savePreferences() {
        const rankings = this.preferencesList.map((item, idx) => ({
            ranked_user_id: item.ranked_user_id,
            rank_value: idx + 1,
        }));
        try {
            this.preferencesList = await this.api('/api/preferences', {
                method: 'PUT',
                body: JSON.stringify({ rankings }),
            });
            this.renderPreferencesList();
            this.toast('Partner preference rankings saved!', 'success');
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    // -----------------------------------------------------------------------
    // 4. My Team View
    // -----------------------------------------------------------------------
    async loadMyTeam() {
        const container = document.getElementById('my-team-container');
        try {
            const team = await this.api('/api/teams/my-team');
            const editable = (this.settings && this.settings.team_setup_open) || this.user.is_admin;

            container.innerHTML = `
                <div class="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 sm:p-8 space-y-6">
                    <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                        <div>
                            <span class="text-xs font-bold uppercase px-2.5 py-1 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                2v2 Paired Squad
                            </span>
                            <h2 class="text-2xl font-extrabold text-white mt-2">${this.escapeHtml(team.name)}</h2>
                        </div>
                        <div class="text-right">
                            <p class="text-xs text-slate-400">Team Captain</p>
                            <p class="text-sm font-bold text-amber-400">👑 ${this.escapeHtml(team.leader_name || 'Unassigned')}</p>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        ${[team.player1, team.player2].map(p => `
                            <div class="rounded-xl border ${team.leader_id === p.id ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-800 bg-slate-950/70'} p-4">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs font-bold uppercase text-slate-400">Squad Member</span>
                                    ${team.leader_id === p.id ? '<span class="text-[11px] font-bold text-amber-400">👑 Leader</span>' : ''}
                                </div>
                                <p class="text-base font-bold text-white mt-1">${this.escapeHtml(p.name)}</p>
                                <p class="text-xs font-mono-num text-emerald-400">@${this.escapeHtml(p.efootball_username)}</p>
                            </div>
                        `).join('')}
                    </div>

                    <form onsubmit="app.handleUpdateTeam(event)" class="space-y-4 pt-4 border-t border-slate-800">
                        <h3 class="text-sm font-bold uppercase tracking-wider text-slate-300">Customize Team Identity</h3>
                        <div>
                            <label class="block text-xs font-semibold text-slate-400 mb-1.5">Official Team Name</label>
                            <input id="my-team-name-input" type="text" required minlength="2" maxlength="120"
                                value="${this.escapeHtml(team.name)}" ${!editable ? 'disabled' : ''}
                                class="w-full rounded-xl bg-slate-950 border border-slate-800 px-4 py-2.5 text-sm text-white focus:border-emerald-400 focus:outline-none disabled:opacity-50" />
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-400 mb-1.5">Select Team Leader (Captain)</label>
                            <select id="my-team-leader-select" ${!editable ? 'disabled' : ''}
                                class="w-full rounded-xl bg-slate-950 border border-slate-800 px-4 py-2.5 text-sm text-white focus:border-emerald-400 focus:outline-none disabled:opacity-50">
                                <option value="${team.player1.id}" ${team.leader_id === team.player1.id ? 'selected' : ''}>
                                    ${this.escapeHtml(team.player1.name)} (@${this.escapeHtml(team.player1.efootball_username)})
                                </option>
                                <option value="${team.player2.id}" ${team.leader_id === team.player2.id ? 'selected' : ''}>
                                    ${this.escapeHtml(team.player2.name)} (@${this.escapeHtml(team.player2.efootball_username)})
                                </option>
                            </select>
                        </div>
                        ${editable ? `
                            <button type="submit" class="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition shadow-lg shadow-emerald-500/20">
                                Save Team Details
                            </button>
                        ` : `
                            <p class="text-xs text-amber-400">Team Setup is currently locked by the League Administrator.</p>
                        `}
                    </form>
                </div>
            `;
        } catch (err) {
            container.innerHTML = `<p class="text-sm text-rose-400">${this.escapeHtml(err.message)}</p>`;
        }
    },

    async handleUpdateTeam(e) {
        e.preventDefault();
        const name = document.getElementById('my-team-name-input').value.trim();
        const leaderId = parseInt(document.getElementById('my-team-leader-select').value, 10);

        try {
            await this.api('/api/teams/my-team', {
                method: 'PUT',
                body: JSON.stringify({ name, leader_id: leaderId }),
            });
            this.user = await this.api('/api/auth/me');
            this.updateNavigationUI();
            await this.loadMyTeam();
            this.toast('Team Name and Captain updated!', 'success');
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    // -----------------------------------------------------------------------
    // 5. All Fixtures View
    // -----------------------------------------------------------------------
    async loadAllFixtures() {
        const container = document.getElementById('all-fixtures-container');
        const filterEl = document.getElementById('fixtures-mw-filter');

        try {
            this.allMatchesCache = await this.api('/api/matches');
            if (!this.allMatchesCache.length) {
                filterEl.innerHTML = '';
                container.innerHTML = `
                    <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-8 text-center text-sm text-slate-400">
                        Season fixtures have not been generated yet.
                    </div>
                `;
                return;
            }

            const matchweeks = [...new Set(this.allMatchesCache.map(m => m.matchweek))].sort((a, b) => a - b);
            filterEl.innerHTML = [
                `<button onclick="app.setFixtureMwFilter('all')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition ${this.selectedFixtureMw === 'all' ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">All Weeks</button>`,
                ...matchweeks.map(mw => `
                    <button onclick="app.setFixtureMwFilter(${mw})" class="px-3 py-1.5 rounded-lg text-xs font-bold transition ${this.selectedFixtureMw === mw ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}">
                        MW ${mw}
                    </button>
                `),
            ].join('');

            this.renderAllFixturesList();
        } catch (err) {
            container.innerHTML = `<p class="text-xs text-rose-400">${this.escapeHtml(err.message)}</p>`;
        }
    },

    setFixtureMwFilter(mw) {
        this.selectedFixtureMw = mw;
        this.loadAllFixtures();
    },

    renderAllFixturesList() {
        const container = document.getElementById('all-fixtures-container');
        const filtered = this.selectedFixtureMw === 'all'
            ? this.allMatchesCache
            : this.allMatchesCache.filter(m => m.matchweek === this.selectedFixtureMw);

        const grouped = {};
        filtered.forEach(m => {
            if (!grouped[m.matchweek]) grouped[m.matchweek] = [];
            grouped[m.matchweek].push(m);
        });

        container.innerHTML = Object.keys(grouped)
            .sort((a, b) => Number(a) - Number(b))
            .map(mw => `
                <div class="space-y-3">
                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                        <h3 class="text-base font-extrabold text-emerald-400 uppercase tracking-wider">
                            Matchweek ${mw}
                            ${this.settings && Number(mw) === this.settings.current_matchweek ? '<span class="ml-2 text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">Current Week</span>' : ''}
                        </h3>
                        <span class="text-xs text-slate-400">Friday Midnight Deadline: ${this.formatDate(grouped[mw][0].deadline)}</span>
                    </div>
                    <div class="space-y-3">
                        ${grouped[mw].map(m => this.renderMatchCard(m, false)).join('')}
                    </div>
                </div>
            `).join('');
    },

    // -----------------------------------------------------------------------
    // 6. Standings View (Premier League Table)
    // -----------------------------------------------------------------------
    async loadStandings() {
        const tbody = document.getElementById('standings-tbody');
        try {
            const rows = await this.api('/api/standings');
            if (!rows.length) {
                tbody.innerHTML = `
                    <tr><td colspan="10" class="py-8 text-center text-slate-400">No teams formed yet.</td></tr>
                `;
                return;
            }

            tbody.innerHTML = rows.map(r => {
                const isMyTeam = this.user && this.user.team_id === r.team_id;
                const posBadge = r.position === 1
                    ? 'bg-amber-400 text-slate-950 font-black'
                    : r.position <= 3
                        ? 'bg-emerald-500/20 text-emerald-300 font-bold'
                        : 'bg-slate-800 text-slate-400';

                const gdStr = r.goal_difference > 0 ? `+${r.goal_difference}` : `${r.goal_difference}`;
                return `
                    <tr class="${isMyTeam ? 'bg-emerald-500/10' : 'hover:bg-slate-800/40'} transition">
                        <td class="py-3.5 px-4 text-center">
                            <span class="inline-flex w-7 h-7 items-center justify-center rounded-lg text-xs font-mono-num ${posBadge}">
                                ${r.position}
                            </span>
                        </td>
                        <td class="py-3.5 px-4">
                            <div class="font-bold text-white flex items-center gap-2">
                                ${this.escapeHtml(r.team_name)}
                                ${isMyTeam ? '<span class="text-[10px] uppercase px-1.5 py-0.5 rounded bg-emerald-500 text-slate-950 font-extrabold">You</span>' : ''}
                            </div>
                            <div class="text-xs text-slate-400 mt-0.5">${r.members.map(m => this.escapeHtml(m)).join(' • ')}</div>
                        </td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-slate-300">${r.played}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-emerald-400 font-semibold">${r.won}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-amber-300">${r.drawn}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-rose-400">${r.lost}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-slate-300">${r.goals_for}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-slate-300">${r.goals_against}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num font-bold ${r.goal_difference >= 0 ? 'text-slate-200' : 'text-rose-400'}">${gdStr}</td>
                        <td class="py-3.5 px-4 text-center font-mono-num text-base font-extrabold text-emerald-400">${r.points}</td>
                    </tr>
                `;
            }).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="10" class="py-6 text-center text-rose-400">${this.escapeHtml(err.message)}</td></tr>`;
        }
    },

    // -----------------------------------------------------------------------
    // 7. Team Directory View
    // -----------------------------------------------------------------------
    async loadTeamDirectory() {
        const grid = document.getElementById('team-directory-grid');
        try {
            const teams = await this.api('/api/teams');
            if (!teams.length) {
                grid.innerHTML = `
                    <div class="col-span-full rounded-2xl border border-slate-800 bg-slate-900/70 p-8 text-center text-sm text-slate-400">
                        No teams have been paired yet. Waiting for the Admin to run matchmaking.
                    </div>
                `;
                return;
            }

            grid.innerHTML = teams.map(t => `
                <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 flex flex-col justify-between hover:border-slate-700 transition">
                    <div>
                        <div class="flex items-center justify-between gap-2 mb-3">
                            <span class="text-xs font-mono-num font-bold px-2 py-0.5 rounded bg-slate-800 text-emerald-400">Club #${t.id}</span>
                            <span class="text-xs font-semibold text-amber-400">👑 Captain: ${this.escapeHtml(t.leader_name || 'TBD')}</span>
                        </div>
                        <h3 class="text-lg font-extrabold text-white mb-4">${this.escapeHtml(t.name)}</h3>
                    </div>
                    <div class="space-y-2 pt-3 border-t border-slate-800/80 text-xs">
                        ${[t.player1, t.player2].map(p => `
                            <div class="flex items-center justify-between rounded-xl bg-slate-950/70 px-3 py-2 border border-slate-800/60">
                                <div>
                                    <p class="font-bold text-slate-200">${this.escapeHtml(p.name)}</p>
                                    <p class="font-mono-num text-slate-400">@${this.escapeHtml(p.efootball_username)}</p>
                                </div>
                                ${t.leader_id === p.id ? '<span class="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold text-[10px] uppercase">Leader</span>' : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');
        } catch (err) {
            grid.innerHTML = `<p class="text-xs text-rose-400">${this.escapeHtml(err.message)}</p>`;
        }
    },

    // -----------------------------------------------------------------------
    // 8. Player Stats (MVP Leaderboard) View
    // -----------------------------------------------------------------------
    async loadLeaderboard() {
        const thead = document.getElementById('leaderboard-thead');
        const tbody = document.getElementById('leaderboard-tbody');
        const s = this.settings || { track_points: true, track_goals: true, track_assists: true };

        thead.innerHTML = `
            <tr class="border-b border-slate-800 bg-slate-950/60 text-xs font-bold uppercase tracking-wider text-slate-400">
                <th class="py-3.5 px-4 w-16 text-center">Rank</th>
                <th class="py-3.5 px-4">Player</th>
                <th class="py-3.5 px-4">2v2 Team</th>
                <th class="py-3.5 px-3 text-center">Matches</th>
                ${s.track_points ? '<th class="py-3.5 px-4 text-center text-emerald-400">Total Points</th><th class="py-3.5 px-3 text-center">Avg Pts</th>' : ''}
                ${s.track_goals ? '<th class="py-3.5 px-3 text-center">Goals</th>' : ''}
                ${s.track_assists ? '<th class="py-3.5 px-3 text-center">Assists</th>' : ''}
            </tr>
        `;

        try {
            const rows = await this.api('/api/stats/leaderboard');
            if (!rows.length) {
                tbody.innerHTML = `<tr><td colspan="8" class="py-8 text-center text-slate-400">No players registered yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = rows.map(r => {
                const isMe = this.user && this.user.id === r.user_id;
                const badge = r.rank === 1
                    ? 'bg-amber-400 text-slate-950 font-black'
                    : r.rank <= 3
                        ? 'bg-emerald-500/20 text-emerald-300 font-bold'
                        : 'bg-slate-800 text-slate-400';

                return `
                    <tr class="${isMe ? 'bg-emerald-500/10' : 'hover:bg-slate-800/40'} transition">
                        <td class="py-3.5 px-4 text-center">
                            <span class="inline-flex w-7 h-7 items-center justify-center rounded-lg text-xs font-mono-num ${badge}">
                                ${r.rank}
                            </span>
                        </td>
                        <td class="py-3.5 px-4">
                            <div class="font-bold text-white">${this.escapeHtml(r.name)}</div>
                            <div class="text-xs font-mono-num text-slate-400">@${this.escapeHtml(r.efootball_username)}</div>
                        </td>
                        <td class="py-3.5 px-4 text-xs text-slate-300">${this.escapeHtml(r.team_name || 'Unassigned')}</td>
                        <td class="py-3.5 px-3 text-center font-mono-num text-slate-300">${r.matches_played}</td>
                        ${s.track_points ? `
                            <td class="py-3.5 px-4 text-center font-mono-num text-base font-extrabold text-emerald-400">${r.total_points.toLocaleString()}</td>
                            <td class="py-3.5 px-3 text-center font-mono-num text-slate-300">${r.avg_points.toLocaleString()}</td>
                        ` : ''}
                        ${s.track_goals ? `<td class="py-3.5 px-3 text-center font-mono-num font-bold text-blue-400">${r.goals}</td>` : ''}
                        ${s.track_assists ? `<td class="py-3.5 px-3 text-center font-mono-num font-bold text-amber-300">${r.assists}</td>` : ''}
                    </tr>
                `;
            }).join('');
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-rose-400">${this.escapeHtml(err.message)}</td></tr>`;
        }
    },

    // -----------------------------------------------------------------------
    // 9. Score Submission & Away Verification Modals
    // -----------------------------------------------------------------------
    openScoreModal(match, mode = 'home_submit') {
        document.getElementById('modal-match-id').value = match.id;
        document.getElementById('modal-mode').value = mode;
        document.getElementById('modal-home-team-name').textContent = match.home_team_name;
        document.getElementById('modal-away-team-name').textContent = match.away_team_name;
        document.getElementById('modal-home-score').value = match.home_score !== null ? match.home_score : 0;
        document.getElementById('modal-away-score').value = match.away_score !== null ? match.away_score : 0;

        const titleEl = document.getElementById('modal-score-title');
        const statusWrap = document.getElementById('modal-admin-status-wrap');
        if (mode === 'admin_override') {
            titleEl.textContent = `Admin Retroactive Override — Match #${match.id} (MW ${match.matchweek})`;
            statusWrap.classList.remove('hidden');
            document.getElementById('modal-admin-status').value = match.status || 'accepted';
        } else {
            titleEl.textContent = `Submit Match Score & Player Stats — MW ${match.matchweek}`;
            statusWrap.classList.add('hidden');
        }

        const existingMap = {};
        (match.player_stats || []).forEach(st => {
            existingMap[st.user_id] = st;
        });

        const allPlayers = [
            ...match.home_players.map(p => ({ ...p, side: 'HOME', teamName: match.home_team_name })),
            ...match.away_players.map(p => ({ ...p, side: 'AWAY', teamName: match.away_team_name })),
        ];

        const s = this.settings || { track_points: true, track_goals: true, track_assists: true };
        const isAdminMode = mode === 'admin_override';

        const rowsContainer = document.getElementById('modal-player-stats-rows');
        rowsContainer.innerHTML = allPlayers.map(p => {
            const st = existingMap[p.id] || { total_points: 0, goals: 0, assists: 0 };
            return `
                <div class="rounded-xl border border-slate-800 bg-slate-950/80 p-3 grid grid-cols-1 sm:grid-cols-12 items-center gap-3" data-stat-user-id="${p.id}">
                    <div class="sm:col-span-5">
                        <span class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${p.side === 'HOME' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-blue-500/15 text-blue-400'}">${p.side}</span>
                        <span class="font-bold text-xs text-white ml-1">${this.escapeHtml(p.name)}</span>
                        <p class="text-[11px] font-mono-num text-slate-400">@${this.escapeHtml(p.efootball_username)}</p>
                    </div>
                    <div class="sm:col-span-7 grid grid-cols-3 gap-2">
                        <div>
                            <label class="block text-[10px] uppercase text-slate-400 mb-0.5">Points (1000s)</label>
                            <input type="number" min="0" step="1" data-field="total_points" value="${st.total_points}"
                                ${(!s.track_points && !isAdminMode) ? 'disabled' : ''}
                                class="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs font-mono-num text-white disabled:opacity-40" />
                        </div>
                        <div>
                            <label class="block text-[10px] uppercase text-slate-400 mb-0.5">Goals</label>
                            <input type="number" min="0" step="1" data-field="goals" value="${st.goals}"
                                ${(!s.track_goals && !isAdminMode) ? 'disabled' : ''}
                                class="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs font-mono-num text-white disabled:opacity-40" />
                        </div>
                        <div>
                            <label class="block text-[10px] uppercase text-slate-400 mb-0.5">Assists</label>
                            <input type="number" min="0" step="1" data-field="assists" value="${st.assists}"
                                ${(!s.track_assists && !isAdminMode) ? 'disabled' : ''}
                                class="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs font-mono-num text-white disabled:opacity-40" />
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('modal-score').classList.remove('hidden');
    },

    closeScoreModal() {
        document.getElementById('modal-score').classList.add('hidden');
    },

    async handleScoreModalSubmit(e) {
        e.preventDefault();
        const matchId = parseInt(document.getElementById('modal-match-id').value, 10);
        const mode = document.getElementById('modal-mode').value;
        const homeScore = parseInt(document.getElementById('modal-home-score').value, 10);
        const awayScore = parseInt(document.getElementById('modal-away-score').value, 10);

        const playerStats = [];
        document.querySelectorAll('#modal-player-stats-rows [data-stat-user-id]').forEach(row => {
            const userId = parseInt(row.getAttribute('data-stat-user-id'), 10);
            const totalPoints = parseInt(row.querySelector('[data-field="total_points"]').value || '0', 10);
            const goals = parseInt(row.querySelector('[data-field="goals"]').value || '0', 10);
            const assists = parseInt(row.querySelector('[data-field="assists"]').value || '0', 10);
            playerStats.push({ user_id: userId, total_points: totalPoints, goals, assists });
        });

        try {
            if (mode === 'admin_override') {
                const statusVal = document.getElementById('modal-admin-status').value;
                await this.api(`/api/admin/matches/${matchId}/override`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        home_score: homeScore,
                        away_score: awayScore,
                        status: statusVal,
                        player_stats: playerStats,
                    }),
                });
                this.toast(`Match #${matchId} retroactively updated by Admin.`, 'success');
                this.closeScoreModal();
                await this.loadAdminDashboard();
            } else {
                await this.api(`/api/matches/${matchId}/submit`, {
                    method: 'POST',
                    body: JSON.stringify({
                        home_score: homeScore,
                        away_score: awayScore,
                        player_stats: playerStats,
                    }),
                });
                this.toast('Match score & stats submitted! Waiting for Away team verification.', 'success');
                this.closeScoreModal();
                await this.loadDashboard();
            }
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    openVerifyModal(match) {
        const body = document.getElementById('modal-verify-body');
        body.innerHTML = `
            <div class="rounded-xl border border-slate-800 bg-slate-950 p-4 text-center">
                <p class="text-xs text-slate-400 uppercase font-bold mb-2">Matchweek ${match.matchweek} Submitted Score</p>
                <div class="flex items-center justify-center gap-4 text-lg font-extrabold text-white">
                    <span>${this.escapeHtml(match.home_team_name)}</span>
                    <span class="px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 font-mono-num text-emerald-400">${match.home_score} - ${match.away_score}</span>
                    <span>${this.escapeHtml(match.away_team_name)}</span>
                </div>
            </div>

            <div class="space-y-2">
                <p class="text-xs font-bold uppercase text-slate-400">Submitted Individual Player Stats</p>
                ${(match.player_stats || []).map(st => `
                    <div class="flex items-center justify-between rounded-lg bg-slate-950 px-3 py-2 border border-slate-800 text-xs">
                        <span class="font-semibold text-white">${this.escapeHtml(st.user_name)} <span class="text-slate-500">@${this.escapeHtml(st.efootball_username)}</span></span>
                        <span class="font-mono-num text-slate-300">
                            <strong class="text-emerald-400">${st.total_points} pts</strong> • ⚽ ${st.goals} • 🅰️ ${st.assists}
                        </span>
                    </div>
                `).join('')}
            </div>

            <div class="grid grid-cols-2 gap-3 pt-3 border-t border-slate-800">
                <button onclick="app.submitVerification(${match.id}, 'dispute')"
                    class="py-3 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-300 font-bold text-xs transition">
                    🚩 Dispute Result (Flag Admin)
                </button>
                <button onclick="app.submitVerification(${match.id}, 'accept')"
                    class="py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition shadow-lg shadow-emerald-500/20">
                    ✓ Accept & Finalize Result
                </button>
            </div>
        `;
        document.getElementById('modal-verify').classList.remove('hidden');
    },

    closeVerifyModal() {
        document.getElementById('modal-verify').classList.add('hidden');
    },

    async submitVerification(matchId, action) {
        try {
            await this.api(`/api/matches/${matchId}/verify`, {
                method: 'POST',
                body: JSON.stringify({ action }),
            });
            this.closeVerifyModal();
            if (action === 'accept') {
                this.toast('Match score accepted! Standings and MVP stats updated.', 'success');
            } else {
                this.toast('Match flagged as Disputed for Admin review.', 'info');
            }
            await this.loadDashboard();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    // -----------------------------------------------------------------------
    // 10. Admin Control Center View
    // -----------------------------------------------------------------------
    async loadAdminDashboard() {
        try {
            const [settings, users, disputes, allMatches] = await Promise.all([
                this.api('/api/admin/settings'),
                this.api('/api/admin/users'),
                this.api('/api/admin/disputes'),
                this.api('/api/matches'),
            ]);
            this.settings = settings;
            this.allMatchesCache = allMatches;
            this.updateNavigationUI();

            this.renderAdminToggles(settings);
            this.renderAdminEngineControls(settings, users);
            this.renderAdminDisputes(disputes);
            this.renderAdminMatchesFilterAndTable();
            this.renderAdminUsersTable(users);
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    renderAdminToggles(s) {
        const items = [
            { key: 'registration_open', label: '1. Registration Phase Open', desc: 'Allow new players to register accounts' },
            { key: 'preferences_open', label: '2. Partner Preference Phase Open', desc: 'Allow players to rank preferred 2v2 partners' },
            { key: 'team_setup_open', label: '3. Team Setup Phase Open', desc: 'Allow paired squads to edit Team Name & Leader' },
            { key: 'season_live', label: '4. Live Season Active', desc: 'Enable weekly match score submissions & verifications' },
            { key: 'track_points', label: 'Track Player Total Points (1000s)', desc: 'Collect & display individual match points' },
            { key: 'track_goals', label: 'Track Player Goals', desc: 'Collect & display individual goals scored' },
            { key: 'track_assists', label: 'Track Player Assists', desc: 'Collect & display individual assists' },
        ];

        const container = document.getElementById('admin-toggles-container');
        container.innerHTML = items.map(item => `
            <div class="flex items-center justify-between gap-4 p-3 rounded-xl bg-slate-950/70 border border-slate-800">
                <div>
                    <p class="text-sm font-bold text-white">${item.label}</p>
                    <p class="text-xs text-slate-400">${item.desc}</p>
                </div>
                <button onclick="app.toggleSystemSetting('${item.key}', ${!s[item.key]})"
                    class="px-3.5 py-1.5 rounded-lg text-xs font-extrabold uppercase transition ${s[item.key] ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-white'}">
                    ${s[item.key] ? 'ON' : 'OFF'}
                </button>
            </div>
        `).join('');
    },

    async toggleSystemSetting(key, newValue) {
        try {
            this.settings = await this.api('/api/admin/settings', {
                method: 'PUT',
                body: JSON.stringify({ [key]: newValue }),
            });
            this.toast(`Updated ${key} = ${newValue}`, 'success');
            await this.loadAdminDashboard();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    renderAdminEngineControls(s, users) {
        const nonAdminPlayers = users.filter(u => !u.is_admin);
        const container = document.getElementById('admin-engine-controls');

        container.innerHTML = `
            <!-- Step A: Partner Matchmaking -->
            <div class="rounded-xl bg-slate-950/80 border border-slate-800 p-4 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase text-emerald-400">Step A: 2v2 Matchmaking Algorithm</span>
                    <span class="text-xs text-slate-400">${nonAdminPlayers.length} Eligible Players (${nonAdminPlayers.length % 2 === 0 ? 'Even ✓' : 'Odd ⚠️'})</span>
                </div>
                <p class="text-xs text-slate-400">
                    Runs Irving's Stable Roommate / Blossom Minimum-Weight Matching to pair players based on mutual highest ranks.
                </p>
                <button onclick="app.adminRunMatchmaking()"
                    class="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition shadow-lg shadow-emerald-500/20">
                    Run Partner Matchmaking & Pair Teams
                </button>
            </div>

            <!-- Step B: Fixture Generator -->
            <div class="rounded-xl bg-slate-950/80 border border-slate-800 p-4 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase text-blue-400">Step B: Season Fixture Generator</span>
                    <div class="flex items-center gap-2">
                        <label class="text-xs text-slate-400">Format Multiplier:</label>
                        <select id="admin-rr-multiplier" class="rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1 text-xs text-white font-bold">
                            <option value="1" ${s.round_robin_multiplier === 1 ? 'selected' : ''}>1x (Single Round-Robin)</option>
                            <option value="2" ${s.round_robin_multiplier === 2 ? 'selected' : ''}>2x (Home & Away)</option>
                            <option value="3" ${s.round_robin_multiplier === 3 ? 'selected' : ''}>3x (Triple Round-Robin)</option>
                            <option value="4" ${s.round_robin_multiplier === 4 ? 'selected' : ''}>4x (Quadruple Round-Robin)</option>
                        </select>
                    </div>
                </div>
                <button onclick="app.adminGenerateFixtures()"
                    class="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition shadow-lg shadow-blue-600/20">
                    Generate Entire Season Fixtures
                </button>
            </div>

            <!-- Step C: Active Matchweek & Friday Auto-Draw -->
            <div class="rounded-xl bg-slate-950/80 border border-slate-800 p-4 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase text-amber-400">Step C: Weekly Cycle & Friday Auto-Draws</span>
                    <div class="flex items-center gap-2">
                        <label class="text-xs text-slate-400">Active Matchweek:</label>
                        <input id="admin-current-mw-input" type="number" min="1" value="${s.current_matchweek}"
                            class="w-16 rounded-lg bg-slate-900 border border-slate-700 px-2 py-1 text-xs font-mono-num text-center text-white" />
                        <button onclick="app.adminUpdateMatchweek()" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-bold text-emerald-400">
                            Set MW
                        </button>
                    </div>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <button onclick="app.adminTriggerAutoDraw(false)"
                        class="py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition">
                        Check Expired Deadlines
                    </button>
                    <button onclick="app.adminTriggerAutoDraw(true)"
                        class="py-2 px-3 rounded-xl bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-xs font-bold text-purple-300 transition">
                        Force 0-0 Unplayed in MW ${s.current_matchweek}
                    </button>
                </div>
            </div>
        `;
    },

    async adminRunMatchmaking() {
        try {
            const res = await this.api('/api/admin/matchmaking/run', { method: 'POST' });
            this.toast(res.detail, 'success');
            await this.loadAdminDashboard();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    async adminGenerateFixtures() {
        const mult = parseInt(document.getElementById('admin-rr-multiplier').value, 10);
        try {
            const res = await this.api('/api/admin/fixtures/generate', {
                method: 'POST',
                body: JSON.stringify({ round_robin_multiplier: mult }),
            });
            this.toast(res.detail, 'success');
            await this.loadAdminDashboard();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    async adminUpdateMatchweek() {
        const mw = parseInt(document.getElementById('admin-current-mw-input').value, 10);
        await this.toggleSystemSetting('current_matchweek', mw);
    },

    async adminTriggerAutoDraw(forceCurrentMw) {
        try {
            const mw = this.settings ? this.settings.current_matchweek : 1;
            const query = forceCurrentMw ? `?matchweek=${mw}&force_matchweek=true` : '';
            const res = await this.api(`/api/admin/matches/auto-draw${query}`, { method: 'POST' });
            this.toast(res.detail, 'info');
            await this.loadAdminDashboard();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },

    renderAdminDisputes(disputes) {
        document.getElementById('admin-dispute-badge').textContent = disputes.length;
        const listEl = document.getElementById('admin-disputes-list');

        if (!disputes.length) {
            listEl.innerHTML = `<p class="text-xs text-slate-500">No disputed matches requiring action.</p>`;
            return;
        }

        listEl.innerHTML = disputes.map(m => `
            <div class="rounded-xl border border-rose-500/40 bg-rose-500/5 p-4 flex flex-wrap items-center justify-between gap-4">
                <div>
                    <span class="text-xs font-bold text-rose-400">Match #${m.id} • MW ${m.matchweek}</span>
                    <p class="text-sm font-bold text-white mt-0.5">
                        ${this.escapeHtml(m.home_team_name)} <span class="text-emerald-400 font-mono-num">${m.home_score} - ${m.away_score}</span> ${this.escapeHtml(m.away_team_name)}
                    </p>
                </div>
                <button onclick='app.openScoreModal(${JSON.stringify(m)}, "admin_override")'
                    class="px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold text-xs transition">
                    Resolve & Override Score
                </button>
            </div>
        `).join('');
    },

    renderAdminMatchesFilterAndTable() {
        const select = document.getElementById('admin-match-mw-filter');
        const currentVal = select.value || 'all';
        const mws = [...new Set(this.allMatchesCache.map(m => m.matchweek))].sort((a, b) => a - b);

        select.innerHTML = `<option value="all">All Matchweeks (${this.allMatchesCache.length} Matches)</option>` +
            mws.map(mw => `<option value="${mw}" ${String(mw) === String(currentVal) ? 'selected' : ''}>Matchweek ${mw}</option>`).join('');

        this.renderAdminMatchesTable();
    },

    renderAdminMatchesTable() {
        const filterVal = document.getElementById('admin-match-mw-filter').value;
        const container = document.getElementById('admin-matches-list');

        const matches = filterVal === 'all'
            ? this.allMatchesCache
            : this.allMatchesCache.filter(m => String(m.matchweek) === String(filterVal));

        if (!matches.length) {
            container.innerHTML = `<p class="text-xs text-slate-500">No fixtures generated yet.</p>`;
            return;
        }

        container.innerHTML = matches.map(m => `
            <div class="rounded-xl border border-slate-800 bg-slate-950/80 p-3.5 flex flex-wrap items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                    <span class="text-xs font-mono-num font-bold px-2 py-1 rounded bg-slate-900 text-slate-300">MW ${m.matchweek}</span>
                    <div>
                        <p class="text-sm font-bold text-white">
                            ${this.escapeHtml(m.home_team_name)}
                            <span class="mx-1.5 font-mono-num text-emerald-400">${m.home_score !== null ? `${m.home_score} - ${m.away_score}` : 'vs'}</span>
                            ${this.escapeHtml(m.away_team_name)}
                        </p>
                        <div class="mt-1">${this.statusBadge(m.status)}</div>
                    </div>
                </div>
                <button onclick='app.openScoreModal(${JSON.stringify(m)}, "admin_override")'
                    class="px-3.5 py-2 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 font-bold text-xs transition">
                    Edit Score & Stats
                </button>
            </div>
        `).join('');
    },

    renderAdminUsersTable(users) {
        const nonAdminCount = users.filter(u => !u.is_admin).length;
        document.getElementById('admin-user-count').textContent = `${nonAdminCount} Registered Players • ${users.length} Total Accounts`;

        const tbody = document.getElementById('admin-users-tbody');
        tbody.innerHTML = users.map(u => `
            <tr class="hover:bg-slate-800/40">
                <td class="py-3 px-4 font-mono-num text-xs text-slate-400">#${u.id}</td>
                <td class="py-3 px-4 font-bold text-white">${this.escapeHtml(u.name)}</td>
                <td class="py-3 px-4 font-mono-num text-emerald-400">@${this.escapeHtml(u.efootball_username)}</td>
                <td class="py-3 px-4">
                    ${u.is_admin
                        ? '<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-xs font-bold">Admin</span>'
                        : '<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-xs">Player</span>'}
                </td>
                <td class="py-3 px-4 text-xs text-slate-300">${this.escapeHtml(u.team_name || '—')}</td>
                <td class="py-3 px-4 text-right">
                    ${!u.is_admin ? `
                        <button onclick="app.adminDeleteUser(${u.id}, '${this.escapeHtml(u.name)}')"
                            class="px-3 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/30 border border-rose-500/30 text-rose-300 text-xs font-semibold transition">
                            Delete
                        </button>
                    ` : '<span class="text-xs text-slate-600">Protected</span>'}
                </td>
            </tr>
        `).join('');
    },

    async adminDeleteUser(userId, name) {
        try {
            const res = await this.api(`/api/admin/users/${userId}`, { method: 'DELETE' });
            this.toast(res.detail || `Deleted ${name}`, 'info');
            await this.loadAdminDashboard();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    },
};

window.addEventListener('DOMContentLoaded', () => app.init());

