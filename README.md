# job-board-scraper

Pipeline ETL bất đồng bộ dùng để thu thập danh sách việc làm từ hơn 11 trang tuyển dụng của các công ty, tổng hợp về một cơ sở dữ liệu chuẩn hóa duy nhất. Được viết bằng Python 3.11+ trên nền tảng `asyncio`, `httpx`, `pydantic` và `SQLAlchemy 2`.

> **Trạng thái:** Giai đoạn 9 (Docker + PostgreSQL + CI cứng hóa) đã hoàn thành. Xem [docs/ROADMAP.md](docs/ROADMAP.md) để biết nguồn dữ liệu duy nhất về tiến độ.

## Kiến trúc

```
BỘ ĐIỀU PHỐI (lập lịch ngoài hoặc APScheduler)
   │
   ▼
PIPELINE ETL
   TRÍCH XUẤT (adapter) → BIẾN ĐỔI → KHỬ TRÙNG LẶP → TẢI LÊN → BÁO CÁO
   │
   ▼
GIÁM SÁT (AlertManager + MetricsCollector)
```

Ba họ adapter:

| Họ | Độ khó | Ví dụ (manifest hiện tại) |
| --- | --- | --- |
| API/ATS | thấp | OPSWAT, Vancity (bộ dữ liệu giả lập đến khi được duyệt) |
| HTML | trung bình | TechCorp, StartupXYZ (cào trang tĩnh) |
| Trình duyệt | cao | TikTok, Northrop Grumman — **hoãn đến bản phát hành 1** theo [ADR-0007](docs/adr/0007-compliance.md) |

Để đọc đầy đủ hợp đồng kiến trúc, xem [docs/TECHNICAL.md](docs/TECHNICAL.md); để đọc kế hoạch theo giai đoạn, xem [docs/ROADMAP.md](docs/ROADMAP.md).

## Cấu trúc thư mục

```
job-board-scraper/
├── pyproject.toml        # Metadata Poetry + cấu hình công cụ (ruff, pyright, pytest, coverage)
├── Dockerfile            # Image đa tầng: builder → runtime → runtime-browser
├── docker-compose.yml    # Stack phát triển cục bộ (PostgreSQL + scraper)
├── README.md             # Tài liệu này
├── .env.example          # Mẫu biến môi trường chỉ chứa giá trị giữ chỗ
├── docs/                 # PLAN.md, TECHNICAL.md, ROADMAP.md, ADR, manifest nguồn
├── src/                  # Mã nguồn ứng dụng
├── tests/                # Unit + integration + e2e
├── scripts/              # Script vận hành (init_db, seed_companies, run_scrape)
├── migrations/           # Migration schema Alembic
├── config/              # Cấu hình riêng cho từng adapter
├── data/                 # Cơ sở dữ liệu SQLite + báo cáo CSV
└── logs/                 # Log có cấu trúc
```

## Công cụ

| Công cụ | Mục đích |
| --- | --- |
| Python 3.11+ | Môi trường chạy |
| Poetry | Quản lý phụ thuộc và lockfile |
| Pydantic 2 / pydantic-settings 2 | Cấu hình + hợp đồng miền |
| pytest + pytest-asyncio + pytest-cov | Bộ chạy kiểm thử |
| Ruff | Trình kiểm tra và định dạng mã |
| Pyright | Kiểm tra kiểu tĩnh |
| detect-secrets | Trình quét bí mật |

## Hướng dẫn nhanh (phát triển cục bộ)

Các bước dưới đây giả định Python 3.11+ đã có trong PATH.

```powershell
# 1. Tạo môi trường ảo cục bộ (bỏ qua nếu .venv đã tồn tại)
python -m venv .venv

# 2. Cài đặt phụ thuộc runtime + phát triển
.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 3. Khởi tạo cơ sở dữ liệu (idempotent — an toàn khi chạy lại)
.venv\Scripts\python.exe scripts\init_db.py

# 4. Gieo dữ liệu công ty từ manifest nguồn (idempotent)
.venv\Scripts\python.exe scripts\seed_companies.py

# 5. Chạy scraper (tất cả công ty, chạy thử trước)
.venv\Scripts\python.exe scripts\run_scrape.py --dry-run
.venv\Scripts\python.exe scripts\run_scrape.py

# 6. Chạy bộ kiểm thử
.venv\Scripts\python.exe -m pytest

# 7. Kiểm tra định dạng / lint / kiểu
.venv\Scripts\python.exe -m ruff format .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pyright src tests
```

Nếu `.\.venv\Scripts\python.exe` đã có sẵn trong `PATH`, hãy bỏ phần tiền tố đó đi.

## Docker (khuyến nghị cho môi trường production)

Môi trường runtime production là **container chạy một lần** được điều khiển bởi bộ lập lịch ngoài (Kubernetes CronJob, Cloud Scheduler, v.v.) theo [ADR-0006](docs/adr/0006-scheduler-export.md).

### Build image

```bash
# Image tiêu chuẩn (không có tự động hóa trình duyệt)
docker build --target runtime -t job-board-scraper:latest .

# Image kèm Playwright + Chromium (chỉ cần khi các nguồn trình duyệt được duyệt)
docker build --target runtime-browser -t job-board-scraper:browser .
```

### Chạy với docker-compose (PostgreSQL cục bộ)

```bash
# Khởi động PostgreSQL và chạy scraper trỏ vào đó
docker compose up --build postgres scraper

# Chạy một lần cào thử (dry-run)
docker compose run --rm scraper python -m job_board_scraper.cli run --dry-run

# Chạy cho một công ty cụ thể
docker compose run --rm scraper python -m job_board_scraper.cli run -c opswat

# Khởi tạo cơ sở dữ liệu
docker compose run --rm scraper python -m job_board_scraper.cli init-db

# Gieo dữ liệu công ty
docker compose run --rm scraper python -m job_board_scraper.cli seed

# Xuất danh sách việc làm ra CSV
docker compose run --rm scraper python -m job_board_scraper.cli export -o /app/data/jobs.csv

# Truy cập shell của container
docker compose run --rm --entrypoint bash scraper
```

### Chạy độc lập (PostgreSQL ngoài)

```bash
# Thiết lập biến môi trường
export DATABASE_URL="postgresql+asyncpg://jobs:password@host:5432/jobs"
export LOG_LEVEL="INFO"

# Chạy
docker run --rm \
  -e DATABASE_URL \
  -e LOG_LEVEL \
  -v ./data:/app/data \
  -v ./logs:/app/logs \
  job-board-scraper:latest \
  python -m job_board_scraper.cli run
```

### Biến môi trường

| Biến | Mặc định | Mô tả |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/jobs.db` | Chuỗi kết nối cơ sở dữ liệu bất đồng bộ |
| `LOG_LEVEL` | `INFO` | Mức log tối thiểu |
| `LOG_FILE` | `./logs/scraper.log` | Đường dẫn file log |
| `SCHEDULER_ENABLED` | `false` | Bật APScheduler (chỉ dành cho môi trường cục bộ) |
| `PLAYWRIGHT_BROWSERS_INSTALLED` | `false` | Đặt true khi dùng target có trình duyệt |
| `ALERT_EMAIL_ENABLED` | `false` | Bật cảnh báo qua email |
| `ALERT_SLACK_WEBHOOK` | (rỗng) | URL webhook Slack |
| `EXPORT_DIR` | `./data` | Thư mục xuất CSV |

## Tham chiếu CLI

CLI hỗ trợ các lệnh con:

```bash
# Chạy cào
job-board-scraper run              # Tất cả công ty đang hoạt động
job-board-scraper run -c opswat   # Một công ty cụ thể
job-board-scraper run --dry-run   # Không ghi vào cơ sở dữ liệu

# Cơ sở dữ liệu
job-board-scraper init-db         # Tạo bảng
job-board-scraper seed            # Gieo dữ liệu công ty

# Xuất dữ liệu
job-board-scraper export          # Xuất việc đang tuyển ra CSV
job-board-scraper export --all    # Bao gồm cả việc đã đóng
```

Mã thoát: `0` = thành công, `1` = một phần, `2` = thất bại.

## Cấu hình

Cấu hình được điều khiển qua biến môi trường; không có bí mật nào được commit vào repo. Xem [`.env.example`](.env.example) để lấy mẫu giữ chỗ đầy đủ. Giá trị thật được lấy từ kho bí mật của người vận hành (Kubernetes Secret, AWS Secrets Manager, GitHub Actions secret, v.v.).

## Tùy chọn triển khai

| Mục tiêu | Cách thực hiện | Ghi chú |
| --- | --- | --- |
| Cục bộ / phát triển | Python trực tiếp + SQLite | `python scripts/run_scrape.py` |
| Cục bộ / giống production | docker compose + PostgreSQL | `docker compose up scraper` |
| Cloud / production | Container một lần + bộ lập lịch ngoài | Xem ADR-0006 |
| CI / kiểm thử | Ma trận GitHub Actions | Service PostgreSQL trong `.github/workflows/ci.yml` |

## Tuân thủ và chính sách nguồn

Chúng tôi không vượt qua kiểm soát truy cập, không giải CAPTCHA, không luân phiên proxy dân cư. Mỗi nguồn trong số 11 nguồn được liệt kê ở [docs/sources/manifest.md](docs/sources/manifest.md) đều có quyết định được viết rõ trong [docs/sources/compliance-notes.md](docs/sources/compliance-notes.md). Nguồn có trạng thái tuân thủ khác `approved` được nạp với `is_active: false` và không thể bật nếu không có ADR mới.

## Giấy phép

Sở hữu riêng — chỉ sử dụng nội bộ.
