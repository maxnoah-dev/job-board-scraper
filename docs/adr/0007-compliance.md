# ADR 0007 — Chính sách tuân thủ nguồn

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead + Product Owner
- Thay thế: không

## Bối cảnh

`PLAN.md` §4 nêu "vượt anti-bot" là rủi ro kỹ thuật thực sự với TikTok và Northrop Grumman. `TECHNICAL.md` §8 liệt kê "chuyển sang chế độ trình duyệt" là chiến lược khôi phục khi gặp thử thách anti-bot, đây là giá trị mặc định sai cho dự án ưu tiên tuân thủ.

Một trình cào dữ liệu phải tôn trọng quy tắc của từng mục tiêu. Bất kỳ điều gì khác đều khiến dự án đối mặt rủi ro pháp lý và uy tín vượt xa giá trị của một nguồn bổ sung.

## Quyết định

- Mọi nguồn liệt kê trong `docs/sources/manifest.md` phải có hồ sơ tuân thủ bằng văn bản (`docs/sources/compliance-notes.md`) bao gồm:
  1. Cho phép `robots.txt` đối với đường dẫn tuyển dụng.
  2. Tóm tắt Điều khoản Dịch vụ liên quan đến truy cập tự động.
  3. Nguồn có công bố API hay ATS không, và điều khoản có cấm rõ ràng việc cào trang HTML công khai hay không.
  4. Quyết định: `approved`, `needs-review`, `blocked`.
- **Không nguồn nào được triển khai cơ chế vượt anti-bot.** Trình duyệt headless chỉ được phép tải các trang công khai mà nguồn đã phục vụ cho khách truy cập chưa xác thực; không được mạo danh dấu vân tay thiết bị cụ thể, luân phiên proxy dân cư, hay giải CAPTCHA.
- Nguồn có trạng thái tuân thủ `needs-review` không thể bắt đầu công việc Giai đoạn 7 (trình duyệt) cho đến khi product owner đổi sang `approved` hoặc `blocked`.
- Nguồn đánh dấu `blocked` không được xuất hiện trong bất kỳ sản phẩm Giai đoạn 5+ nào. Adapter của nguồn bị chặn bị loại khỏi registry khi khởi động.
- Mỗi adapter phơi ra **kill switch** theo nguồn trong `config/adapters/<slug>.yaml` (`enabled: false`). Việc đặt switch là quyết định runtime; không cần đổi mã.
- Cột `compliance_status` trên manifest là nguồn sự thật duy nhất. Giai đoạn 0 phải kết thúc với cả 11 nguồn đã được đánh dấu.

## Các phương án đã xét

### Phương án 1: Triển khai vượt anti-bot cho TikTok và Northrop

- Ưu điểm: Thêm nhiều nguồn trong bản phát hành 1.
- Nhược điểm: Rủi ro pháp lý, rủi ro uy tín, rủi ro bị cấm IP, và lo ngại về đạo đức khi vi phạm chính sách truy cập rõ ràng của máy chủ đích.
- Lý do không chọn: Nằm ngoài phạm vi. Hoãn lại.

### Phương án 2: Cào âm thầm không có hồ sơ tuân thủ

- Ưu điểm: Ship nhanh hơn.
- Nhược điểm: Không thể kiểm toán, không thể bảo vệ trong review.
- Lý do không chọn: Hồ sơ có tài liệu là yêu cầu bản phát hành 1.

### Phương án 3: Một kill switch toàn cục

- Ưu điểm: Triển khai tầm thường.
- Nhược điểm: Không thể tắt một nguồn xấu mà không tắt cả pipeline.
- Lý do không chọn: Cần độ chi tiết theo nguồn cho câu chuyện cảnh báo ở Giai đoạn 8.

## Hệ quả

- Tích cực: Có thể kiểm toán, có thể bảo vệ, và có thể đảo ngược. Mỗi nguồn có thể tắt trong vài giây.
- Tiêu cực: Một số nguồn (TikTok, Northrop, và các nguồn có anti-bot mạnh khác) bị hoãn. Chúng có thể quay lại ở bản sau khi tìm được lối tuân thủ.
- Rủi ro: Kỹ sư tương lai có thể bị cám dỗ thêm bypass "chỉ để test". Giảm thiểu: kill switch được kiểm thử ở Giai đoạn 7, và registry từ chối nạp adapter có cờ bypass.

## Câu hỏi mở

- Không có tại M0. Danh sách hoãn nằm trong mục "Phạm vi hoãn" của `ROADMAP.md`.
