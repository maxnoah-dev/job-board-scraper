# ADR 0002 — Schema & Run model

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead
- Thay thế: không
- Liên quan: ADR-0003 (định danh công việc), ADR-0004 (đóng stale)

## Bối cảnh

`TECHNICAL.md` trộn lẫn bảng `scrape_logs` theo công ty với một ERD hiển thị `scrape_logs.job_id`, không nhất quán. Ngữ nghĩa chúng ta cần là:

- Một "run" cấp cao nhất bao trùm một lần gọi pipeline ETL.
- Với mỗi công ty được thử trong run đó, ta giữ các chỉ số theo công ty.
- Lịch sử xuất hiện của từng công việc **không** bắt buộc cho MVP và không được lưu trên `scrape_logs`.

## Quyết định

Áp dụng schema sau:

- `scrape_runs` — một bản ghi cho mỗi lần gọi pipeline (thủ công hoặc theo lịch).
  Các trường: `id`, `started_at`, `finished_at`, `status` (`running`,
  `success`, `partial`, `failed`, `cancelled`, `interrupted`),
  `triggered_by`, `notes`.
- `scrape_attempts` — một bản ghi cho mỗi `(run, company)`. Các trường: `id`,
  `run_id` (FK), `company_id` (FK), `started_at`, `finished_at`,
  `status`, `jobs_found`, `jobs_valid`, `records_rejected`, `new_jobs`,
  `closed_jobs`, `pages_fetched`, `requests_made`, `complete`,
  `authoritative_snapshot`, `error_type`, `error_message`, `warnings`.

Không có cột `job_id` trên `scrape_attempts`.

## Hệ quả

- Cách ly theo công ty được thể hiện tường minh; cách ly đồng thời/lỗi hoạt động trên `scrape_attempts`, không trên `scrape_logs`.
- Khôi phục mồ côi: khi khởi động, mọi `scrape_runs.status = 'running'` cũ hơn timeout run sẽ được đặt thành `interrupted`, và các `scrape_attempts` đang mở của nó trở thành `interrupted`.
- Lịch sử quan sát theo công việc trong tương lai (nếu cần) sẽ nằm ở bảng `job_observations` riêng để tránh phình `scrape_attempts`.

## Câu hỏi mở

- Không có.
