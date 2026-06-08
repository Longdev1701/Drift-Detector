"""Flask API backend for Drift Detector Web Dashboard
Customers phân mảnh ngang: Site A = Branch A, Site B = Branch B.
Transactions phân mảnh ngang: Site A = ATM A, Site B = ATM B.
"""
from flask import Flask, render_template, jsonify, request, make_response
import psycopg2, psycopg2.extras
import random
import csv
import io
from config import SITE_A, SITE_B, LR_THRESHOLD

app = Flask(__name__)

def get_conn(site):
    cfg = SITE_A if site == 'a' else SITE_B
    return psycopg2.connect(**cfg)

def query(site, sql, params=None):
    conn = get_conn(site)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows



@app.route('/')
def index():
    return render_template('index.html')

# ──────────────────────────────────────────────────────────
# Overview — mỗi site chỉ có customers của branch mình
# ──────────────────────────────────────────────────────────
@app.route('/api/overview')
def overview():
    result = {}
    for s in ['a','b']:
        label = 'site_' + s
        rows = query(s, "SELECT COUNT(*) as cnt FROM customers")
        result[label + '_customers'] = rows[0]['cnt']
        rows = query(s, "SELECT COUNT(*) as cnt FROM transactions")
        result[label + '_transactions'] = rows[0]['cnt']
        rows = query(s, "SELECT homebranchid, COUNT(*) as cnt FROM customers GROUP BY homebranchid ORDER BY homebranchid")
        result[label + '_by_branch'] = {r['homebranchid'].strip(): r['cnt'] for r in rows}
    return jsonify(result)

# ──────────────────────────────────────────────────────────
# Customers list — query from specific site
# ──────────────────────────────────────────────────────────
@app.route('/api/customers')
def customers():
    site = request.args.get('site', 'a')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    search = request.args.get('search', '').strip()
    branch_filter = request.args.get('branch', '').strip()
    offset = (page - 1) * per_page

    where = []
    params = []
    if search:
        where.append("(fullname ILIKE %s OR email ILIKE %s)")
        params += [f'%{search}%', f'%{search}%']
    if branch_filter:
        where.append("homebranchid = %s")
        params.append(branch_filter)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    count_rows = query(site, f"SELECT COUNT(*) as cnt FROM customers {where_sql}", params)
    total = count_rows[0]['cnt']

    rows = query(site,
        f"""SELECT customerid,fullname,email,phone,address,account_type,
            account_balance::float,date_of_birth::text,created_at::text,homebranchid
            FROM customers {where_sql}
            ORDER BY customerid LIMIT %s OFFSET %s""",
        params + [per_page, offset])

    for r in rows:
        r['homebranchid'] = r['homebranchid'].strip()

    return jsonify({'customers': rows, 'total': total, 'page': page, 'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page})

# ──────────────────────────────────────────────────────────
# Customer detail — tìm customer ở site phù hợp (distributed lookup)
# ──────────────────────────────────────────────────────────
@app.route('/api/customer/<int:cid>/transactions')
def customer_transactions(cid):
    result = {}
    # Lấy transactions từ cả 2 site
    for s in ['a','b']:
        rows = query(s,
            """SELECT t.txid, t.atm_branchid, t.amount::float, t.txdate::text, t.workload_day
               FROM transactions t WHERE t.customerid=%s ORDER BY t.txid""", (cid,))
        for r in rows:
            r['atm_branchid'] = r['atm_branchid'].strip()
        result['site_' + s] = rows

    # Tìm customer info — thử site A trước, nếu không có thì site B (distributed lookup)
    info = query('a', """SELECT customerid,fullname,email,phone,address,account_type,
        account_balance::float,homebranchid FROM customers WHERE customerid=%s""", (cid,))
    if not info:
        info = query('b', """SELECT customerid,fullname,email,phone,address,account_type,
            account_balance::float,homebranchid FROM customers WHERE customerid=%s""", (cid,))
    if info:
        info[0]['homebranchid'] = info[0]['homebranchid'].strip()
        result['customer'] = info[0]
    return jsonify(result)

# ── Dynamic Transaction Modification ──
@app.route('/api/customer/<int:cid>/add-tx', methods=['POST'])
def add_tx(cid):
    data = request.json
    atm = data.get('atm', 'A')
    day = data.get('day', 30)
    amount = round(random.uniform(50, 5000), 2)
    
    # insert into appropriate site based on atm_branchid
    site = 'a' if atm == 'A' else 'b'
    conn = get_conn(site)
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (customerid, atm_branchid, amount, workload_day) VALUES (%s, %s, %s, %s)",
                (cid, atm, amount, day))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/tx/<int:txid>/<site>', methods=['DELETE'])
def delete_tx(txid, site):
    conn = get_conn(site)
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE txid=%s", (txid,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

# ──────────────────────────────────────────────────────────
# LR Analysis — distributed JOIN trong Python
# ──────────────────────────────────────────────────────────
@app.route('/api/lr')
def lr_analysis():
    threshold = request.args.get('threshold', LR_THRESHOLD, type=float)
    
    # Thu thập tất cả customers từ cả 2 site → dict customerid → homebranchid
    cust_branch = {}
    for s in ['a','b']:
        for r in query(s, "SELECT customerid, homebranchid FROM customers"):
            cust_branch[r['customerid']] = r['homebranchid'].strip()

    days_data = {}
    for day in [1, 30]:
        # Thu thập tất cả transactions từ cả 2 site
        all_tx = []
        for s in ['a','b']:
            rows = query(s,
                "SELECT customerid, atm_branchid FROM transactions WHERE workload_day=%s", (day,))
            all_tx.extend(rows)

        # Tính LR trong Python (distributed JOIN)
        stats = {}
        for tx in all_tx:
            cid = tx['customerid']
            atm = tx['atm_branchid'].strip()
            home = cust_branch.get(cid)
            if home is None:
                continue
            key = home + '_' + atm
            stats[key] = stats.get(key, 0) + 1

        la = stats.get('A_A', 0)
        ra = stats.get('A_B', 0)
        lb = stats.get('B_B', 0)
        rb = stats.get('B_A', 0)
        ta = la + ra
        tb = lb + rb
        total = ta + tb
        local_total = la + lb

        days_data[f'day_{day}'] = {
            'A_A': la, 'A_B': ra, 'total_a': ta,
            'B_B': lb, 'B_A': rb, 'total_b': tb,
            'lr_a': round(la/ta, 3) if ta else 0,
            'lr_b': round(lb/tb, 3) if tb else 0,
            'lr_overall': round(local_total/total, 3) if total else 0,
            'total': total, 'local_total': local_total
        }

    days_data['threshold'] = threshold
    return jsonify(days_data)

# ──────────────────────────────────────────────────────────
# Migration candidates — lấy customers từ CẢ 2 site
# ──────────────────────────────────────────────────────────
@app.route('/api/migration-candidates')
def migration_candidates():
    """Find ALL drifted customers (>50% remote TX on Day 30) from both branches"""
    threshold = request.args.get('threshold', LR_THRESHOLD, type=float)
    
    # TX counts per customer from both sites on Day 30
    tx_at_a = {}
    for r in query('a', "SELECT customerid, COUNT(*) as cnt FROM transactions WHERE workload_day=30 GROUP BY customerid"):
        tx_at_a[r['customerid']] = r['cnt']
    tx_at_b = {}
    for r in query('b', "SELECT customerid, COUNT(*) as cnt FROM transactions WHERE workload_day=30 GROUP BY customerid"):
        tx_at_b[r['customerid']] = r['cnt']

    # Lấy customers từ CẢ 2 site (distributed query)
    all_custs = []
    for s in ['a','b']:
        rows = query(s, "SELECT customerid, fullname, email, homebranchid FROM customers ORDER BY customerid")
        all_custs.extend(rows)

    candidates = []
    for c in all_custs:
        cid = c['customerid']
        branch = c['homebranchid'].strip()
        local_cnt = tx_at_a.get(cid, 0) if branch == 'A' else tx_at_b.get(cid, 0)
        remote_cnt = tx_at_b.get(cid, 0) if branch == 'A' else tx_at_a.get(cid, 0)
        total = local_cnt + remote_cnt
        if total == 0:
            continue
        lr = local_cnt / total
        # Chỉ coi là candidate nếu thực sự bị drift (giao dịch remote nhiều hơn local, tức là lr < 0.5)
        # và đồng thời lr < threshold
        if lr < threshold and lr < 0.5:
            remote_pct = round(remote_cnt / total * 100, 1)
            candidates.append({
                'customerid': cid,
                'fullname': c['fullname'],
                'email': c['email'],
                'homebranchid': branch,
                'local_tx_count': local_cnt,
                'remote_tx_count': remote_cnt,
                'total_tx': total,
                'remote_pct': remote_pct,
                'target_branch': 'B' if branch == 'A' else 'A'
            })

    candidates.sort(key=lambda x: x['remote_pct'], reverse=True)
    return jsonify({'candidates': candidates})

# ──────────────────────────────────────────────────────────
# Migration — chuyển customer records + transactions giữa sites
# ──────────────────────────────────────────────────────────
@app.route('/api/migrate', methods=['POST'])
def migrate():
    """Re-fragmentation: move drifted customers + their transactions to new home site"""
    data = request.json or {}
    threshold = float(data.get('threshold', LR_THRESHOLD))

    # ── Create backups before migrating so we can undo ──
    for s in ['a', 'b']:
        conn = get_conn(s)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS customers_backup;")
        cur.execute("DROP TABLE IF EXISTS transactions_backup;")
        cur.execute("CREATE TABLE customers_backup AS SELECT * FROM customers;")
        cur.execute("CREATE TABLE transactions_backup AS SELECT * FROM transactions;")
        conn.commit()
        cur.close()
        conn.close()

    # ── Step 1: Compute per-customer TX distribution on Day 30 ──
    tx_at_a = {}
    for r in query('a', "SELECT customerid, COUNT(*) as cnt FROM transactions WHERE workload_day=30 GROUP BY customerid"):
        tx_at_a[r['customerid']] = r['cnt']
    tx_at_b = {}
    for r in query('b', "SELECT customerid, COUNT(*) as cnt FROM transactions WHERE workload_day=30 GROUP BY customerid"):
        tx_at_b[r['customerid']] = r['cnt']

    # Lấy tất cả customers từ cả 2 site
    all_custs = []
    for s in ['a','b']:
        rows = query(s, "SELECT customerid, homebranchid FROM customers")
        all_custs.extend(rows)

    migrate_a_to_b = []  # Branch A customers → become Branch B
    migrate_b_to_a = []  # Branch B customers → become Branch A

    for c in all_custs:
        cid = c['customerid']
        branch = c['homebranchid'].strip()
        local_cnt = tx_at_a.get(cid, 0) if branch == 'A' else tx_at_b.get(cid, 0)
        remote_cnt = tx_at_b.get(cid, 0) if branch == 'A' else tx_at_a.get(cid, 0)
        total = local_cnt + remote_cnt
        if total == 0:
            continue
        lr = local_cnt / total
        if lr < threshold and lr < 0.5:
            if branch == 'A':
                migrate_a_to_b.append(cid)
            else:
                migrate_b_to_a.append(cid)

    # ── Step 2: Move CUSTOMER RECORDS between sites ──
    cust_moved_to_b = 0
    if migrate_a_to_b:
        # Lấy full customer data từ Site A
        conn_a = get_conn('a')
        cur = conn_a.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT customerid,fullname,email,phone,address,account_type,
            account_balance,date_of_birth,created_at,homebranchid
            FROM customers WHERE customerid = ANY(%s)""", (migrate_a_to_b,))
        cust_rows = cur.fetchall()
        cust_moved_to_b = len(cust_rows)
        cur.close()

        # Insert vào Site B với homebranchid = 'B'
        conn_b = get_conn('b')
        cur_b = conn_b.cursor()
        for r in cust_rows:
            cur_b.execute("""INSERT INTO customers
                (customerid,fullname,email,phone,address,account_type,account_balance,date_of_birth,created_at,homebranchid)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'B')""",
                (r['customerid'], r['fullname'], r['email'], r['phone'], r['address'],
                 r['account_type'], r['account_balance'], r['date_of_birth'], r['created_at']))
        conn_b.commit(); cur_b.close(); conn_b.close()

        # Xóa khỏi Site A
        cur_del = conn_a.cursor()
        cur_del.execute("DELETE FROM customers WHERE customerid = ANY(%s)", (migrate_a_to_b,))
        conn_a.commit(); cur_del.close(); conn_a.close()

    cust_moved_to_a = 0
    if migrate_b_to_a:
        # Lấy full customer data từ Site B
        conn_b = get_conn('b')
        cur = conn_b.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT customerid,fullname,email,phone,address,account_type,
            account_balance,date_of_birth,created_at,homebranchid
            FROM customers WHERE customerid = ANY(%s)""", (migrate_b_to_a,))
        cust_rows = cur.fetchall()
        cust_moved_to_a = len(cust_rows)
        cur.close()

        # Insert vào Site A với homebranchid = 'A'
        conn_a = get_conn('a')
        cur_a = conn_a.cursor()
        for r in cust_rows:
            cur_a.execute("""INSERT INTO customers
                (customerid,fullname,email,phone,address,account_type,account_balance,date_of_birth,created_at,homebranchid)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'A')""",
                (r['customerid'], r['fullname'], r['email'], r['phone'], r['address'],
                 r['account_type'], r['account_balance'], r['date_of_birth'], r['created_at']))
        conn_a.commit(); cur_a.close(); conn_a.close()

        # Xóa khỏi Site B
        cur_del = conn_b.cursor()
        cur_del.execute("DELETE FROM customers WHERE customerid = ANY(%s)", (migrate_b_to_a,))
        conn_b.commit(); cur_del.close(); conn_b.close()

    # ── Step 3: Move TRANSACTIONS — all TX of migrated customers go to new home site ──
    tx_moved_to_b = 0
    if migrate_a_to_b:
        # Lấy TX của customers migrate_a_to_b từ Site A — bao gồm txid gốc để giữ Schema Integrity
        conn_a = get_conn('a')
        cur = conn_a.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT txid, customerid, atm_branchid, amount, txdate, workload_day FROM transactions WHERE customerid = ANY(%s)",
                    (migrate_a_to_b,))
        rows = cur.fetchall()
        tx_moved_to_b += len(rows)
        cur.close()

        # Insert vào Site B — giữ nguyên txid gốc (tránh mất OID / trùng khóa)
        conn_b = get_conn('b')
        cur_b = conn_b.cursor()
        for r in rows:
            cur_b.execute(
                "INSERT INTO transactions (txid,customerid,atm_branchid,amount,txdate,workload_day) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (txid) DO NOTHING",
                (r['txid'], r['customerid'], r['atm_branchid'], r['amount'], r['txdate'], r['workload_day']))
        # Cập nhật sequence để tránh conflict sau này
        cur_b.execute("SELECT setval('transactions_txid_seq', (SELECT MAX(txid) FROM transactions))")
        conn_b.commit(); cur_b.close(); conn_b.close()

        # Xóa từ Site A
        cur_del = conn_a.cursor()
        cur_del.execute("DELETE FROM transactions WHERE customerid = ANY(%s)", (migrate_a_to_b,))
        conn_a.commit(); cur_del.close(); conn_a.close()

    tx_moved_to_a = 0
    if migrate_b_to_a:
        # Lấy TX của customers migrate_b_to_a từ Site B — bao gồm txid gốc để giữ Schema Integrity
        conn_b = get_conn('b')
        cur = conn_b.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT txid, customerid, atm_branchid, amount, txdate, workload_day FROM transactions WHERE customerid = ANY(%s)",
                    (migrate_b_to_a,))
        rows = cur.fetchall()
        tx_moved_to_a += len(rows)
        cur.close()

        # Insert vào Site A — giữ nguyên txid gốc (tránh mất OID / trùng khóa)
        conn_a = get_conn('a')
        cur_a = conn_a.cursor()
        for r in rows:
            cur_a.execute(
                "INSERT INTO transactions (txid,customerid,atm_branchid,amount,txdate,workload_day) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (txid) DO NOTHING",
                (r['txid'], r['customerid'], r['atm_branchid'], r['amount'], r['txdate'], r['workload_day']))
        # Cập nhật sequence để tránh conflict sau này
        cur_a.execute("SELECT setval('transactions_txid_seq', (SELECT MAX(txid) FROM transactions))")
        conn_a.commit(); cur_a.close(); conn_a.close()

        # Xóa từ Site B
        cur_del = conn_b.cursor()
        cur_del.execute("DELETE FROM transactions WHERE customerid = ANY(%s)", (migrate_b_to_a,))
        conn_b.commit(); cur_del.close(); conn_b.close()

    # ── Step 4: Recalculate LR after migration ──
    cust_branch = {}
    for s in ['a','b']:
        for r in query(s, "SELECT customerid, homebranchid FROM customers"):
            cust_branch[r['customerid']] = r['homebranchid'].strip()

    all_tx = []
    for s in ['a','b']:
        rows = query(s, "SELECT customerid, atm_branchid FROM transactions WHERE workload_day=30")
        all_tx.extend(rows)

    stats = {}
    for tx in all_tx:
        home = cust_branch.get(tx['customerid'])
        if home is None:
            continue
        key = home + '_' + tx['atm_branchid'].strip()
        stats[key] = stats.get(key, 0) + 1

    la = stats.get('A_A', 0)
    ra = stats.get('A_B', 0)
    lb = stats.get('B_B', 0)
    rb = stats.get('B_A', 0)
    total = la + ra + lb + rb
    local_total = la + lb
    new_lr = round(local_total / total, 3) if total else 0

    return jsonify({
        'migrated_a_to_b': len(migrate_a_to_b),
        'migrated_b_to_a': len(migrate_b_to_a),
        'cust_moved_to_b': cust_moved_to_b,
        'cust_moved_to_a': cust_moved_to_a,
        'tx_moved_to_b': tx_moved_to_b,
        'tx_moved_to_a': tx_moved_to_a,
        'new_lr': new_lr,
        'message': f'Chuyển {len(migrate_a_to_b)} khách A→B, {len(migrate_b_to_a)} khách B→A. '
                   f'Di chuyển {tx_moved_to_b} TX → Site B, {tx_moved_to_a} TX → Site A. New LR: {new_lr}'
    })

@app.route('/api/undo', methods=['POST'])
def undo_migration():
    for s in ['a', 'b']:
        conn = get_conn(s)
        cur = conn.cursor()
        # Ensure backups exist
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'customers_backup')")
        if cur.fetchone()[0]:
            cur.execute("TRUNCATE transactions, customers CASCADE;")
            cur.execute("INSERT INTO customers SELECT * FROM customers_backup;")
            cur.execute("INSERT INTO transactions SELECT * FROM transactions_backup;")
        conn.commit()
        cur.close()
        conn.close()
    return jsonify({'status': 'ok', 'message': 'Đã khôi phục dữ liệu về trạng thái trước khi chuyển!'})

# ──────────────────────────────────────────────────────────
# CSV Export Routes
# ──────────────────────────────────────────────────────────
@app.route('/api/export/customers/<site>')
def export_customers_csv(site):
    if site not in ['a', 'b']:
        return "Invalid site", 400
    
    rows = query(site, """SELECT customerid, fullname, email, phone, address, account_type, 
                          account_balance::float, date_of_birth::text, created_at::text, homebranchid 
                          FROM customers ORDER BY customerid""")
    
    for r in rows:
        r['homebranchid'] = r['homebranchid'].strip()
        
    si = io.StringIO()
    cw = csv.writer(si)
    if rows:
        cw.writerow(rows[0].keys())
        for row in rows:
            cw.writerow(row.values())
            
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=customers_site_{site.upper()}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/api/export/transactions/<site>')
def export_transactions_csv(site):
    if site not in ['a', 'b']:
        return "Invalid site", 400
        
    rows = query(site, """SELECT txid, customerid, atm_branchid, amount::float, 
                          txdate::text, workload_day FROM transactions ORDER BY txid""")
    
    for r in rows:
        r['atm_branchid'] = r['atm_branchid'].strip()
        
    si = io.StringIO()
    cw = csv.writer(si)
    if rows:
        cw.writerow(rows[0].keys())
        for row in rows:
            cw.writerow(row.values())
            
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=transactions_site_{site.upper()}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/api/export/candidates')
def export_candidates_csv():
    threshold = request.args.get('threshold', LR_THRESHOLD, type=float)
    
    tx_at_a = {}
    for r in query('a', "SELECT customerid, COUNT(*) as cnt FROM transactions WHERE workload_day=30 GROUP BY customerid"):
        tx_at_a[r['customerid']] = r['cnt']
    tx_at_b = {}
    for r in query('b', "SELECT customerid, COUNT(*) as cnt FROM transactions WHERE workload_day=30 GROUP BY customerid"):
        tx_at_b[r['customerid']] = r['cnt']

    all_custs = []
    for s in ['a','b']:
        rows = query(s, "SELECT customerid, fullname, email, homebranchid FROM customers ORDER BY customerid")
        all_custs.extend(rows)

    candidates = []
    for c in all_custs:
        cid = c['customerid']
        branch = c['homebranchid'].strip()
        local_cnt = tx_at_a.get(cid, 0) if branch == 'A' else tx_at_b.get(cid, 0)
        remote_cnt = tx_at_b.get(cid, 0) if branch == 'A' else tx_at_a.get(cid, 0)
        total = local_cnt + remote_cnt
        if total == 0:
            continue
        lr = local_cnt / total
        if lr < threshold and lr < 0.5:
            remote_pct = round(remote_cnt / total * 100, 1)
            candidates.append({
                'customerid': cid,
                'fullname': c['fullname'],
                'email': c['email'],
                'homebranchid': branch,
                'local_tx_count': local_cnt,
                'remote_tx_count': remote_cnt,
                'total_tx': total,
                'remote_pct': remote_pct,
                'target_branch': 'B' if branch == 'A' else 'A'
            })

    candidates.sort(key=lambda x: x['remote_pct'], reverse=True)
    
    si = io.StringIO()
    cw = csv.writer(si)
    if candidates:
        cw.writerow(candidates[0].keys())
        for row in candidates:
            cw.writerow(row.values())
            
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=migration_candidates_threshold_{threshold:.2f}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/api/export/drift')
def export_drift_csv():
    threshold = request.args.get('threshold', LR_THRESHOLD, type=float)
    
    cust_branch = {}
    for s in ['a','b']:
        for r in query(s, "SELECT customerid, homebranchid FROM customers"):
            cust_branch[r['customerid']] = r['homebranchid'].strip()

    drift_records = []
    for day in [1, 30]:
        all_tx = []
        for s in ['a','b']:
            rows = query(s, "SELECT customerid, atm_branchid FROM transactions WHERE workload_day=%s", (day,))
            all_day_txs = [dict(r) for r in rows]
            all_tx.extend(all_day_txs)

        stats = {}
        for tx in all_tx:
            cid = tx['customerid']
            atm = tx['atm_branchid'].strip()
            home = cust_branch.get(cid)
            if home is None:
                continue
            key = home + '_' + atm
            stats[key] = stats.get(key, 0) + 1

        la = stats.get('A_A', 0)
        ra = stats.get('A_B', 0)
        lb = stats.get('B_B', 0)
        rb = stats.get('B_A', 0)
        ta = la + ra
        tb = lb + rb
        total = ta + tb
        local_total = la + lb
        
        lr_overall = round(local_total/total, 4) if total else 0.0

        drift_records.append({
            'Workload_Day': f"Day {day}",
            'Branch_A_Local_TX': la,
            'Branch_A_Remote_TX': ra,
            'Branch_A_Total_TX': ta,
            'Branch_A_LR': round(la/ta, 4) if ta else 0.0,
            'Branch_B_Local_TX': lb,
            'Branch_B_Remote_TX': rb,
            'Branch_B_Total_TX': tb,
            'Branch_B_LR': round(lb/tb, 4) if tb else 0.0,
            'Overall_Local_TX': local_total,
            'Overall_Total_TX': total,
            'Overall_LR': lr_overall,
            'Threshold': threshold,
            'Drift_Detected': "YES" if lr_overall < threshold else "NO"
        })

    si = io.StringIO()
    cw = csv.writer(si)
    if drift_records:
        cw.writerow(drift_records[0].keys())
        for row in drift_records:
            cw.writerow(row.values())
            
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=drift_analysis_report.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

if __name__ == '__main__':
    app.run(debug=True, port=5000)
