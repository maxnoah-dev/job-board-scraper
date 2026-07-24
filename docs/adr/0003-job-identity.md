# ADR 0003 — Định danh công việc & khử trùng lặp

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead
- Thay thế: không
- Liên quan: ADR-0002 (schema), ADR-0004 (đóng stale)

## Bối cảnh

Các công việc được cào từ nhiều nguồn không đồng nhất. Chúng ta cần một quy tắc tất định để quyết định một bản ghi cào được có đề cập đến cùng công việc mà ta đã lưu hay không. Quy tắc định danh sai sẽ gây ra cả trùng lặp âm thầm lẫn đóng oan các công việc hợp lệ.

`PLAN.md` §2 lấy `Job_URL` làm khoá khử trùng lặp. Ta phải quyết định hình dạng URL nào được coi là canonical, `source_job_id` do nguồn cung cấp có nên là duy nhất hay không, và việc khử trùng lặp có trải qua các công ty hay không.

## Quyết định

- Lưu cả URL thô của nguồn lẫn `canonical_url` trên mỗi bản ghi công việc.
  `canonical_url` là kết quả của bộ canonicalize theo nguồn (bỏ query UTM/tracking, bỏ fragment, hostname viết thường, chuẩn hoá dấu gạch chéo cuối, bỏ port mặc định).
- Ràng buộc duy nhất trên `(company_id, canonical_url)`.
- `source_job_id` tuỳ chọn với `UNIQUE (company_id, source_job_id)` chỉ được áp dụng khi nguồn cung cấp định danh ổn định. Nguồn tái sử dụng ID (ví dụ: ID Greenhouse ổn định; ID một số tenant Workday thì không) không áp dụng ràng buộc này.
- **Không khử trùng lặp xuyên công ty trong bản phát hành 1.** Một công việc mà cùng một người thấy ở hai công ty sẽ được ghi hai lần. Điều này được hoãn rõ ràng (xem mục "Phạm vi hoãn" trong `ROADMAP.md`).
- Transformer là nơi duy nhất tạo ra `canonical_url`. Adapter chỉ phát ra URL thô.

## Các phương án đã xét

### Phương án 1: Chỉ dùng `Job_URL`, không canonicalize

- Ưu điểm: Quy tắc đơn giản nhất, triển khai nhanh nhất.
- Nhược điểm: Hai bài đăng giống hệt nhưng khác tham số UTM sẽ thành hai bản ghi; liên kết chia sẻ lại tạo cảnh báo "công việc mới" giả.
- Lý do không chọn: Các bảng việc làm ngoài đời thực đều dùng tham số UTM khi chia sẻ trên mạng xã hội.

### Phương án 2: Băm `(title, company_id, location)` làm định danh

- Ưu điểm: Sống sót qua việc xáo trộn URL.
- Nhược điểm: Đụng độ trên các tiêu đề tương tự, thay đổi nhỏ về diễn đạt gây churn, rất khó gỡ lỗi.
- Lý do không chọn: URL là hợp đồng với ứng viên; ta phải giữ nguyên.

### Phương án 3: Khử trùng lặp xuyên công ty qua fuzzy matching

- Ưu điểm: Nhìn đẹp trên dashboard.
- Nhược điểm: Cần quy trình review thủ công, dương tính giả tốn kém vận hành, và nằm ngoài phạm vi bản phát hành 1.
- Lý do không chọn: Hoãn lại. Xem phần "Phạm vi hoãn" trong `ROADMAP.md`.

## Hệ quả

- Tích cực: Định danh tất định, tỉ lệ dương tính giả thấp, dễ gỡ lỗi.
- Tiêu cực: Thêm một cột bảng, thêm một canonicalizer cho mỗi nguồn.
- Rủi ro: Canonicalizer tệ trên một nguồn có thể tạo bản ghi trùng. Giảm thiểu: mỗi canonicalizer được kiểm thử đơn vị ở Giai đoạn 2 với fixture dương và âm, và kiểm thử tích hợp ở Giai đoạn 4 với OPSWAT.

## Câu hỏi mở

- Không có tại M0. Danh sách canonicalizer nằm cạnh config adapter nguồn (xem `docs/sources/manifest.md`).
