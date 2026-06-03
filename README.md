# Hệ Thống Distributed Banking Ledger & Drift Detector

Hệ thống mô phỏng cơ sở dữ liệu phân tán (Distributed Database) dành cho hệ thống ngân hàng trực tuyến, tích hợp công cụ giám sát và tự động tối ưu hóa phân mảnh dữ liệu thông qua phát hiện độ lệch cục bộ (Drift Detection & Dynamic Re-Fragmentation) dựa trên chỉ số **Locality of Reference (LR)**.

Dự án này áp dụng các nguyên lý học thuật nâng cao về CSDL phân tán (như giám sát giao dịch dựa trên ngưỡng của **SWORD** kết hợp với lập hồ sơ dữ liệu ở cấp độ bản ghi của **E-Store**) để tự động phát hiện tình trạng suy giảm hiệu năng do khách hàng di chuyển địa lý hoặc thay đổi hành vi giao dịch, từ đó thực hiện tái phân mảnh động để tối ưu hóa truy vấn cục bộ.

---

## 📌 Tính Năng Nổi Bật

- **Mô phỏng Phân tán Đa Chi nhánh**: Sử dụng Docker chạy song song 2 phân vùng cơ sở dữ liệu độc lập (Site A - East Coast và Site B - West Coast) sử dụng PostgreSQL 15.
- **Phân mảnh Ngang (Horizontal Fragmentation)**:
  - Bảng `customers` được phân mảnh ngang dựa trên thuộc tính `homebranchid` ('A' -> Site A, 'B' -> Site B).
  - Bảng `transactions` được phân mảnh ngang dựa trên nơi thực hiện giao dịch `atm_branchid` ('A' -> Site A, 'B' -> Site B).
- **Giám sát Locality of Reference (LR)**: Đo lường tỷ lệ giao dịch nội vùng trên tổng số giao dịch nhằm đánh giá hiệu quả phân mảnh.
- **Phát Hiện Độ Lệch Phân Mảnh (Drift Detection)**: Tự động phát hiện khi chỉ số LR của từng khách hàng và toàn hệ thống giảm xuống dưới ngưỡng thiết lập (mặc định là `0.70`).
- **Tái Phân Mảnh Động (Dynamic Re-Fragmentation)**:
  - Tự động phát hiện các ứng viên (Customers) bị lệch dữ liệu (drift candidates).
  - Di chuyển thông tin khách hàng và toàn bộ lịch sử giao dịch của họ sang chi nhánh phù hợp hơn nhằm đưa chỉ số LR trở lại mức tối ưu.
  - Đảm bảo tính toàn vẹn dữ liệu, đồng bộ hóa sequence (`txid`) để tránh xung đột khoá ngoại và khoá chính.
- **Khôi phục Trạng thái (Undo/Rollback Migration)**: Hỗ trợ khôi phục lại trạng thái phân mảnh ban đầu bằng cơ chế backup tạm thời.
- **Giao diện Giám sát Glassmorphic Dashboard**: Dashboard trực quan với các biểu đồ gauge, bảng dữ liệu phân trang, tìm kiếm thời gian thực, quản lý giao dịch và điều hướng cấu hình tái phân mảnh.

---

## 🧱 Kiến Trúc Hệ Thống

Hệ thống được thiết kế theo mô hình client-server phân tán kết hợp với một Coordinator ở giữa điều phối các truy vấn phân tán:

```
               +----------------------------------------+
               |         Trình Duyệt (Web UI)           |
               | (HTML5, Vanilla CSS, JS Glassmorphism) |
               +-------------------+--------------------+
                                   | HTTP REST
                                   v
               +----------------------------------------+
               |            Flask Coordinator           |
               |     (Trung tâm điều phối & tính toán)  |
               +---------+--------------------+---------+
                         |                    |
            Port 5431    | PostgreSQL         | Port 5433
            Direct Conn  | (psycopg2)         | Direct Conn
                         v                    v
               +------------------+  +------------------+
               |  PostgreSQL Container  |  |  PostgreSQL Container  |
               |      [SITE_A]    |  |      [SITE_B]    |
               |   Branch A Data  |  |   Branch B Data  |
               +------------------+  +------------------+
```

### Chi tiết Mô hình Cơ sở Dữ liệu Phân tán

1. **Bảng `branches`**:
   - `branchid` (CHAR(1) PK): Chi nhánh `'A'` hoặc `'B'`.
   - `branchname` (VARCHAR(100)): Tên chi nhánh.
   - `location` (VARCHAR(200)): Vị trí địa lý.
2. **Bảng `customers`**:
   - `customerid` (INT PK): Mã định danh khách hàng.
   - Phân mảnh ngang: Khách hàng thuộc chi nhánh A nằm ở Site A, khách hàng thuộc chi nhánh B nằm ở Site B.
3. **Bảng `transactions`**:
   - `txid` (SERIAL PK): Mã giao dịch.
   - `atm_branchid` (CHAR(1) FK): Chi nhánh nơi cây ATM thực hiện giao dịch được đặt.
   - Phân mảnh ngang: Giao dịch phát sinh tại ATM chi nhánh A lưu trữ tại Site A, giao dịch phát sinh tại ATM chi nhánh B lưu trữ tại Site B.

---

## 📁 Cấu Trúc Dự Án

```
DDB_Project/
├── app.py                     # Flask backend - API endpoints & Logic Coordinator
├── config.py                  # Cấu hình kết nối CSDL và các tham số ngưỡng LR
├── docker-compose.yml         # Thiết lập container PostgreSQL cho 2 Sites (A & B)
├── requirements.txt           # Thư viện Python cần thiết (psycopg2, flask)
├── Distributed Database Project Proposal - Filled.docx # Tài liệu báo cáo dự án
├── datasetOfDriftDetector.rar # Dataset dự phòng của hệ thống
├── db_scripts/
│   ├── init_db.py             # Khởi tạo Schema và seed 5,000 customers ban đầu
│   └── simulate_workload.py   # Tạo dữ liệu giao dịch Day 1 (LR=0.90) và Day 30 (LR=0.40)
├── templates/
│   └── index.html             # Giao diện dashboard HTML
└── static/
    ├── app.js                 # Xử lý tương tác AJAX, cập nhật UI và API calls
    └── style.css              # Giao diện Glassmorphism CSS hiện đại, trực quan
```

---

## 🛠️ Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### Bước 1: Khởi động Cơ sở dữ liệu qua Docker
Yêu cầu máy tính cài đặt sẵn Docker và Docker Compose. Mở terminal tại thư mục gốc dự án và chạy:

```bash
docker-compose up -d
```
Lệnh này sẽ khởi chạy 2 container PostgreSQL:
- **Site A (East Coast)**: Port `5431`
- **Site B (West Coast)**: Port `5433`
- Tài khoản truy cập mặc định: User: `admin`, Password: `password123`, DB Name: `bank_db`

### Bước 2: Thiết lập môi trường Python
Khuyên dùng môi trường ảo (virtualenv) để tránh xung đột thư viện:

```bash
python -m venv venv
venv\Scripts\activate       # Trên Windows (Powershell/CMD)
# Hoặc: source venv/bin/activate trên Linux/macOS
```

Cài đặt các gói phụ thuộc:
```bash
pip install -r requirements.txt
```

### Bước 3: Khởi tạo Database và Seed dữ liệu khách hàng
Khởi tạo bảng và phân phối ngẫu nhiên 5,000 khách hàng về 2 site:

```bash
python db_scripts/init_db.py
```

### Bước 4: Tạo dữ liệu mô phỏng giao dịch (Workload Simulation)
Chạy kịch bản mô phỏng để tạo giao dịch cho 2 mốc thời gian:
- **Day 1 (Mặc định)**: Tỷ lệ giao dịch nội vùng cao (~90% giao dịch thực hiện tại ATM cùng chi nhánh với nơi mở tài khoản).
- **Day 30 (Lệch phân mảnh)**: Khách hàng di chuyển khiến tỷ lệ giao dịch nội vùng giảm mạnh xuống còn khoảng ~35-45%, kích hoạt cảnh báo Drift.

```bash
python db_scripts/simulate_workload.py
```

### Bước 5: Khởi chạy Ứng dụng Web
Khởi động Flask server:

```bash
python app.py
```
Truy cập vào ứng dụng qua trình duyệt tại địa chỉ: **[http://localhost:5000](http://localhost:5000)**

---

## 📊 Luồng Hoạt Động & Cơ Chế Drift Detection

1. **Phân tích Hiệu Năng (Day 1 vs Day 30)**:
   - Hệ thống quét lịch sử giao dịch và tính toán tỷ lệ Locality of Reference:
     $$\text{LR} = \frac{\text{Số giao dịch thực hiện tại ATM cùng chi nhánh (Nội vùng)}}{\text{Tổng số giao dịch của khách hàng}}$$
   - Tại màn hình **Drift Analysis**, người dùng dễ dàng so sánh biểu đồ hiệu năng hệ thống giữa Day 1 (khoẻ mạnh) và Day 30 (bị lệch hiệu năng).
2. **Tìm Kiếm Ứng Viên Di Trú (Migration Candidates)**:
   - Hệ thống lọc ra tất cả những khách hàng có chỉ số $LR < \text{Ngưỡng chỉ định}$ (mặc định là $0.70$).
   - Nếu đa số giao dịch của họ lại phát sinh ở ATM thuộc chi nhánh khác, họ sẽ được xếp vào danh sách cần tái phân mảnh động.
3. **Thực thi Tái Phân Mảnh (Dynamic Re-Fragmentation)**:
   - Khi kích hoạt lệnh **Migrate**, hệ thống sẽ:
     - Tạo bảng backup tạm thời (`customers_backup` và `transactions_backup`).
     - Di chuyển các hồ sơ khách hàng được chọn cùng toàn bộ lịch sử giao dịch liên quan từ Site cũ sang Site mới.
     - Cập nhật lại trường `homebranchid` của khách hàng đó theo chi nhánh mới để tối ưu truy vấn nội vùng cho tương lai.
     - Đồng bộ lại sequence tự động tăng `transactions_txid_seq` trên cả 2 site nhằm tránh xung đột dữ liệu khi thêm mới giao dịch sau này.
4. **Khôi Phục Trạng Thái (Undo)**:
   - Nếu muốn chạy lại mô phỏng hoặc hoàn tác, nút **Undo Migration** sẽ khôi phục dữ liệu nguyên trạng từ các bảng backup và đồng bộ lại sequence ID giao dịch.

---

## 🔌 API Reference (Cổng Tích Hợp)

Flask Coordinator cung cấp các API RESTful sau:

### Giám sát & Số liệu thống kê
* **`GET /api/overview`**: Trả về số lượng tổng quan khách hàng, giao dịch của từng site.
* **`GET /api/lr?threshold=<value>`**: Phân tích chỉ số LR toàn hệ thống cho Day 1 và Day 30.

### Quản lý Dữ liệu Phân tán
* **`GET /api/customers?site=<a|b>&page=<int>&search=<str>&branch=<str>`**: Lấy danh sách khách hàng phân trang, có bộ lọc từ khóa và chi nhánh.
* **`GET /api/customer/<id>/transactions`**: Truy vấn phân tán (Distributed Join) toàn bộ lịch sử giao dịch của khách hàng cụ thể trên cả 2 site.
* **`POST /api/customer/<id>/add-tx`**: Tạo mới giao dịch thủ công cho khách hàng tại ATM được chỉ định.
* **`DELETE /api/tx/<txid>/<site>`**: Xóa một giao dịch cụ thể tại site tương ứng.

### Tái Phân Mảnh & Phục Hồi
* **`GET /api/migration-candidates?threshold=<value>`**: Liệt kê các khách hàng có chỉ số LR dưới ngưỡng và gợi ý hướng di chuyển tối ưu.
* **`POST /api/migrate`**: Thực hiện chuyển dịch phân mảnh cho toàn bộ ứng viên được chọn.
* **`POST /api/undo`**: Hoàn tác quá trình di trú dữ liệu, phục hồi trạng thái phân mảnh gốc.

### Xuất báo cáo dữ liệu (CSV Export)
* **`GET /api/export/customers/<site>`**: Tải xuống danh sách khách hàng dưới dạng file CSV.
* **`GET /api/export/transactions/<site>`**: Tải xuống danh sách giao dịch dưới dạng file CSV.
* **`GET /api/export/candidates`**: Xuất danh sách ứng viên di trú sang file CSV.
* **`GET /api/export/drift`**: Xuất dữ liệu thống kê drift sang file CSV.
#   D r i f t - D e t e c t o r  
 