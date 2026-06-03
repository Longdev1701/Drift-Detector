"""
Khởi tạo schema và seed dữ liệu.
Customers phân mảnh ngang: Branch A → Site A, Branch B → Site B.
Transactions phân mảnh ngang theo atm_branchid: ATM A → Site A, ATM B → Site B.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random, psycopg2
from psycopg2.extras import execute_values
from config import SITE_A, SITE_B, TOTAL_CUSTOMERS

random.seed(42)

FIRST = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda",
"David","Elizabeth","William","Barbara","Richard","Susan","Joseph","Jessica",
"Thomas","Sarah","Charles","Karen","Christopher","Lisa","Daniel","Nancy",
"Matthew","Betty","Anthony","Margaret","Mark","Sandra","Donald","Ashley",
"Steven","Dorothy","Andrew","Kimberly","Paul","Emily","Joshua","Donna",
"Kenneth","Michelle","Kevin","Carol","Brian","Amanda","George","Melissa",
"Timothy","Deborah","Ronald","Stephanie","Edward","Rebecca","Jason","Sharon",
"Jeffrey","Laura","Ryan","Cynthia","Jacob","Kathleen","Gary","Amy",
"Nicholas","Angela","Eric","Shirley","Jonathan","Anna","Stephen","Brenda",
"Larry","Pamela","Justin","Emma","Scott","Nicole","Brandon","Helen",
"Benjamin","Samantha","Samuel","Katherine","Raymond","Christine","Gregory","Debra",
"Frank","Rachel","Alexander","Carolyn","Patrick","Janet","Jack","Catherine",
"Dennis","Maria","Jerry","Heather","Tyler","Diane","Aaron","Ruth"]

LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
"Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
"Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
"White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
"Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
"Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell",
"Carter","Roberts","Phillips","Evans","Turner","Diaz","Parker","Cruz",
"Edwards","Collins","Reyes","Stewart","Morris","Morales","Murphy","Cook",
"Rogers","Gutierrez","Ortiz","Morgan","Cooper","Peterson","Bailey","Reed",
"Kelly","Howard","Ramos","Kim","Cox","Ward","Richardson","Watson",
"Brooks","Chavez","Wood","James","Bennett","Gray","Mendoza","Ruiz",
"Hughes","Price","Alvarez","Castillo","Sanders","Patel","Myers","Long",
"Ross","Foster","Jimenez","Powell","Jenkins","Perry","Russell","Sullivan"]

STREETS = ["Main St","Oak Ave","Maple Dr","Cedar Ln","Pine Rd","Elm St","Washington Blvd",
"Park Ave","Lake Dr","Hill Rd","River Rd","Church St","Spring St","High St",
"Union Ave","Market St","Academy Dr","Bridge St","Sunset Blvd","Broadway"]

CITIES_A = ["New York","Boston","Philadelphia","Hartford","Newark"]
CITIES_B = ["Los Angeles","San Francisco","Seattle","Portland","San Diego"]
STATES_A = ["NY","MA","PA","CT","NJ"]
STATES_B = ["CA","CA","WA","OR","CA"]
ACC_TYPES = ["Savings","Checking","Business"]


def create_schema(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS transactions CASCADE;")
    cur.execute("DROP TABLE IF EXISTS customers CASCADE;")
    cur.execute("DROP TABLE IF EXISTS branches CASCADE;")
    cur.execute("""
        CREATE TABLE branches (
            branchid CHAR(1) PRIMARY KEY,
            branchname VARCHAR(100) NOT NULL,
            location VARCHAR(200)
        );
    """)
    cur.execute("INSERT INTO branches VALUES ('A', 'Branch A - East Coast', 'New York, NY');")
    cur.execute("INSERT INTO branches VALUES ('B', 'Branch B - West Coast', 'Los Angeles, CA');")
    cur.execute("""
        CREATE TABLE customers (
            customerid INT PRIMARY KEY,
            fullname VARCHAR(100) NOT NULL,
            email VARCHAR(150),
            phone VARCHAR(20),
            address VARCHAR(200),
            account_type VARCHAR(20),
            account_balance DECIMAL(15,2),
            date_of_birth DATE,
            created_at DATE,
            homebranchid CHAR(1) NOT NULL,
            FOREIGN KEY (homebranchid) REFERENCES branches(branchid)
        );
    """)
    cur.execute("""
        CREATE TABLE transactions (
            txid SERIAL PRIMARY KEY,
            customerid INT NOT NULL,
            atm_branchid CHAR(1) NOT NULL,
            amount DECIMAL(15,2) NOT NULL,
            txdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            workload_day INT NOT NULL DEFAULT 1,
            FOREIGN KEY (atm_branchid) REFERENCES branches(branchid)
        );
    """)
    conn.commit()
    cur.close()


def generate_customer(cid, branch):
    fn = random.choice(FIRST)
    ln = random.choice(LAST)
    name = f"{fn} {ln}"
    email = f"{fn.lower()}.{ln.lower()}{cid}@bank.com"
    phone = f"({random.randint(200,999)}) {random.randint(100,999)}-{random.randint(1000,9999)}"

    if branch == 'A':
        ci = random.randint(0, len(CITIES_A)-1)
        city, state = CITIES_A[ci], STATES_A[ci]
    else:
        ci = random.randint(0, len(CITIES_B)-1)
        city, state = CITIES_B[ci], STATES_B[ci]

    addr = f"{random.randint(1,9999)} {random.choice(STREETS)}, {city}, {state}"
    acc_type = random.choice(ACC_TYPES)
    balance = round(random.uniform(100, 50000), 2)
    dob = f"{random.randint(1960,2003)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
    created = f"{random.randint(2020,2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

    return (cid, name, email, phone, addr, acc_type, balance, dob, created, branch)


def init_databases():
    print("=" * 60)
    print("  KHỞI TẠO DATABASE - Phân mảnh ngang Customers")
    print("=" * 60)

    sql = """INSERT INTO customers
        (customerid,fullname,email,phone,address,account_type,account_balance,date_of_birth,created_at,homebranchid)
        VALUES %s"""

    customers_a = []
    customers_b = []
    for i in range(1, TOTAL_CUSTOMERS + 1):
        branch = 'A' if random.random() < 0.5 else 'B'
        if branch == 'A':
            customers_a.append(generate_customer(i, 'A'))
        else:
            customers_b.append(generate_customer(i, 'B'))

    # ── Site A: chỉ chứa Branch A customers ──
    print(f"\n▶ Đang khởi tạo Site A ({len(customers_a)} Branch A customers)...")
    conn_a = psycopg2.connect(**SITE_A)
    create_schema(conn_a)
    cur_a = conn_a.cursor()
    
    if customers_a:
        execute_values(cur_a, sql, customers_a, page_size=10000)
    
    conn_a.commit()
    cur_a.execute("SELECT COUNT(*) FROM customers")
    cnt_a = cur_a.fetchone()[0]
    cur_a.close()
    conn_a.close()
    print(f"  ✅ Site A: {cnt_a} customers (all Branch A)")

    # ── Site B: chỉ chứa Branch B customers ──
    print(f"\n▶ Đang khởi tạo Site B ({len(customers_b)} Branch B customers)...")
    conn_b = psycopg2.connect(**SITE_B)
    create_schema(conn_b)
    cur_b = conn_b.cursor()
    
    if customers_b:
        execute_values(cur_b, sql, customers_b, page_size=10000)
    
    conn_b.commit()
    cur_b.execute("SELECT COUNT(*) FROM customers")
    cnt_b = cur_b.fetchone()[0]
    cur_b.close()
    conn_b.close()
    print(f"  ✅ Site B: {cnt_b} customers (all Branch B)")

    print(f"\n✅ KHỞI TẠO HOÀN TẤT — Tổng: {cnt_a + cnt_b} customers phân mảnh trên 2 site")


if __name__ == '__main__':
    init_databases()
