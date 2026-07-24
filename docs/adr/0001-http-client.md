# ADR 0001 — HTTP client

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead
- Thay thế: không

## Bối cảnh

`TECHNICAL.md` §1.1 ban đầu đề xuất `asyncio + aiohttp` làm runtime bất đồng bộ và `aiohttp` làm HTTP client mặc định. Đến khi dự án chuyển sang giai đoạn triển khai, chúng ta đã cần:

- Hỗ trợ HTTP/2 cho các endpoint ATS chỉ expose API danh sách qua HTTP/2 (một số tenant Workday và SmartRecruiters).
- Các hàm hỗ trợ `Timeout`, `Limits`, và vòng đời `AsyncClient` hạng nhất với hành vi có thể dự đoán được khi gặp `asyncio.CancelledError`.
- Một client duy nhất có thể dùng chung cho các adapter HTML tĩnh, để proxy headers, user-agent và tracing được cấu hình tập trung một chỗ.
- Type stubs vượt qua Pyright ở strict mode mà không cần monkey patching.

`httpx` đã đáp ứng đủ cả bốn yêu cầu. Việc trộn `aiohttp` và `httpx` sẽ thêm hai connection pool và hai bộ đặc thù (chunked encoding, proxy auth, chuẩn hoá header) mà không mang lại lợi ích rõ rệt.

`scrapy` và `pandas` vẫn được liệt kê là tuỳ chọn trong `TECHNICAL.md` §1.2, nhưng chúng kéo theo các phụ thuộc bắc cầu (Twisted, lxml, numpy) không cần thiết cho bất kỳ adapter nào trong manifest bản phát hành 1. Chúng được loại khỏi lõi.

## Quyết định

- Dùng `httpx.AsyncClient` làm HTTP client duy nhất cho tất cả các họ adapter (API, HTML, và các HTTP probe dự phòng cho trình duyệt).
- **Không** đưa `aiohttp` vào danh sách phụ thuộc.
- **Không** thêm `scrapy` hay `pandas` vào `pyproject.toml` cho đến khi có một use case cụ thể. Đánh giá lại qua ADR mới khi use case đó xuất hiện.
- Toàn bộ mã adapter phải đi qua wrapper `HttpClient` duy nhất (`src/utils/http.py`) — nơi quản lý vòng đời `httpx.AsyncClient`, cấu hình timeout, log có cấu trúc được che dấu, và phân loại retry.
- Header, cookie và tiêm credential theo từng nguồn nằm trên đối tượng config của adapter, không nằm trên client dùng chung.

## Các phương án đã xét

### Phương án 1: Dùng `aiohttp` cho mọi thứ

- Ưu điểm: Trưởng thành, hơi nhanh hơn trên HTTP/1.1 thuần, middleware session trưởng thành.
- Nhược điểm: Không có HTTP/2 native, câu chuyện Pyright yếu hơn, tách stack khỏi mọi mã HTTP probe do trình duyệt điều khiển.
- Lý do không chọn: HTTP/2 là yêu cầu bắt buộc đối với ít nhất một tenant ATS; chi phí bảo trì khi chạy hai HTTP stack vượt xa mọi lợi ích hiệu năng đơn lẻ.

### Phương án 2: `requests` + `asyncio.to_thread`

- Ưu điểm: API quen thuộc, cộng đồng lớn.
- Nhược điểm: I/O chặn bên dưới, phá vỡ event loop bất đồng bộ, không chia sẻ connection pool với các request do trình duyệt điều khiển.
- Lý do không chọn: Nó loại bỏ lý do chính mà chúng ta chọn Python 3.11+ cho dự án.

### Phương án 3: `scrapy` làm framework

- Ưu điểm: Crawler, khử trùng lặp và xuất feed có sẵn.
- Nhược điểm: Runtime dựa trên Twisted, mô hình crawler có chủ ý không khớp với cách tách adapter/ETL của chúng ta, bề mặt phụ thuộc lớn.
- Lý do không chọn: Chúng ta đã có kiến trúc ETL + plugin cố ý. Scrapy sẽ bắt chúng ta phải tái cấu trúc dự án theo mô hình crawler của nó.

## Hệ quả

- Tích cực: Một HTTP stack, timeout có thể dự đoán, header rate-limit dùng chung, tracing dùng chung, HTTP/2 khi server hỗ trợ.
- Tích cực: Pyright ở strict mode pass mà không cần `type: ignore` trên các đường dẫn HTTP.
- Tiêu cực: Phải tự viết các lớp retry và circuit-breaker (đã nằm trong phạm vi Giai đoạn 3).
- Rủi ro: Nếu `httpx` ngừng được bảo trì, chúng ta phải di trú toàn bộ stack. Giảm thiểu: giữ phụ thuộc phía sau interface `HttpClient` để bề mặt di trú nhỏ.

## Câu hỏi mở

- Không có tại M0. Sẽ xem lại nếu Giai đoạn 5/6 làm lộ ra tenant cần tính năng mà `httpx` không cung cấp.
