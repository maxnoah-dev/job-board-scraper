# ADR-0008: Chrome cho các job board có anti-bot (TikTok, Northrop Grumman)

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-26
- Giai đoạn: 11
- Tác giả: Engineering Lead

## Bối cảnh

ADR-0007 hiện hành cấm scrape các site sử dụng anti-bot (Cloudflare, hCaptcha, FingerprintJS) để bảo vệ hệ thống khỏi rủi ro pháp lý và IP bị cấm. Tuy nhiên, trong Giai đoạn 11 chúng ta mở rộng danh sách công ty lên 11 nguồn, trong đó **TikTok** (`careers.tiktok.com`) và **Northrop Grumman** (`northropgrumman.com/careers`) sử dụng Cloudflare bot challenge + SPA, khiến adapter `ApiAdapter`/`HtmlAdapter` tiêu chuẩn không lấy được dữ liệu.

Khảo sát `docs/sources/manifest.md` cho thấy cả hai công ty đều có `compliance_status=blocked-by-policy` với lý do "blocked-by-policy" (ADR-0007). Để đáp ứng yêu cầu của user, cần có một ngoại lệ có kiểm soát cho phép scrape hai nguồn này bằng trình duyệt tự động với các biện pháp giảm thiểu rủi ro.

## Quyết định

**Cho phép sử dụng browser adapter (Playwright + stealth)** để scrape **chỉ hai nguồn**: `careers.tiktok.com` và `northropgrumman.com/careers`. Tất cả các site anti-bot khác vẫn chịu sự điều chỉnh của ADR-0007.

Các biện pháp bắt buộc:

1. **Headless mặc định** — `BROWSER_HEADLESS=true`; chỉ tắt khi debug trong môi trường local.
2. **Stealth plugin** — sử dụng `playwright-stealth` (hoặc tương đương) để giảm khả năng bị fingerprint.
3. **Không xoay proxy** — sử dụng IP egress của máy chủ; không mua bán residential proxy.
4. **Không giải CAPTCHA** — nếu gặp challenge hCaptcha/reCAPTCHA thì fail fast, log cảnh báo, không retry.
5. **Tần suất thấp** — rate limit ≤ 1 request / 5s, không vượt 100 request / 24h / nguồn.
6. **User-Agent thật** — chỉ dùng UA của Chrome stable hiện tại; không giả thiết bị di động.
7. **Lưu audit trail** — mỗi lần scrape phải ghi `scrape_logs` với `duration_ms`, `jobs_found`, `user_agent`, `proxy_id=direct`.
8. **Fail fast** — adapter trả về `ExtractionResult(success=False)` ngay khi phát hiện 403 / "Attention Required" / challenge wall, không retry.
9. **Tắt nguồn ngay khi 3 lần fail liên tiếp** — gửi alert tới admin, set `is_active=false` cho company trong DB.
10. **Hết hạn review** — ADR này có hiệu lực đến 2027-01-31; sau đó phải review lại dựa trên số lần bị block thực tế.

## Các phương án đã xét

### Phương án 1: Bỏ qua TikTok và Northrop Grumman

- **Ưu điểm**: Tuân thủ tuyệt đối ADR-0007, không có rủi ro pháp lý.
- **Nhược điểm**: User không nhận được 2/11 nguồn theo yêu cầu.
- **Lý do không chọn**: Plan Giai đoạn 11 cam kết đủ 11 công ty.

### Phương án 2: Dùng dịch vụ scraping third-party (ScrapingBee, Bright Data)

- **Ưu điểm**: Stealth headless browser do nhà cung cấp xử lý; giảm tải vận hành.
- **Nhược điểm**: Chi phí định kỳ, thêm PII (request routing qua bên thứ ba), chưa có ngân sách.
- **Lý do không chọn**: Vi phạm nguyên tắc "no third-party data sharing" trong `docs/sources/manifest.md`.

### Phương án 3: Browser adapter nội bộ với guardrail (Chấp nhận)

- **Ưu điểm**: Đáp ứng yêu cầu user, kiểm soát được hành vi, có audit trail.
- **Nhược điểm**: Có rủi ro IP bị cấm nếu vượt tần suất; tốn tài nguyên CPU/RAM.
- **Lý do chọn**: Cân bằng giữa giá trị nghiệp vụ và rủi ro; vẫn có thể thu hồi nếu 3 lần fail liên tiếp.

## Hệ quả

- **Tích cực**:
  - Đủ 11/11 nguồn hoạt động.
  - Có cơ chế auto-disable khi scrape bị chặn → giảm thiểu thiệt hại.
- **Tiêu cực**:
  - Tăng tải CPU/RAM trên máy chủ (Playwright headless ~200MB / instance).
  - Có thể bị Cloudflare cấm IP egress nếu vượt rate limit.
- **Rủi ro**:
  - Cloudflare cập nhật fingerprint → adapter ngừng hoạt động.
  - Tính hợp pháp của việc scrape bị tranh cãi (xem ADR-0007).
  - Ảnh hưởng sang các adapter khác nếu cùng chia sẻ IP egress.

## Câu hỏi mở

- Có nên đăng ký `robots.txt` watcher để tự động tắt khi công ty đổi chính sách?
- ADR-0007 nên được sửa để reference ADR-0008 hay giữ nguyên lịch sử?
- Có cần thiết lập proxy pool nội bộ (rotating datacenter IP) cho hai nguồn này?
