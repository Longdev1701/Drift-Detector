# Distributed Database Simulation - Conversation Log & Technical Summary

## 📅 Phiên làm việc: 16/05/2026

### 1. Mục tiêu dự án
Xây dựng hệ thống mô phỏng phát hiện và xử lý hiện tượng **Data Access Pattern Drift** (thay đổi mẫu truy cập dữ liệu) trong cơ sở dữ liệu phân tán. Hệ thống tập trung vào việc giám sát chỉ số **Locality of Reference (LR)** và thực hiện tái phân mảnh (Re-fragmentation) tự động khi hiệu năng giảm sút.

### 2. Các tính năng cốt lõi đã triển khai
- **Cố định dữ liệu gốc**: Loại bỏ việc sinh lại dữ liệu ngẫu nhiên mỗi lần chạy để đảm bảo tính nhất quán khi xuất file DB.
- **Cơ chế Undo Migration**: Tự động tạo bảng `backup` (customers_backup, transactions_backup) ngay trước khi chuyển đổi dữ liệu, cho phép khôi phục trạng thái ban đầu chỉ với 1 click.
- **Tùy chỉnh ngưỡng LR (Adjustable Threshold)**: Thêm ô nhập liệu trên UI cho phép thay đổi ngưỡng báo động (ví dụ từ 0.7 xuống 0.6) để quan sát sự thay đổi trạng thái của hệ thống trong thời gian thực.
- **Quản lý Transaction thủ công**: Hỗ trợ thêm (+) hoặc xóa (✕) giao dịch cho từng khách hàng cụ thể trong popup chi tiết để demo thao tác gây nhiễu dữ liệu.
- **Giao diện Dashboard hiện đại**: Sử dụng Dark Mode, Glassmorphism, tích hợp biểu đồ quan sát biến thiên LR giữa Day 1 và Day 30.

### 3. Logic kỹ thuật & Giải thích thuật toán
#### Locality of Reference (LR)
LR được tính bằng tỷ lệ giữa giao dịch tại chỗ (Local) trên tổng số giao dịch. 
- **Trước Migration**: Khách hàng ở Nhánh A nhưng giao dịch nhiều ở Nhánh B -> LR thấp (Drift Detected).
- **Sau Migration**: Khách hàng được chuyển sang Nhánh B -> Các giao dịch trước đây là "Remote" nay trở thành "Local" -> LR tăng lên (System Stable).

#### Hiện tượng "Sụt giảm LR Day 1" sau khi chuyển
Đây là một quan sát quan trọng: Khi dời hộ khẩu khách hàng dựa trên hành vi Day 30, dữ liệu lịch sử Day 1 (vốn thuộc về nhánh cũ) sẽ bị coi là Remote. Điều này minh chứng cho sự đánh đổi giữa tối ưu hóa hiện tại và tính đúng đắn của dữ liệu lịch sử trong hệ thống phân tán.

### 4. Đối chiếu học thuật (Research Mapping)
Hệ thống này áp dụng kết hợp các kỹ thuật từ các hệ quản trị CSDL tiên tiến:
- **Hệ thống SWORD**: Giám sát tỷ lệ phần trăm giao dịch phân tán và kích hoạt tái cấu hình dựa trên ngưỡng (Threshold).
- **Hệ thống E-Store**: Lập hồ sơ truy cập ở cấp độ phần tử (Tuple profiling) để định danh chính xác các khách hàng "nóng" cần di chuyển.

### 5. Cấu trúc thư mục tối ưu
- `app.py`: Backend Flask API xử lý logic chính.
- `config.py`: Cấu hình kết nối PostgreSQL.
- `db_scripts/`: Chứa các script khởi tạo và mô phỏng workload tách biệt.
- `templates/` & `static/`: Giao diện người dùng.

---
*Tài liệu này được tạo tự động để phục vụ việc lưu trữ lịch sử phát triển và hỗ trợ viết báo cáo đồ án.*




Dựa trên những gì chúng ta đã xây dựng trong đồ án của bạn, hệ thống của bạn khớp nhất với kỹ thuật Giám sát phần trăm giao dịch phân tán (Hệ thống SWORD), nhưng có bổ sung thêm các đặc điểm của Giám sát cấp độ phần tử (Hệ thống E-Store).

Cụ thể như sau:

1. Giống hệ thống SWORD nhất (Trọng tâm):
Nguyên lý: SWORD theo dõi tỷ lệ phần trăm các giao dịch phân tán (distributed transactions). Nếu tỷ lệ này tăng cao (vượt ngưỡng), nó sẽ kích hoạt tái cấu hình.
Dự án của bạn: Bạn đang theo dõi chỉ số Locality of Reference (LR). Thực chất LR chính là "nghịch đảo" của tỷ lệ giao dịch phân tán.
Giao dịch phân tán cao = LR thấp.
Bạn sử dụng một Ngưỡng (Threshold) cụ thể (ví dụ: 0.7). Khi LR tụt xuống dưới ngưỡng này, hệ thống của bạn sẽ đánh giá là workload đã bị "drift" (thay đổi) và yêu cầu Re-fragmentation.
2. Có sự kết hợp của hệ thống E-Store (Cấp độ phần tử):
Nguyên lý: E-Store theo dõi chi tiết từng phần tử dữ liệu (tuple) để biết cái nào "nóng" (truy cập nhiều) và cần di chuyển.
Dự án của bạn: Khi hệ thống phát hiện Drift, bạn không chỉ báo động chung chung mà còn trích xuất được danh sách Migration Candidates.
Bạn đang "lập hồ sơ" (profiling) cho từng khách hàng cụ thể (tương ứng với các tuple).
Bạn đếm xem khách hàng đó giao dịch ở ATM A bao nhiêu lần, ATM B bao nhiêu lần để quyết định khách hàng đó là "nóng" ở đâu và cần dời "hộ khẩu" về site nào.
Tóm lại, bạn có thể khẳng định trong báo cáo:
"Hệ thống sử dụng phương pháp giám sát dựa trên ngưỡng tỷ lệ giao dịch phân tán (tương tự mô hình SWORD), kết hợp với phân tích hành vi truy cập ở cấp độ phần tử dữ liệu (tương tự mô hình E-Store) để định danh chính xác các đối tượng cần di chuyển nhằm tối ưu hóa tính cục bộ của dữ liệu."

Cách tiếp cận này rất khoa học vì nó vừa có cái nhìn tổng thể (chỉ số LR toàn hệ thống) vừa có cái nhìn chi tiết (tỷ lệ remote của từng khách hàng).