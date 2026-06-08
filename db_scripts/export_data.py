"""
Script xuất dữ liệu từ các CSDL phân tán (Site A và Site B) ra các file CSV trong thư mục dataset.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv, psycopg2
from config import SITE_A, SITE_B

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dataset")

def export_table(site_name, site_config, table_name, file_name):
    print(f"▶ Đang xuất bảng {table_name} từ {site_name}...")
    try:
        conn = psycopg2.connect(**site_config)
        cur = conn.cursor()
        
        # Lấy thông tin các cột
        cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
        colnames = [desc[0] for desc in cur.description]
        
        # Lấy toàn bộ dữ liệu
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        # Tạo thư mục xuất nếu chưa có
        os.makedirs(EXPORT_DIR, exist_ok=True)
        filepath = os.path.join(EXPORT_DIR, file_name)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(colnames)  # Ghi header
            for row in rows:
                writer.writerow(row)
                
        print(f"  ✅ Đã xuất {len(rows)} dòng vào: dataset/{file_name}")
        cur.close(); conn.close()
    except Exception as e:
        print(f"  ❌ Lỗi khi xuất bảng {table_name} từ {site_name}: {e}")

def run_export():
    print("=" * 60)
    print("  BẮT ĐẦU XUẤT DỮ LIỆU PHÂN TÁN RA CSV")
    print("=" * 60)
    
    export_table("Site A", SITE_A, "customers", "customers_site_a.csv")
    export_table("Site A", SITE_A, "transactions", "transactions_site_a.csv")
    export_table("Site B", SITE_B, "customers", "customers_site_b.csv")
    export_table("Site B", SITE_B, "transactions", "transactions_site_b.csv")
    
    print("\n✅ Hoàn tất xuất dữ liệu! Tất cả các file nằm trong thư mục 'dataset'.")

if __name__ == '__main__':
    run_export()
