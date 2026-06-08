"""
Mô phỏng workload: Day 1 (high locality) đến Day 30 (drift) với các ngày ngẫu nhiên ở giữa.
Transactions phân mảnh ngang: atm_branchid='A' → Site A, 'B' → Site B.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random, psycopg2, datetime
from psycopg2.extras import execute_values
from config import SITE_A, SITE_B, TOTAL_CUSTOMERS

random.seed(42)

def get_random_timestamp(day):
    # Ngày 1 bắt đầu từ 2026-05-01, Ngày 30 là 2026-05-30
    base_date = datetime.datetime(2026, 5, 1)
    day_date = base_date + datetime.timedelta(days=(day - 1))
    
    # Thêm giờ, phút, giây ngẫu nhiên
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    microsecond = random.randint(0, 999999)
    return day_date.replace(hour=hour, minute=minute, second=second, microsecond=microsecond)

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
        if day in [1, 30]:
            num_tx = random.randint(3, 10)
        else:
            # Các ngày ở giữa: mỗi khách hàng chỉ có 15% cơ hội phát sinh giao dịch
            if random.random() > 0.15:
                continue
            num_tx = random.randint(1, 2)

        local_cnt = int(round(num_tx * local_rate_a))
        remote_cnt = num_tx - local_cnt
        atms = ['A'] * local_cnt + ['B'] * remote_cnt
        random.shuffle(atms)
        for atm in atms:
            txdate = get_random_timestamp(day)
            txs.append((cid, atm, round(random.uniform(50,5000),2), day, txdate))
            
    # Each Branch B customer gets a random number of transactions
    for cid in cids_b:
        if day in [1, 30]:
            num_tx = random.randint(3, 10)
        else:
            # Các ngày ở giữa: mỗi khách hàng chỉ có 15% cơ hội phát sinh giao dịch
            if random.random() > 0.15:
                continue
            num_tx = random.randint(1, 2)

        local_cnt = int(round(num_tx * local_rate_b))
        remote_cnt = num_tx - local_cnt
        atms = ['B'] * local_cnt + ['A'] * remote_cnt
        random.shuffle(atms)
        for atm in atms:
            txdate = get_random_timestamp(day)
            txs.append((cid, atm, round(random.uniform(50,5000),2), day, txdate))
            
    return txs

def insert_transactions(transactions):
    site_a = [t for t in transactions if t[1]=='A']
    site_b = [t for t in transactions if t[1]=='B']
    for cfg, txs in [(SITE_A, site_a), (SITE_B, site_b)]:
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        sql = "INSERT INTO transactions (customerid,atm_branchid,amount,workload_day,txdate) VALUES %s"
        execute_values(cur, sql, txs, page_size=10000)
        conn.commit(); cur.close(); conn.close()
    return len(site_a), len(site_b)

def clear_transactions():
    for cfg in [SITE_A, SITE_B]:
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions;")
        cur.execute("ALTER SEQUENCE transactions_txid_seq RESTART WITH 1;")
        cur.execute("DROP TABLE IF EXISTS transactions_backup;")
        cur.execute("DROP TABLE IF EXISTS customers_backup;")
        conn.commit(); cur.close(); conn.close()

def run_simulation():
    print("▶ Xóa transactions cũ..."); clear_transactions()
    
    total_inserted_a = 0
    total_inserted_b = 0
    total_tx = 0
    
    print("▶ Bắt đầu sinh giao dịch ngẫu nhiên từ Day 1 đến Day 30...")
    for day in range(1, 31):
        # Nội suy tỷ lệ cục bộ từ 90% (Day 1) giảm xuống 20%/25% (Day 30) để tạo drift rõ rệt hơn, giúp LR sau di chuyển vượt ngưỡng 0.7
        rate_a = 0.90 - (0.90 - 0.20) * (day - 1) / 29.0
        rate_b = 0.90 - (0.90 - 0.25) * (day - 1) / 29.0
        
        txs = generate_transactions(day, rate_a, rate_b)
        if txs:
            a, b = insert_transactions(txs)
            total_inserted_a += a
            total_inserted_b += b
            total_tx += len(txs)
            
            # In thông tin các mốc ngày chính
            if day in [1, 5, 10, 15, 20, 25, 30]:
                print(f"  Day {day:02d}: {len(txs):5d} txs (Site A: {a:4d}, Site B: {b:4d}) | Locality Rates A: {rate_a:.2f}, B: {rate_b:.2f}")
                
    print(f"✅ Hoàn tất mô phỏng! Tổng cộng sinh {total_tx} giao dịch (Site A: {total_inserted_a}, Site B: {total_inserted_b})")

if __name__ == '__main__':
    run_simulation()
