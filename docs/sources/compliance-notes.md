# Ghi chú tuân thủ nguồn

> Nguồn sự thật duy nhất cho việc mỗi nguồn trong manifest có được phép cào hay không, và dưới những ràng buộc nào. Mỗi mục bên dưới được tham chiếu từ `docs/sources/manifest.md` (cột compliance_status) và từ `config/adapters/<slug>.yaml` (cờ `enabled`).
>
> **Chính sách:** Không vượt anti-bot. Trình duyệt headless chỉ được phép tải các trang mà nguồn đã phục vụ cho khách truy cập chưa xác thực. Giải CAPTCHA, luân phiên proxy dân cư và mạo danh dấu vân tay nằm ngoài phạm vi. Xem `docs/adr/0007-compliance.md`.

## Chú giải trạng thái

| Trạng thái | Ý nghĩa |
| --- | --- |
| `approved` | Nguồn có thể được cào dưới các ràng buộc liệt kê trong file này |
| `needs-review` | Quyết định chưa được đưa ra; không cho phép công việc triển khai |
| `blocked` | Nguồn không được cào trong bản phát hành này; kill switch bị ép tắt |
| `blocked-by-policy` | Nguồn về mặt kỹ thuật cào được nhưng bị từ chối vì lý do tuân thủ (xem ADR-0007) |
| `blocked-pending-owner` | Nguồn thiếu thông tin bắt buộc từ product owner; không thể phân loại |

## Nguồn

### opswat — `needs-review`

- Owner: TBD (cần product owner xác nhận)
- URL tuyển dụng công khai: https://www.opswat.com/careers (cần xác nhận)
- ATS: Greenhouse (cần xác nhận)
- Đã rà `robots.txt`: chưa
- Tóm tắt ToS: chưa ghi nhận
- Quyết định: giữ `needs-review` cho đến khi owner ký duyệt. Công việc adapter cho Giai đoạn 4 chỉ được tiến hành chống lại fixture giả lập.

### vancity — `needs-review`

- Owner: TBD
- URL tuyển dụng công khai: https://jobs.vancity.com (cần xác nhận)
- ATS: Workday (cần xác nhận)
- Đã rà `robots.txt`: chưa
- Tóm tắt ToS: chưa ghi nhận
- Quyết định: giống opswat. Phát triển fixture-first cho đến khi owner đổi trạng thái.

### tiktok — `blocked-by-policy`

- Owner: TBD
- URL tuyển dụng công khai: https://careers.tiktok.com
- ATS: tuỳ biến (không được công bố công khai)
- `robots.txt`: đường dẫn tuyển dụng bị cấm đối với crawler đa dụng; dịch ngược SPA kích hoạt thử thách anti-bot.
- Tóm tắt ToS: Điều khoản chung của TikTok cấm truy cập tự động quy mô lớn vào các endpoint không được công bố công khai. Không có API công bố cho miền tuyển dụng.
- Quyết định: **hoãn cho bản phát hành 1.** Một adapter trình duyệt tôn trọng ToS này sẽ cần thỏa thuận chia sẻ dữ liệu rõ ràng với TikTok, hoặc bị giới hạn ở tần suất yêu cầu rất nhỏ làm mất giá trị của nguồn. Chúng ta không triển khai cơ chế vượt anti-bot.
- Hành động: giữ mục trong manifest để kiểm toán, đặt `enabled: false` trong `config/adapters/tiktok.yaml`, ghi lại quyết định trong mục "Phạm vi hoãn" của `ROADMAP.md`.

### northrop — `blocked-by-policy`

- Owner: TBD
- URL tuyển dụng công khai: https://www.northropgrumman.com/careers
- ATS: tuỳ biến (front-end Workday với anti-bot nặng ở back-end)
- `robots.txt`: đường dẫn tuyển dụng cho phép crawler chung nhưng front-end ứng dụng đưa ra thử thách kiểu Cloudflare khi chịu tải.
- Tóm tắt ToS: cấm rõ ràng truy cập tự động gây cản trở hoạt động bình thường của trang.
- Quyết định: **hoãn cho bản phát hành 1.** Lý do giống TikTok.
- Hành động: giống TikTok.

### absolute-security — `blocked-pending-owner`

- Owner: TBD
- URL tuyển dụng công khai: TBD (không được cung cấp trong `PLAN.md`)
- ATS: TBD
- Quyết định: không thể phân loại. Không cho phép công việc triển khai cho đến khi product owner cung cấp URL, ATS và ký duyệt.

### farm-credit-canada — `blocked-pending-owner`

- Owner: TBD
- URL tuyển dụng công khai: TBD (được nêu trong `PLAN.md` nhưng không cung cấp URL)
- ATS: TBD
- Quyết định: không thể phân loại. Use case "cảnh báo không có việc" trong `PLAN.md` §4 được giữ lại cho Giai đoạn 8; ta chỉ chưa biết công ty nào kích hoạt nó.

### source-07..source-11 — `blocked-pending-owner`

- Owner: TBD
- URL tuyển dụng công khai: TBD
- ATS: TBD
- Quyết định: vị trí giữ chỗ. Product owner cung cấp tên, URL, ATS và bằng chứng tuân thủ cho từng nguồn trước khi Giai đoạn 1 bắt đầu.

## Cách cập nhật file này

1. Cập nhật hàng phía trên.
2. Cập nhật hàng tương ứng trong `docs/sources/manifest.md`.
3. Cập nhật `config/adapters/<slug>.yaml` để cờ `enabled` khớp với trạng thái mới.
4. Thêm mục tiến độ vào `docs/ROADMAP.md`.
5. Không triển khai mã cho bất kỳ nguồn nào có trạng thái không phải `approved`.
