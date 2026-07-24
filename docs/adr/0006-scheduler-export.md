# ADR 0006 — Scheduler & xuất CSV

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead
- Thay thế: không

## Bối cảnh

`TECHNICAL.md` §7 xây dựng hệ thống xoay quanh `APScheduler` chạy cùng container với pipeline ETL. Trong thực tế, ta cần triển khai production được điều khiển bởi bộ lập lịch ngoài (cron, GitHub Actions, Argo, v.v.) để retry, đồng thời và khả năng quan sát nằm ngoài container ứng dụng. Ta cũng cần định dạng xuất có thể tái lập và an toàn.

## Quyết định

### Scheduler

- Production chạy dưới dạng **container Docker chạy một lần**, thoát với một trong các mã `success` / `partial` / `failed` sau một lần chạy ETL. Bộ lập lịch ngoài chịu trách nhiệm về tần suất và retry.
- `APScheduler` là **tuỳ chọn**, chỉ dùng cho chạy cục bộ đơn tiến trình trong phát triển và demo. Nó dùng lại cùng application service và run lock; không có code path riêng.
- Run lock đảm bảo chỉ một lần chạy ETL được thực thi tại một thời điểm trên mỗi cơ sở dữ liệu. Chạy thủ công và chạy theo lịch đều đi qua cùng lock nên không thể chồng lấn.
- Khôi phục mồ côi: khi khởi động, mọi `scrape_runs.status = 'running'` cũ hơn `RUN_TIMEOUT_SECONDS` sẽ được đánh dấu `interrupted` và các `scrape_attempts` đang mở của nó cũng được đánh dấu `interrupted`.

### Xuất CSV

- Xuất mặc định là **CSV**, UTF-8, quoting theo RFC 4180, thứ tự cột tất định, sắp xếp theo `(company_name, title, canonical_url)`.
- File xuất chỉ chứa **các cột đã chuẩn hoá**: `company_name`, `job_title`, `location`, `job_url`, `canonical_url`, `date_posted`, `status`, `first_seen_at`, `last_seen_at`. `raw_data` không bao giờ được xuất.
- Bộ lọc mặc định: `status = 'open'`. Cờ tuỳ chọn cho phép xuất mọi dòng, kể cả lịch sử đã đóng.
- Xuất **nguyên tử**: ghi vào file tạm cùng thư mục rồi đổi tên vào vị trí. File lỗi dang dở không bao giờ xuất hiện ở đường dẫn đích.
- Xuất **byte-for-byte tái lập** cho cùng một snapshot cơ sở dữ liệu; kiểm thử xuất ở Giai đoạn 8 khẳng định thuộc tính này.

## Các phương án đã xét

### Phương án 1: Container scheduler chạy dài

- Ưu điểm: Chỉ một binary để triển khai.
- Nhược điểm: Lỗi bị che sau tiến trình treo, không có sẵn cơ chế retry, khó scale ngang.
- Lý do không chọn: Bộ lập lịch ngoài là mẫu chuẩn cho ETL chạy một lần.

### Phương án 2: Xuất XLSX

- Ưu điểm: Tiện cho người xem không rành kỹ thuật.
- Nhược điểm: Định dạng nhị phân không tất định, khó diff trong code review, và `PLAN.md` không yêu cầu.
- Lý do không chọn: Hoãn sang bản phát hành sau.

### Phương án 3: JSON Lines thay vì CSV

- Ưu điểm: Dễ tiêu thụ bằng chương trình hơn.
- Nhược điểm: Không phải thứ các bên liên quan nghiệp vụ yêu cầu, khó mở trong bảng tính.
- Lý do không chọn: CSV là hợp đồng.

## Hệ quả

- Tích cực: Chế độ lỗi production đơn giản (một container, một exit code). Xuất có thể tái lập và dễ diff.
- Tiêu cực: Hai cách gọi pipeline (CLI + APScheduler). Giảm thiểu: cả hai đều đi qua cùng `RunService`.
- Rủi ro: Khôi phục mồ côi chỉ tốt bằng đồng hồ của cơ sở dữ liệu. Giảm thiểu: dùng `started_at` từ cơ sở dữ liệu, không phải đồng hồ container.

## Câu hỏi mở

- Không có tại M0. Schema xuất đã cố định; thêm cột cần một ADR.
