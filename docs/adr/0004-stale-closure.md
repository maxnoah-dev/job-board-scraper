# ADR 0004 — Chính sách đóng công việc stale

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead
- Thay thế: không
- Liên quan: ADR-0002 (schema), ADR-0003 (định danh công việc)

## Bối cảnh

`PLAN.md` §3 bước 4 nói rằng ta phải đóng các công việc "không còn xuất hiện trong lần cào mới nhất". Câu này nguy hiểm nếu hiểu theo nghĩa đen. Một run một phần (một adapter lỗi) hoặc kết quả rỗng từ adapter cấu hình sai không được phép đóng toàn bộ công việc của một công ty. Tương tự, một thử thách anti-bot tạm thời trả về 0 công việc không phải tín hiệu rằng mọi công việc đã được tuyển.

Ta cần một quy tắc tường minh ràng buộc việc đóng với *độ tin cậy* của run, không chỉ với sự vắng mặt.

## Quyết định

Một công việc đủ điều kiện chuyển sang trạng thái `closed` chỉ khi **tất cả** các điều sau đều đúng với run gần nhất đã quan sát công ty của nó:

1. `scrape_attempts.complete = true` (mọi trang/phản hồi kỳ vọng đã được xử lý, không chỉ một trang trả về rỗng).
2. `scrape_attempts.authoritative_snapshot = true` cho công ty đó (khai báo theo nguồn; xem `docs/sources/manifest.md`).
3. `(company_id, canonical_url)` của công việc **không** xuất hiện trong run hiện tại, và `missing_count` cấp run của công ty cho công việc đó ≥ 2 (mặc định `MAX_MISSES_BEFORE_CLOSE = 2`).
4. `last_seen_at` của công việc cũ hơn `started_at` của run.

Bước reconcile là nơi **duy nhất** đảo trạng thái `open → closed`. Adapter không bao giờ thay đổi `jobs.status`.

Một công việc xuất hiện lại sau khi đã đóng sẽ được mở lại (`closed → open`), và `last_seen_at` được đặt lại. Việc đóng không phá huỷ; các bản ghi lịch sử được giữ để kiểm tra.

Một run có `status` là `partial`, `failed`, `cancelled`, `interrupted`, hoặc có `authoritative_snapshot = false` sẽ **không** đóng góp vào bộ đếm `missing_count`.

## Các phương án đã xét

### Phương án 1: Đóng sau một lần vắng

- Ưu điểm: Đối chiếu nhanh nhất.
- Nhược điểm: Bất kỳ lỗi tạm thời nào cũng đóng mọi công việc đang mở của công ty đó. Thảm hoạ cho chất lượng dữ liệu.
- Lý do không chọn: Không vượt qua cổng "không âm thầm thất bại" ở Giai đoạn 8.

### Phương án 2: Đóng sau một khung thời gian cố định (ví dụ: 7 ngày không thấy)

- Ưu điểm: Theo thời gian, dễ giải thích.
- Nhược điểm: Độc lập với lịch cào thực tế, để công việc stale tồn tại qua run thành công tiếp theo, yêu cầu cron riêng.
- Lý do không chọn: Ta đã có tín hiệu run; dùng nó chính xác hơn.

### Phương án 3: Chỉ đóng thủ công

- Ưu điểm: Không đóng oan.
- Nhược điểm: Tốn công vận hành, vô hiệu hoá mục đích tự động hoá, và `PLAN.md` yêu cầu rõ đóng tự động.
- Lý do không chọn: Nằm ngoài mục tiêu bản phát hành.

## Hệ quả

- Tích cực: An toàn theo mặc định. Run một phần và run thất bại không thể vô tình đóng công việc. Hỗ trợ mở lại khi phát hiện lại.
- Tiêu cực: Công việc có thể giữ trạng thái "open" thêm một chu kỳ run sau khi biến mất. Đây là cái giá của sự an toàn và đã được ghi trong runbook.
- Rủi ro: Một nguồn không bao giờ tạo ra kết quả `authoritative_snapshot = true` sẽ không bao giờ đóng công việc. Giảm thiểu: cờ authoritative theo nguồn được rà soát ở Giai đoạn 0 và xem lại ở Giai đoạn 8.

## Câu hỏi mở

- Không có tại M0. Ngưỡng được cấu hình qua biến môi trường (`MAX_MISSES_BEFORE_CLOSE`).
