# ADR 0005 — Timestamps & database migration

- Trạng thái: Đã chấp nhận
- Ngày: 2026-07-15
- Giai đoạn: 0 (Phạm vi & Quyết định)
- Tác giả: Tech Lead
- Thay thế: không

## Bối cảnh

`PLAN.md` và `TECHNICAL.md` hiện chưa quy định chính sách múi giờ. Dự án phải chạy ở Việt Nam (UTC+7) và trong các môi trường CI/cloud mặc định theo UTC. Timestamp naive giả định "giờ địa phương" gây ra lỗi lệch N giờ rất khó gỡ.

Ngoài ra, dự án phải chạy trên SQLite cục bộ và PostgreSQL ở production. `TECHNICAL.md` liệt kê `SQLAlchemy` + `aiosqlite` nhưng chưa chốt cách áp dụng thay đổi schema.

## Quyết định

### Timestamps

- Mọi timestamp trong mã, log và cơ sở dữ liệu đều được lưu theo UTC.
- Mọi cột SQLAlchemy dùng `DateTime(timezone=True)`, ánh xạ sang `TIMESTAMP WITH TIME ZONE` trên PostgreSQL và chuỗi ISO-8601 trên SQLite.
- Mô hình Pydantic phơi ra trường `datetime` có nhận thức múi giờ; validator từ chối datetime naive với thông báo rõ ràng.
- CLI in timestamp theo UTC mặc định và chấp nhận cờ `--tz` chỉ dùng cho hiển thị.

### Migration

- Dùng **Alembic** làm công cụ migration có thẩm quyền. `metadata.create_all` của SQLAlchemy **không** phải giải pháp thay thế được chấp nhận cho môi trường `init_db` chạy trên dữ liệu đã tồn tại.
- Migration được kiểm thử trên cả SQLite và PostgreSQL trong Giai đoạn 2 (ma trận CI) và một lần nữa trong Giai đoạn 9 (cứng hoá bản phát hành).
- Mỗi file migration phải có cả `upgrade()` và `downgrade()` và phải đảo ngược được không mất dữ liệu đối với các cột ta quan tâm (URL, status, timestamps).

### Database engine

- Dev và test cục bộ: `sqlite+aiosqlite:///./data/jobs.db`.
- Production: `postgresql+asyncpg://...`, DSN được tiêm qua biến môi trường `DATABASE_URL`.
- Chỉ dùng API bất đồng bộ SQLAlchemy 2.x.

## Các phương án đã xét

### Phương án 1: Lưu giờ địa phương (Asia/Ho_Chi_Minh)

- Ưu điểm: Người vận hành ở Việt Nam dễ chịu.
- Nhược điểm: Trôi DST/giờ mùa hè ở môi trường khác, audit trail mơ hồ, khó tái lập CI.
- Lý do không chọn: UTC là giá trị mặc định an toàn duy nhất cho dự án đa múi giờ.

### Phương án 2: Chỉ `metadata.create_all()`, không Alembic

- Ưu điểm: Không cần công cụ migration.
- Nhược điểm: Không thể tiến hoá schema ở production mà không mất dữ liệu, không downgrade được, không có audit trail.
- Lý do không chọn: Giai đoạn 2 yêu cầu rõ Alembic.

### Phương án 3: File SQL thuần, không ORM migration tool

- Ưu điểm: Toàn quyền kiểm soát.
- Nhược điểm: Dễ trôi khỏi mô hình SQLAlchemy, khó kiểm thử hơn, không có autogenerate cho thay đổi nhỏ.
- Lý do không chọn: Alembic đã tích hợp sẵn với ORM ta chọn.

## Hệ quả

- Tích cực: Run tái lập được xuyên múi giờ; schema đảo ngược được; CI bắt drift sớm.
- Tiêu cực: Thêm một phụ thuộc (Alembic) và ma trận kiểm thử migration.
- Rủi ro: Chênh lệch kiểu PostgreSQL/SQLite. Giảm thiểu: kiểm thử hai engine ở Giai đoạn 2 chặn mọi migration.

## Câu hỏi mở

- Không có tại M0. Hình dạng ma trận CI được chốt ở Giai đoạn 9.
