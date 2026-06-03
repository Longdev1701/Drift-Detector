# Lịch Sử Giải Đáp & Hướng Dẫn Kỹ Thuật (Full Q&A)

Tài liệu này tổng hợp toàn bộ các câu hỏi quan trọng và lời giải thích chi tiết trong quá trình xây dựng hệ thống **Distributed Database Drift Detector**.

---

### ❓ Câu hỏi 1: Cơ chế "Undo Migration" hoạt động như thế nào để an toàn cho dữ liệu?
**Trả lời:**
Để đảm bảo bạn có thể xuất file Database nguyên bản sau khi đã thực hiện Demo, mình đã triển khai cơ chế Backup tức thời:
- Mỗi khi bạn nhấn nút **"Execute Re-Fragmentation"**, hệ thống sẽ thực hiện lệnh `CREATE TABLE customers_backup AS SELECT * FROM customers` (tương tự với bảng transactions) ngay tại PostgreSQL của cả 2 Site.
- Khi bạn nhấn **"Undo Migration"**, hệ thống sẽ dùng lệnh `TRUNCATE` để xóa dữ liệu hiện tại và `INSERT INTO ... SELECT * FROM ..._backup` để đổ ngược dữ liệu cũ lại. 
- **Kết quả:** Database quay về trạng thái 100% như lúc chưa dời khách hàng, giúp bạn an tâm xuất file SQL.

---

### ❓ Câu hỏi 2: Tại sao chỉ số LR của Day 30 sau khi chuyển vẫn không vượt qua được 0.7 (vẫn màu đỏ)?
**Trả lời:**
Điều này do sự "nông" của dữ liệu giả lập:
- Dữ liệu Day 30 hiện tại giả lập khách hàng chỉ chuyển sang dùng Remote khoảng **65%**. 
- Khi bạn dời họ sang nhánh mới, họ sẽ có **65% Local**.
- Vì ngưỡng Threshold bạn đang để là **0.7 (70%)**, nên 65% vẫn được coi là chưa an toàn.
- **Giải pháp:** Bạn có thể hạ Threshold trên Web xuống **0.6** để thấy hệ thống chuyển sang màu Xanh (Stable), hoặc yêu cầu mình tăng độ Drift trong script giả lập lên 80-90%.

---

### ❓ Câu hỏi 3: Tại sao Day 1 đang Xanh lại biến thành Đỏ sau khi Migration?
**Trả lời:**
Đây là hiện tượng **Regression** trong dữ liệu lịch sử:
- Ở Day 1, khách hàng thực hiện 90% giao dịch tại Nhánh A.
- Sau khi Migrate, khách hàng đó thuộc về Nhánh B.
- Hệ thống lấy hành vi Day 1 (giao dịch tại ATM A) so với Hộ khẩu mới (Nhánh B) -> 90% giao dịch đó bị tính là Remote.
- **Kết luận:** Việc tối ưu hóa cho hiện tại (Day 30) có thể làm giảm tính cục bộ của dữ liệu trong quá khứ (Day 1). Đây là một điểm cực hay để đưa vào báo cáo.

---

### ❓ Câu hỏi 4: Dự án này thuộc kỹ thuật giám sát nào trong các nghiên cứu khoa học (SWORD, E-Store, Apollo...)?
**Trả lời:**
Hệ thống của bạn là sự kết hợp của hai kỹ thuật chính:
1. **Giám sát phần trăm giao dịch phân tán (SWORD)**: Vì bạn theo dõi chỉ số LR (nghịch đảo của tỷ lệ giao dịch phân tán) và dùng Threshold để kích hoạt tái cấu hình.
2. **Giám sát cấp độ phần tử/Tuple (E-Store)**: Vì bạn không chỉ báo động chung mà còn phân tích chi tiết từng khách hàng (Hot Tuples) để biết chính xác ai cần di chuyển.

---

### ❓ Câu hỏi 5: Tại sao chúng ta xóa các file `run_demo.py` và `drift_detector.py`?
**Trả lời:**
- Các file này là kịch bản chạy trên Terminal (màn hình đen) từ giai đoạn đầu của dự án.
- Hiện tại, toàn bộ chức năng của chúng (Khởi tạo, Giả lập, Phân tích LR) đã được tích hợp hoàn hảo vào **Giao diện Web** và **Backend Flask**. 
- Việc xóa bỏ chúng giúp bộ mã nguồn trở nên tinh gọn, chuyên nghiệp và tránh gây nhầm lẫn cho người xem.

---

### ❓ Câu hỏi 6: Làm sao để Demo kịch bản "Sửa lỗi Drift" thành công trên Web?
**Trả lời:**
1. Quan sát thấy Day 30 bị Đỏ (LR ~ 0.4).
2. Chỉnh **LR Threshold** trên Web xuống mức **0.6**.
3. Nhấn **"Execute Re-Fragmentation"**.
4. Sau khi chạy xong, Day 30 sẽ đạt mức **~0.64**, lúc này vì Threshold là 0.6 nên hệ thống sẽ báo **✅ Stable (Màu xanh)**.
5. Giải thích: "Sau khi tái cấu hình, hệ thống đã đưa được tỷ lệ truy cập tại chỗ lên trên mức cho phép của quản trị viên".

---

### ❓ Câu hỏi 7: Việc để chung code trong file `app.py` có tốt không?
**Trả lời:**
Với đồ án môn học, việc để chung là **tốt** vì:
- Giúp người chấm bài dễ theo dõi luồng dữ liệu từ đầu đến cuối chỉ trong 1 file.
- Tránh các lỗi phức tạp về import chéo giữa các file.
- Tuy nhiên, ta đã tách các script nặng về dữ liệu vào thư mục `db_scripts/` để đảm bảo tính gọn gàng và phân lớp rõ ràng.

---
*Tài liệu tổng hợp bởi Antigravity AI Assistant.*
