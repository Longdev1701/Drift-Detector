"""Cấu hình kết nối database và tham số hệ thống"""

SITE_A = {
    'host': 'localhost', 'port': 5431,
    'dbname': 'bank_db', 'user': 'admin', 'password': 'password123'
}

SITE_B = {
    'host': 'localhost', 'port': 5433,
    'dbname': 'bank_db', 'user': 'admin', 'password': 'password123'
}

LR_THRESHOLD = 0.70
TOTAL_CUSTOMERS = 5000
