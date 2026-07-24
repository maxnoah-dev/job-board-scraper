# Manifest nguồn

> Trạng thái: **Đã duyệt cho M0 với 4 nguồn đã biết và 7 vị trí hoãn.**
> Manifest này là nguồn sự thật duy nhất cho việc job-board scraper được phép chạm vào nguồn nào trong bản phát hành 1. Nguồn không có trong danh sách này nằm ngoài phạm vi. Bằng chứng tuân thủ nằm ở [`compliance-notes.md`](compliance-notes.md). Mọi quyết định tuân thủ được điều phối bởi [`../../adr/0007-compliance.md`](../../adr/0007-compliance.md).

## Các trường

| Trường | Ý nghĩa |
| --- | --- |
| `slug` | Định danh chữ thường canonical dùng trong DB và config |
| `display_name` | Tên hiển thị thân thiện |
| `careers_url` | Trang tuyển dụng công khai |
| `api_or_ats` | Hệ thống backend nếu biết (`Greenhouse`, `Workday`, `SmartRecruiters`, `Lever`, `Teamtailor`, custom API, none) |
| `adapter_type` | `api`, `html` hoặc `browser` |
| `expected_count_min/max` | Khoảng số lượng công việc ước tính từ mẫu gần đây |
| `auth_required` | `yes`/`no` — nguồn credential phải là biến môi trường |
| `rate_policy` | Khoảng cách tối thiểu giữa các yêu cầu, số yêu cầu đồng thời tối đa |
| `authoritative_snapshot` | `true` nếu trang danh sách của nguồn là danh sách canonical của mọi việc đang mở |
| `compliance_status` | `approved`, `needs-review`, `blocked`, `blocked-by-policy`, `blocked-pending-owner` |
| `fixtures_plan` | Phản hồi giả lập sẽ đến từ đâu |
| `owner` | Người xác nhận nguồn có thể cào |

## Nguồn

| slug | display_name | adapter_type | api_or_ats | careers_url | authoritative_snapshot | compliance_status | owner | ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opswat | OPSWAT | `api` | Greenhouse (cần xác nhận) | https://www.opswat.com/careers | true | `needs-review` | TBD | Xác nhận URL board chính xác và mô hình auth. Giai đoạn 4 chỉ dùng fixture giả lập. |
| vancity | Vancity | `api` | Workday (cần xác nhận) | https://jobs.vancity.com | true | `needs-review` | TBD | Xác nhận tenant Workday và truy cập công khai. Giai đoạn 5 chỉ dùng fixture giả lập. |
| tiktok | TikTok | `browser` | Tuỳ biến | https://careers.tiktok.com | true | `blocked-by-policy` | TBD | Hoãn cho bản phát hành 1 — xem `compliance-notes.md`. |
| northrop | Northrop Grumman | `browser` | Tuỳ biến | https://www.northropgrumman.com/careers | true | `blocked-by-policy` | TBD | Hoãn cho bản phát hành 1 — xem `compliance-notes.md`. |
| absolute-security | Absolute Security | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Được nêu trong `PLAN.md`; thiếu URL/ATS/owner. |
| farm-credit-canada | Farm Credit Canada | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Được nêu trong `PLAN.md`; thiếu URL/ATS/owner. |
| source-07 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Vị trí mở — product owner cung cấp. |
| source-08 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Vị trí mở — product owner cung cấp. |
| source-09 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Vị trí mở — product owner cung cấp. |
| source-10 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Vị trí mở — product owner cung cấp. |
| source-11 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Vị trí mở — product owner cung cấp. |

## Tóm tắt theo loại adapter

| adapter_type | nguồn (số lượng) | bật cho bản phát hành 1 | câu hỏi mở |
| --- | --- | --- | --- |
| `api` | 2 xác nhận (`opswat`, `vancity`) | có, fixture-first | Xác nhận tenant Greenhouse/Workday và truy cập công khai. |
| `html` | 0 xác nhận | có, chỉ khung | Sẽ suy ra từ các hàng `blocked-pending-owner` khi URL đã biết. |
| `browser` | 2 xác nhận (`tiktok`, `northrop`) | **không** | Cả hai bị hoãn qua `blocked-by-policy`; xem `compliance-notes.md`. |

## Tập nguồn hiệu lực bản phát hành 1

Sau khi áp dụng các quyết định tuân thủ trong `compliance-notes.md`:

- 0 nguồn `approved` tại thời điểm này.
- 2 nguồn `needs-review` và chỉ có thể tiến hành **chống lại** fixture giả lập.
- 2 nguồn `blocked-by-policy` và bị hoãn.
- 7 nguồn `blocked-pending-owner` và bị hoãn.

Do đó lát cắt dọc bản phát hành 1 (Giai đoạn 4) được triển khai hoàn toàn chống lại fixture OPSWAT giả lập. Truy cập mạng thật chỉ được bật sau khi product owner đổi một nguồn sang `approved`.

## Hợp đồng adapter theo nguồn (mẫu)

Với mỗi nguồn có trạng thái tuân thủ trở thành `approved`, sản phẩm Giai đoạn 0 phải bao gồm:

1. **Điều kiện đầu vào** — auth bắt buộc, tên biến môi trường, phạm vi.
2. **Endpoint danh sách** — mẫu URL và cơ chế phân trang.
3. **Ánh xạ trường** — trường thô → trường `JobRecord`.
4. **Canonicalize** — cách `Job_URL` và ngày được chuẩn hoá cho nguồn này.
5. **Khai báo authoritative snapshot** — tín hiệu thiếu việc có an toàn không?
6. **Chính sách tần suất** — ghi đè khoảng cách tối thiểu theo nguồn và đồng thời.
7. **Chế độ lỗi** — mã trạng thái HTTP/thay đổi DOM nào kích hoạt kết quả trình trích xuất nào (`success`, `partial`, `failed`, `empty_unverified`, `blocked_by_anti_bot`).
8. **Kế hoạch fixture** — fixture giả lập nào sẽ giữ CI tất định.

## Vướng mắc đang mở

- 7 nguồn (`absolute-security`, `farm-credit-canada`, `source-07..11`) cần product owner cung cấp thông tin trước khi có thể phân loại. Chúng chặn việc lập kế hoạch năng lực Giai đoạn 5–7 nhưng **không** chặn việc đóng Giai đoạn 0.
- `opswat` và `vancity` cần product owner xác nhận URL tenant ATS trước khi Giai đoạn 4/5 chạm vào mạng thật.
- `tiktok` và `northrop` bị hoãn cho đến khi tìm được lối tuân thủ hoặc product owner ký duyệt một thỏa thuận hợp tác.
