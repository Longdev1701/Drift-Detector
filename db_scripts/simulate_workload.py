"""
Mô phỏng workload: Day 1 (high locality) + Day 30 (drift).
Transactions phân mảnh ngang: atm_branchid='A' → Site A, 'B' → Site B.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random, psycopg2
from psycopg2.extras import execute_values
from config import SITE_A, SITE_B, TOTAL_CUSTOMERS

random.seed(42)

def generate_transactions(day, local_rate_a, local_rate_b):
    conn_a = psycopg2.connect(**SITE_A)
    cur_a = conn_a.cursor()
    cur_a.execute("SELECT customerid FROM customers")
    cids_a = [r[0] for r in cur_a.fetchall()]
    conn_a.close()

    conn_b = psycopg2.connect(**SITE_B)
    cur_b = conn_b.cursor()
    cur_b.execute("SELECT customerid FROM customers")
    cids_b = [r[0] for r in cur_b.fetchall()]
    conn_b.close()

    txs = []
    
    # Each Branch A customer gets a random number of transactions
    for cid in cids_a:
        num_tx = random.randint(3, 10)
        local_cnt = int(round(num_tx * local_rate_a))
        remote_cnt = num_tx - local_cnt
        atms = ['A'] * local_cnt + ['B'] * remote_cnt
        random.shuffle(atms)
        for atm in atms:
            txs.append((cid, atm, round(random.uniform(50,5000),2), day))
            
    # Each Branch B customer gets a random number of transactions
    for cid in cids_b:
        num_tx = random.randint(3, 10)
        local_cnt = int(round(num_tx * local_rate_b))
        remote_cnt = num_tx - local_cnt
        atms = ['B'] * local_cnt + ['A'] * remote_cnt
        random.shuffle(atms)
        for atm in atms:
            txs.append((cid, atm, round(random.uniform(50,5000),2), day))
            
    return txs

def insert_transactions(transactions):
    site_a = [t for t in transactions if t[1]=='A']
    site_b = [t for t in transactions if t[1]=='B']
    for cfg, txs in [(SITE_A, site_a), (SITE_B, site_b)]:
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        sql = "INSERT INTO transactions (customerid,atm_branchid,amount,workload_day) VALUES %s"
        execute_values(cur, sql, txs, page_size=10000)
        conn.commit(); cur.close(); conn.close()
    return len(site_a), len(site_b)

def clear_transactions():
    for cfg in [SITE_A, SITE_B]:
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions;")
        cur.execute("ALTER SEQUENCE transactions_txid_seq RESTART WITH 1;")
        conn.commit(); cur.close(); conn.close()

def run_simulation():
    print("▶ Xóa transactions cũ..."); clear_transactions()
    txs1 = generate_transactions(1, 0.90, 0.90)
    a1,b1 = insert_transactions(txs1)
    print(f"  Day 1: {len(txs1)} tx (Site A: {a1}, Site B: {b1})")
    txs30 = generate_transactions(30, 0.35, 0.45)
    a30,b30 = insert_transactions(txs30)
    print(f"  Day 30: {len(txs30)} tx (Site A: {a30}, Site B: {b30})")
    print("✅ Simulation done!")

if __name__ == '__main__':
    run_simulation()
