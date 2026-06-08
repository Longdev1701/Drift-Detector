// ── State ──
let currentPageA = 1, currentPageB = 1;
let searchTimerA, searchTimerB;

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadOverview();
    loadLR();
    loadCandidates();

    document.getElementById('search-a').addEventListener('input', () => {
        clearTimeout(searchTimerA);
        searchTimerA = setTimeout(() => { currentPageA = 1; loadCustomers('a'); }, 300);
    });
    document.getElementById('search-b').addEventListener('input', () => {
        clearTimeout(searchTimerB);
        searchTimerB = setTimeout(() => { currentPageB = 1; loadCustomers('b'); }, 300);
    });
    document.getElementById('branch-filter-a').addEventListener('change', () => { currentPageA = 1; loadCustomers('a'); });
    document.getElementById('branch-filter-b').addEventListener('change', () => { currentPageB = 1; loadCustomers('b'); });
    
    document.getElementById('lr-threshold').addEventListener('input', () => {
        updateThresholdLabels();
        loadLR();
        loadCandidates();
    });
    updateThresholdLabels();
});

// ── Helper ──
function updateThresholdLabels() {
    const val = getThreshold();
    const ids = ['cand-lr-title', 'cand-lr-desc', 'mig-lr-desc'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    });
}
function getThreshold() {
    return document.getElementById('lr-threshold').value || 0.70;
}

// ── Tabs ──
function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = document.getElementById('tab-' + tab.dataset.tab);
            target.classList.add('active');
            if (tab.dataset.tab === 'site-a') loadCustomers('a');
            if (tab.dataset.tab === 'site-b') loadCustomers('b');
            if (tab.dataset.tab === 'drift') loadLR();
            if (tab.dataset.tab === 'migration') loadCandidates();
        });
    });
}

// ── API Helper ──
async function api(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
}

// ── Overview ──
async function loadOverview() {
    const d = await api('/api/overview');
    const grid = document.getElementById('stats-grid');
    grid.innerHTML = `
        <div class="stat-card glow-a">
            <div class="label">Site A — Customers</div>
            <div class="value blue">${d.site_a_customers.toLocaleString()}</div>
            <div class="sub">Branch A: ${d.site_a_by_branch?.A || 0} | Branch B: ${d.site_a_by_branch?.B || 0}</div>
        </div>
        <div class="stat-card glow-b">
            <div class="label">Site B — Customers</div>
            <div class="value purple">${d.site_b_customers.toLocaleString()}</div>
            <div class="sub">Branch A: ${d.site_b_by_branch?.A || 0} | Branch B: ${d.site_b_by_branch?.B || 0}</div>
        </div>
        <div class="stat-card glow-a">
            <div class="label">Site A — Transactions</div>
            <div class="value blue">${d.site_a_transactions.toLocaleString()}</div>
            <div class="sub">Stored on bank_site_a:5431</div>
        </div>
        <div class="stat-card glow-b">
            <div class="label">Site B — Transactions</div>
            <div class="value purple">${d.site_b_transactions.toLocaleString()}</div>
            <div class="sub">Stored on bank_site_b:5433</div>
        </div>`;
}

// ── Customers ──
async function loadCustomers(site) {
    const page = site === 'a' ? currentPageA : currentPageB;
    const search = document.getElementById(`search-${site}`).value;
    const branch = document.getElementById(`branch-filter-${site}`).value;
    const params = new URLSearchParams({ site, page, per_page: 50, search, branch });
    const d = await api(`/api/customers?${params}`);

    const tbody = document.querySelector(`#table-${site} tbody`);
    tbody.innerHTML = d.customers.map(c => `
        <tr>
            <td>${c.customerid}</td>
            <td><strong>${c.fullname}</strong></td>
            <td style="color:var(--text-dim)">${c.email}</td>
            <td>${c.phone}</td>
            <td><span class="badge badge-${c.homebranchid.toLowerCase()}">${c.homebranchid}</span></td>
            <td>${c.account_type}</td>
            <td>$${Number(c.account_balance).toLocaleString('en',{minimumFractionDigits:2})}</td>
            <td><button class="btn btn-view" onclick="viewCustomer(${c.customerid})">View TX</button></td>
        </tr>
    `).join('');

    renderPagination(site, d.page, d.total_pages, d.total);
}

function renderPagination(site, page, totalPages, total) {
    const el = document.getElementById(`pagination-${site}`);
    if (totalPages <= 1) { el.innerHTML = `<span class="info">${total} customers</span>`; return; }

    let html = `<span class="info">Page ${page}/${totalPages} (${total} total)</span>`;
    if (page > 1) html += `<button onclick="goPage('${site}',${page-1})">◀ Prev</button>`;

    const start = Math.max(1, page - 2), end = Math.min(totalPages, page + 2);
    for (let i = start; i <= end; i++) {
        html += `<button class="${i===page?'active':''}" onclick="goPage('${site}',${i})">${i}</button>`;
    }
    if (page < totalPages) html += `<button onclick="goPage('${site}',${page+1})">Next ▶</button>`;
    el.innerHTML = html;
}

function goPage(site, page) {
    if (site === 'a') currentPageA = page; else currentPageB = page;
    loadCustomers(site);
}

// ── Customer Detail Modal ──
async function viewCustomer(cid) {
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';
    overlay.classList.add('show');

    const d = await api(`/api/customer/${cid}/transactions`);
    const c = d.customer;
    if (!c) { content.innerHTML = '<p>Customer not found</p>'; return; }

    const day30A = d.site_a.filter(t => t.workload_day === 30);
    const day30B = d.site_b.filter(t => t.workload_day === 30);
    const day30AtmA = day30A.filter(t => t.atm_branchid === 'A').length + day30B.filter(t => t.atm_branchid === 'A').length;
    const day30AtmB = day30A.filter(t => t.atm_branchid === 'B').length + day30B.filter(t => t.atm_branchid === 'B').length;
    
    const localDay30 = c.homebranchid === 'A' ? day30AtmA : day30AtmB;
    const remoteDay30 = c.homebranchid === 'A' ? day30AtmB : day30AtmA;
    const totalDay30 = localDay30 + remoteDay30;
    const remotePctDay30 = totalDay30 > 0 ? ((remoteDay30 / totalDay30) * 100).toFixed(1) : '0.0';

    const txRowsA = d.site_a.map(t => `<tr>
        <td>${t.txid}</td><td><span class="badge badge-${t.atm_branchid.toLowerCase()}">${t.atm_branchid}</span></td>
        <td>$${Number(t.amount).toLocaleString('en',{minimumFractionDigits:2})}</td>
        <td style="color:var(--text-dim)">${t.txdate?.slice(0,19)}</td><td>Day ${t.workload_day}</td>
        <td><button class="btn btn-sm" style="padding:2px 6px;background:var(--red);color:white;border:none;border-radius:4px;cursor:pointer" onclick="delTx(${t.txid}, 'a', ${cid})">✕</button></td>
    </tr>`).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-dim)">No transactions</td></tr>';

    const txRowsB = d.site_b.map(t => `<tr>
        <td>${t.txid}</td><td><span class="badge badge-${t.atm_branchid.toLowerCase()}">${t.atm_branchid}</span></td>
        <td>$${Number(t.amount).toLocaleString('en',{minimumFractionDigits:2})}</td>
        <td style="color:var(--text-dim)">${t.txdate?.slice(0,19)}</td><td>Day ${t.workload_day}</td>
        <td><button class="btn btn-sm" style="padding:2px 6px;background:var(--red);color:white;border:none;border-radius:4px;cursor:pointer" onclick="delTx(${t.txid}, 'b', ${cid})">✕</button></td>
    </tr>`).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-dim)">No transactions</td></tr>';

    content.innerHTML = `
        <h2>${c.fullname}</h2>
        <p style="color:var(--text-dim)">Customer #${c.customerid}</p>
        <div class="cust-info">
            <div><span class="label">Email:</span> ${c.email}</div>
            <div><span class="label">Phone:</span> ${c.phone}</div>
            <div><span class="label">Address:</span> ${c.address || 'N/A'}</div>
            <div><span class="label">Account:</span> ${c.account_type}</div>
            <div><span class="label">Balance:</span> $${Number(c.account_balance).toLocaleString('en',{minimumFractionDigits:2})}</div>
            <div><span class="label">Home Branch:</span> <span class="badge badge-${c.homebranchid.toLowerCase()}">${c.homebranchid}</span></div>
        </div>

        <div style="margin: 16px 0; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); padding: 16px; border-radius: 8px;">
            <h4 style="margin: 0 0 10px 0; color: var(--accent-a); font-size: 14px; font-weight: 600;">📊 Day 30 Transaction Summary (For Re-Fragmentation Decision)</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px;">
                <div><span style="font-size: 12px; color: var(--text-dim);">Local TX (Day 30):</span><div style="font-size: 16px; font-weight: bold;">${localDay30}</div></div>
                <div><span style="font-size: 12px; color: var(--text-dim);">Remote TX (Day 30):</span><div style="font-size: 16px; font-weight: bold; color: var(--red);">${remoteDay30}</div></div>
                <div><span style="font-size: 12px; color: var(--text-dim);">Remote % (Day 30):</span><div style="font-size: 16px; font-weight: bold; color: ${remotePctDay30 > 50 ? 'var(--red)' : 'var(--orange)'};">${remotePctDay30}%</div></div>
                <div><span style="font-size: 12px; color: var(--text-dim);">LR (Day 30):</span><div style="font-size: 16px; font-weight: bold;">${totalDay30 > 0 ? (localDay30 / totalDay30).toFixed(3) : '0.000'}</div></div>
            </div>
        </div>

        <h3 style="display:flex;justify-content:space-between;align-items:center;">
            <span><span class="tx-site-label site-a-bg">📀 Site A Database</span> — ${d.site_a.length} transactions
            ${c.homebranchid==='A' ? '<span style="color:var(--green);font-size:11px">● LOCAL</span>' : '<span style="color:var(--orange);font-size:11px">● REMOTE</span>'}</span>
            <button class="btn" style="padding:4px 8px;font-size:12px;cursor:pointer" onclick="addTx(${cid}, 'A')">➕ Add TX (Day 30)</button>
        </h3>
        <div class="table-wrap"><table>
            <thead><tr><th>TX ID</th><th>ATM</th><th>Amount</th><th>Date</th><th>Day</th><th></th></tr></thead>
            <tbody>${txRowsA}</tbody>
        </table></div>

        <h3 style="display:flex;justify-content:space-between;align-items:center;">
            <span><span class="tx-site-label site-b-bg">📀 Site B Database</span> — ${d.site_b.length} transactions
            ${c.homebranchid==='B' ? '<span style="color:var(--green);font-size:11px">● LOCAL</span>' : '<span style="color:var(--orange);font-size:11px">● REMOTE</span>'}</span>
            <button class="btn" style="padding:4px 8px;font-size:12px;cursor:pointer" onclick="addTx(${cid}, 'B')">➕ Add TX (Day 30)</button>
        </h3>
        <div class="table-wrap"><table>
            <thead><tr><th>TX ID</th><th>ATM</th><th>Amount</th><th>Date</th><th>Day</th><th></th></tr></thead>
            <tbody>${txRowsB}</tbody>
        </table></div>
    `;
}

window.addTx = async function(cid, atm) {
    await api(`/api/customer/${cid}/add-tx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ atm, day: 30 })
    });
    viewCustomer(cid);
    loadLR();
    loadCandidates();
    loadOverview();
};

window.delTx = async function(txid, site, cid) {
    await api(`/api/tx/${txid}/${site}`, { method: 'DELETE' });
    viewCustomer(cid);
    loadLR();
    loadCandidates();
    loadOverview();
};

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('show');
}

// ── LR Analysis ──
async function loadLR() {
    const d = await api('/api/lr?threshold=' + getThreshold());
    const container = document.getElementById('lr-comparison');

    function makeCard(dayKey, label) {
        const data = d[dayKey];
        if (!data) return '<div class="lr-card"><p>No data</p></div>';
        const lr = data.lr_overall;
        const pct = Math.round(lr * 100);
        const color = lr >= d.threshold ? 'var(--green)' : 'var(--red)';
        const statusClass = lr >= d.threshold ? 'ok' : 'warn';
        const statusText = lr >= d.threshold ? '✅ Stable — No action needed' : '⚠️ DRIFT DETECTED — Re-fragmentation required!';

        return `<div class="lr-card">
            <h3>${label}</h3>
            <div class="lr-gauge" style="--gauge-pct:${pct};--gauge-color:${color}">
                <div class="lr-value" style="color:${color}">${lr.toFixed(3)}</div>
                <div class="lr-label">LR Overall</div>
            </div>
            <table class="lr-detail-table">
                <tr><td class="label-col">LR (Branch A)</td><td><strong>${data.lr_a.toFixed(3)}</strong></td>
                    <td class="label-col">${data.A_A} local / ${data.total_a} total</td></tr>
                <tr><td class="label-col">LR (Branch B)</td><td><strong>${data.lr_b.toFixed(3)}</strong></td>
                    <td class="label-col">${data.B_B} local / ${data.total_b} total</td></tr>
                <tr><td class="label-col">Threshold</td><td colspan="2"><strong>${d.threshold}</strong></td></tr>
            </table>
            <div class="lr-detail-table" style="margin-top:12px">
                <table style="font-size:12px">
                    <thead><tr><th></th><th>ATM A</th><th>ATM B</th><th>Total</th></tr></thead>
                    <tbody>
                        <tr><td class="label-col">Branch A customers</td>
                            <td>${data.A_A} (${data.total_a ? Math.round(data.A_A/data.total_a*100) : 0}%)</td>
                            <td>${data.A_B} (${data.total_a ? Math.round(data.A_B/data.total_a*100) : 0}%)</td>
                            <td>${data.total_a}</td></tr>
                        <tr><td class="label-col">Branch B customers</td>
                            <td>${data.B_A} (${data.total_b ? Math.round(data.B_A/data.total_b*100) : 0}%)</td>
                            <td>${data.B_B} (${data.total_b ? Math.round(data.B_B/data.total_b*100) : 0}%)</td>
                            <td>${data.total_b}</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="lr-status ${statusClass}">${statusText}</div>
        </div>`;
    }

    container.innerHTML = makeCard('day_1', '📅 Day 1 — Normal Workload') + makeCard('day_30', '📅 Day 30 — After Drift');
}

// ── Migration Candidates ──
let allCandidates = [];

async function loadCandidates() {
    const d = await api('/api/migration-candidates?threshold=' + getThreshold());
    allCandidates = d.candidates || [];
    const searchInput = document.getElementById('search-candidates');
    if (searchInput) searchInput.value = '';
    const directionSelect = document.getElementById('filter-candidate-direction');
    if (directionSelect) directionSelect.value = '';
    renderCandidates(allCandidates);
}

function renderCandidates(list) {
    const tbody = document.querySelector('#table-candidates tbody');
    tbody.innerHTML = list.map(c => `
        <tr>
            <td>${c.customerid}</td>
            <td><strong>${c.fullname}</strong></td>
            <td style="color:var(--text-dim)">${c.email}</td>
            <td><span class="badge badge-${c.homebranchid.toLowerCase()}">${c.homebranchid}</span> → <span class="badge badge-${c.target_branch.toLowerCase()}">${c.target_branch}</span></td>
            <td>${c.local_tx_count}</td>
            <td style="color:var(--red)">${c.remote_tx_count}</td>
            <td><span style="color:${c.remote_pct > 50 ? 'var(--red)' : 'var(--orange)'};font-weight:600">${c.remote_pct}%</span></td>
            <td><button class="btn btn-view" onclick="viewCustomer(${c.customerid})">View</button></td>
        </tr>
    `).join('') || '<tr><td colspan="8" style="text-align:center;color:var(--text-dim)">No candidates found</td></tr>';
}

// Search and filter candidates
function filterAndRenderCandidates() {
    const searchInput = document.getElementById('search-candidates');
    const directionSelect = document.getElementById('filter-candidate-direction');
    
    let list = allCandidates;
    
    if (directionSelect) {
        const dir = directionSelect.value;
        if (dir === 'A->B') {
            list = list.filter(c => c.homebranchid === 'A');
        } else if (dir === 'B->A') {
            list = list.filter(c => c.homebranchid === 'B');
        }
    }
    
    if (searchInput) {
        const q = searchInput.value.trim().toLowerCase();
        if (q) {
            list = list.filter(c => c.fullname.toLowerCase().includes(q));
        }
    }
    
    renderCandidates(list);
}

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-candidates');
    const directionSelect = document.getElementById('filter-candidate-direction');
    
    if (searchInput) searchInput.addEventListener('input', filterAndRenderCandidates);
    if (directionSelect) directionSelect.addEventListener('change', filterAndRenderCandidates);
});

// ── Migration ──
async function runMigration() {
    const btn = document.getElementById('btn-migrate');
    btn.disabled = true;
    btn.textContent = '⏳ Migrating...';

    const d = await api('/api/migrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: getThreshold() })
    });
    btn.textContent = '✅ Done!';

    const result = document.getElementById('migration-result');
    result.classList.remove('hidden');
    result.innerHTML = `
        <h3>✅ Re-Fragmentation Complete</h3>
        <p>👤 Chuyển <strong>${d.migrated_a_to_b}</strong> khách hàng: Site A → Site B (${d.cust_moved_to_b || d.migrated_a_to_b} records)</p>
        <p>👤 Chuyển <strong>${d.migrated_b_to_a}</strong> khách hàng: Site B → Site A (${d.cust_moved_to_a || d.migrated_b_to_a} records)</p>
        <p>📤 Di chuyển <strong>${d.tx_moved_to_b}</strong> transactions → Site B</p>
        <p>📤 Di chuyển <strong>${d.tx_moved_to_a}</strong> transactions → Site A</p>
        <p>📊 New LR (Day 30): <strong style="color:var(--green)">${d.new_lr}</strong></p>
        <p style="margin-top:8px;color:var(--text-dim)">${d.message}</p>
        <p style="margin-top:12px;font-size:12px;color:var(--text-dim)">
            ℹ️ Xem <strong>Overview</strong> để thấy số lượng khách hàng đã thay đổi trên mỗi site.
        </p>`;

    // Refresh data
    loadOverview();
    loadLR();
    loadCandidates();
}

// ── Undo Migration ──
async function undoMigration() {
    const btn = document.getElementById('btn-undo');
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Undoing...';

    const res = await api('/api/undo', { method: 'POST' });

    btn.disabled = false;
    btn.innerHTML = '<span>🔙</span> Undo Migration';
    
    if (res.status === 'ok') {
        document.getElementById('migration-result').classList.add('hidden');
        const migrateBtn = document.getElementById('btn-migrate');
        migrateBtn.disabled = false;
        migrateBtn.textContent = '⚡ Execute Re-Fragmentation';

        loadOverview();
        loadLR();
        loadCandidates();
        alert(res.message);
    } else {
        alert("Có lỗi xảy ra khi Undo!");
    }
}

// ── Export CSV ──
window.exportCSV = function(type, site) {
    let url = '';
    const threshold = getThreshold();
    
    if (type === 'customers') {
        url = `/api/export/customers/${site}`;
    } else if (type === 'transactions') {
        url = `/api/export/transactions/${site}`;
    } else if (type === 'candidates') {
        url = `/api/export/candidates?threshold=${threshold}`;
    } else if (type === 'drift') {
        url = `/api/export/drift?threshold=${threshold}`;
    }
    
    if (url) {
        window.location.href = url;
    }
};
