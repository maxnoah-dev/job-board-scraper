# Tài liệu kiến trúc kỹ thuật

**Phiên bản:** 1.0  
**Ngày:** 2026-07-15  
**Tác giả:** Kiến trúc sư kỹ thuật  
**Dựa trên:** PLAN.md (Phân tích nghiệp vụ)

---

## 1. Lựa chọn công nghệ

### 1.1 Ngôn ngữ: Python 3.11+

| Tiêu chí | Lựa chọn | Lý do |
|----------|----------|-------|
| **Ngôn ngữ chính** | Python 3.11+ | Hệ sinh thái phong phú cho scraping (BeautifulSoup, Playwright, Scrapy, httpx) |
| **Async Runtime** | asyncio + httpx | Xử lý đồng thời nhiều scraper cùng lúc |
| **Type Safety** | Pyright/Mypy | Đảm bảo tính nhất quán kiểu cho 11 adapter khác nhau |

### 1.2 Thư viện cốt lõi

```
Web Scraping:
├── httpx          # HTTP client bất đồng bộ (API scrapers)
├── beautifulsoup4 # Phân tích HTML (trang tĩnh)
├── playwright     # Tự động hoá trình duyệt (trang có anti-bot)
└── scrapy         # (tuỳ chọn) cho crawling phức tạp

Xử lý dữ liệu:
├── pydantic       # Kiểm tra và chuẩn hoá dữ liệu
├── pandas         # Thao tác dữ liệu
└── dateparser     # Phân tích ngày nhiều định dạng

Cơ sở dữ liệu:
├── sqlalchemy     # ORM (SQLite/PostgreSQL)
└── aiosqlite      # Thao tác SQLite bất đồng bộ

Scheduler & Cảnh báo:
├── apscheduler    # Lập lịch tác vụ
└── notifiers      # Thông báo Email/Slack
```

### 1.3 Công cụ phát triển

| Công cụ | Mục đích |
|------|---------|
| **Poetry** | Quản lý phụ thuộc |
| **Pytest + pytest-asyncio** | Khung kiểm thử |
| **Black + Ruff** | Định dạng mã & lint |
| **Pre-commit** | Git hooks |
| **Loguru** | Log có cấu trúc |

---

## 2. Kiến trúc hệ thống

### 2.1 Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BỘ ĐIỀU PHỐI                                   │
│                    (APScheduler + Event Loop)                            │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE ETL                                      │
│  ┌─────────┐    ┌─────────────┐    ┌────────────┐    ┌───────────────┐  │
│  │ TRÍCH    │───▶│ BIẾN ĐỔI    │───▶│ KHỬ TRÙNG  │───▶│ TẢI LÊN      │  │
│  │ XUẤT     │    │ (Chuẩn hoá  │    │ LẶP        │    │ (Cơ sở dữ   │  │
│  │ (11      │    │  + Validate) │    │ (Job_URL    │    │  liệu +     │  │
│  │ Adapter) │    │              │    │  unique)   │    │  Báo cáo)   │  │
│  └─────────┘    └─────────────┘    └────────────┘    └───────────────┘  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LỚP GIÁM SÁT                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ Theo dõi lỗi │  │ QLý cảnh báo│  │ Bộ thu thập chỉ số           │  │
│  │ (phát hiện   │  │ (Email/Slack)│  │ (tỉ lệ thành công, thời lượng)│ │
│  │  0 jobs)     │  │              │  │                              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Adapter Pattern (Kiến trúc Plugin)

```
adapters/
├── __init__.py
├── base.py              # Lớp cơ sở trừu tượng
├── protocols/
│   ├── api_adapter.py   # Tích hợp API/ATS
│   ├── html_adapter.py  # Trình cào HTML tĩnh
│   └── browser_adapter.py # Trang có anti-bot
└── implementations/
    ├── opswat_adapter.py      # API Adapter
    ├── vancity_adapter.py     # API Adapter
    ├── tiktok_adapter.py      # Browser Adapter
    ├── northrop_adapter.py    # Browser Adapter
    └── ... (7 adapter nữa)
```

### 2.3 Luồng dữ liệu

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nguồn     │────▶│   Adapter   │────▶│ Transformer │────▶│  JobRecord  │
│  (Dữ liệu   │     │  (Trích     │     │  (Làm sạch) │     │  chuẩn hoá  │
│   thô)      │     │   xuất)     │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                                       │
                           ▼                                       ▼
                    ┌─────────────┐                         ┌─────────────┐
                    │  Log lỗi   │                         │  Cơ sở dữ   │
                    │  (theo      │                         │  liệu       │
                    │   nguồn)    │                         │  (Upsert)   │
                    └─────────────┘                         └─────────────┘
```

---

## 3. Schema cơ sở dữ liệu

### 3.1 Quan hệ thực thể

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    companies     │       │      jobs        │       │   scrape_logs    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │◀──┐   │ id (PK)          │       │ id (PK)          │
│ name             │   │   │ company_id (FK)  │──────▶│ job_id (FK)      │
│ slug             │   │   │ title            │       │ scraped_at        │
│ adapter_type     │   └───│ location         │       │ status           │
│ config (JSON)    │       │ job_url          │       │ jobs_found       │
│ is_active        │       │ date_posted      │       │ error_message    │
│ created_at       │       │ status           │       │ duration_ms      │
│ updated_at       │       │ raw_data (JSON)   │       └──────────────────┘
└──────────────────┘       │ created_at       │
                           │ updated_at       │
                           │ last_seen_at     │
                           └──────────────────┘
```

### 3.2 Định nghĩa bảng

#### Bảng: `companies`
```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    adapter_type TEXT NOT NULL CHECK(adapter_type IN ('api', 'html', 'browser')),
    base_url TEXT NOT NULL,
    config JSON,  -- Cấu hình riêng cho adapter (headers, selectors, v.v.)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Bảng: `jobs`
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    location TEXT,
    job_url TEXT NOT NULL UNIQUE,
    date_posted DATE,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    raw_data JSON,  -- Dữ liệu gốc trước khi chuẩn hoá
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_posted ON jobs(date_posted);
```

#### Bảng: `scrape_logs`
```sql
CREATE TABLE scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('running', 'success', 'failed', 'partial')),
    jobs_found INTEGER DEFAULT 0,
    new_jobs INTEGER DEFAULT 0,
    closed_jobs INTEGER DEFAULT 0,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_company ON scrape_logs(company_id);
CREATE INDEX idx_logs_started ON scrape_logs(started_at);
```

---

## 4. Cấu trúc thư mục

```
job-board-scraper/
│
├── docs/                       # Tài liệu
│   ├── PLAN.md                 # Phân tích nghiệp vụ
│   └── TECHNICAL.md            # Tài liệu này
│
├── src/                        # Mã nguồn
│   ├── __init__.py
│   │
│   ├── core/                   # Logic ứng dụng cốt lõi
│   │   ├── __init__.py
│   │   ├── config.py           # Quản lý cấu hình
│   │   ├── database.py         # Kết nối cơ sở dữ liệu
│   │   └── logging.py          # Thiết lập logging
│   │
│   ├── etl/                    # Pipeline ETL
│   │   ├── __init__.py
│   │   ├── base.py             # Lớp ETL cơ sở
│   │   ├── extractor.py        # Điều phối trích xuất
│   │   ├── transformer.py      # Biến đổi dữ liệu
│   │   ├── loader.py           # Tải dữ liệu
│   │   └── deduplicator.py     # Logic khử trùng lặp
│   │
│   ├── adapters/               # Hệ thống plugin (Adapter Pattern)
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAdapter trừu tượng
│   │   ├── registry.py         # Registry của adapter
│   │   ├── protocols/
│   │   │   ├── __init__.py
│   │   │   ├── api_adapter.py   # Giao thức API
│   │   │   ├── html_adapter.py  # Giao thức cào HTML
│   │   │   └── browser_adapter.py # Giao thức tự động hoá trình duyệt
│   │   │
│   │   └── implementations/    # Adapter cụ thể
│   │       ├── __init__.py
│   │       ├── opswat_adapter.py
│   │       ├── vancity_adapter.py
│   │       ├── tiktok_adapter.py
│   │       ├── northrop_adapter.py
│   │       └── ...             # 7 adapter nữa
│   │
│   ├── models/                 # Mô hình dữ liệu (Pydantic + SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── job.py              # Schema JobRecord
│   │   ├── company.py          # Schema Company
│   │   └── scrape_log.py      # Schema ScrapeLog
│   │
│   ├── scheduler/              # Lập lịch tác vụ
│   │   ├── __init__.py
│   │   ├── scheduler.py        # Thiết lập APScheduler
│   │   └── jobs.py            # Định nghĩa tác vụ
│   │
│   ├── monitoring/             # Giám sát & Cảnh báo
│   │   ├── __init__.py
│   │   ├── alert_manager.py   # Điều phối cảnh báo
│   │   ├── metrics.py          # Thu thập chỉ số
│   │   └── detectors.py        # Phát hiện bất thường
│   │
│   └── utils/                  # Tiện ích
│       ├── __init__.py
│       ├── rate_limiter.py     # Giới hạn tần suất
│       ├── retry.py            # Logic retry
│       └── user_agents.py      # Luân phiên user agent
│
├── tests/                      # Bộ kiểm thử
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_adapters/
│   │   ├── test_transformer/
│   │   └── test_utils/
│   ├── integration/
│   │   └── test_etl_pipeline/
│   └── fixtures/              # Dữ liệu kiểm thử
│
├── scripts/                    # Script vận hành
│   ├── init_db.py             # Khởi tạo cơ sở dữ liệu
│   ├── seed_companies.py      # Gieo dữ liệu công ty
│   └── run_scrape.py          # Kích hoạt cào thủ công
│
├── config/                     # File cấu hình
│   ├── settings.yaml          # Cấu hình chính
│   └── adapters/              # Cấu hình theo adapter
│       ├── opswat.yaml
│       ├── tiktok.yaml
│       └── ...
│
├── logs/                       # Log ứng dụng
├── data/                       # File xuất (CSV, Excel)
│
├── pyproject.toml             # Cấu hình Poetry
├── README.md                  # Tài liệu dự án
└── .env.example               # Mẫu biến môi trường
```

---

## 5. Design pattern

### 5.1 Adapter Pattern (Hệ thống plugin)

```python
# Giao diện cơ sở - tất cả adapter phải implement
class BaseAdapter(ABC):
    @abstractmethod
    async def fetch_jobs(self) -> List[RawJobData]:
        pass

    @abstractmethod
    async def validate_response(self, response: Any) -> bool:
        pass

# Giao thức chuyên biệt cho 3 nhóm
class ApiAdapter(BaseAdapter):
    """Nhóm Dễ: Tích hợp API/ATS"""
    async def fetch_jobs(self) -> List[RawJobData]:
        ...

class HtmlAdapter(BaseAdapter):
    """Nhóm Trung bình: Cào HTML"""
    async def fetch_jobs(self) -> List[RawJobData]:
        ...

class BrowserAdapter(BaseAdapter):
    """Nhóm Khó: Trang có anti-bot"""
    async def fetch_jobs(self) -> List[RawJobData]:
        ...
```

### 5.2 Strategy Pattern (Transformer)

```python
# Mỗi công ty có strategy riêng để biến đổi
class TransformerStrategy(ABC):
    @abstractmethod
    def normalize(self, raw_data: RawJobData) -> JobRecord:
        pass

class TikTokTransformer(TransformerStrategy):
    def normalize(self, raw_data: RawJobData) -> JobRecord:
        # Logic riêng cho TikTok
        ...

class DefaultTransformer(TransformerStrategy):
    def normalize(self, raw_data: RawJobData) -> JobRecord:
        # Logic chung
        ...
```

### 5.3 Observer Pattern (Giám sát)

```python
# Trình lắng nghe cảnh báo đăng ký sự kiện
class AlertObserver(ABC):
    @abstractmethod
    async def on_alert(self, event: AlertEvent):
        pass

class EmailAlert(AlertObserver):
    async def on_alert(self, event: AlertEvent):
        ...

class SlackAlert(AlertObserver):
    async def on_alert(self, event: AlertEvent):
        ...

# AlertManager thông báo tất cả observer
class AlertManager:
    def __init__(self):
        self._observers: List[AlertObserver] = []

    def subscribe(self, observer: AlertObserver):
        self._observers.append(observer)

    async def notify(self, event: AlertEvent):
        await asyncio.gather(*[o.on_alert(event) for o in self._observers])
```

### 5.4 Repository Pattern (Truy cập dữ liệu)

```python
# Lớp trừu tượng giữa logic nghiệp vụ và cơ sở dữ liệu
class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert(self, job: JobRecord) -> Job:
        ...

    async def find_by_url(self, url: str) -> Optional[Job]:
        ...

    async def mark_stale_jobs_closed(self, company_id: int, seen_urls: Set[str]):
        ...
```

---

## 6. Quản lý cấu hình

### 6.1 Biến môi trường

```bash
# .env.example

# Cơ sở dữ liệu
DATABASE_URL=sqlite:///./data/jobs.db

# Lập lịch
SCHEDULE_CRON=0 2 * * *  # 2:00 sáng mỗi ngày
TIMEZONE=UTC

# Cảnh báo
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=admin@example.com
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/...

# Giới hạn tần suất
REQUEST_DELAY_MIN=2  # giây
REQUEST_DELAY_MAX=5  # giây

# Trình duyệt (Anti-bot)
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30000  # ms

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/scraper.log
```

### 6.2 Ví dụ cấu hình adapter

```yaml
# config/adapters/tiktok.yaml
adapter:
  type: browser
  enabled: true

scraper:
  wait_for_selectors:
    - ".job-card"
    - "[data-testid='job-list']"
  pagination:
    type: scroll
    max_pages: 10
    scroll_delay: 2000  # ms

rate_limit:
  min_delay: 3
  max_delay: 6

transform:
  title_field: "position"
  location_field: "location"
  date_format: "%Y-%m-%d"
```

---

## 7. Mô hình đồng thời

### 7.1 Kiến trúc bất đồng bộ

```
Vòng lặp sự kiện chính
│
├── asyncio.gather() - Chạy tất cả adapter đồng thời
│   │
│   ├── Adapter 1 (API) - nhanh, ~500ms
│   ├── Adapter 2 (HTML) - trung bình, ~2s
│   ├── Adapter 3 (Browser) - chậm, ~30s
│   └── ... (8 cái nữa)
│
└── Giới hạn Semaphore = 5 (tránh gây quá tải)
```

### 7.2 Chiến lược giới hạn tần suất

```
Giới hạn tần suất theo adapter:
┌─────────────────────────────────────────────────────┐
│ Adapter         │ Delay tối thiểu │ Delay tối đa │ Đồng thời tối đa │
├─────────────────────────────────────────────────────┤
│ API Adapters    │ 0.5s            │ 1s           │ 3            │
│ HTML Adapters   │ 2s              │ 4s           │ 2            │
│ Browser Adapters│ 3s              │ 6s           │ 1            │
└─────────────────────────────────────────────────────┘
```

---

## 8. Chiến lược xử lý lỗi

### 8.1 Phân loại lỗi

| Loại | Ví dụ | Chiến lược khôi phục |
|----------|---------|-------------------|
| **Tạm thời** | Timeout mạng | Retry 3 lần với exponential backoff |
| **Lỗi phân tích** | Không tìm thấy selector | Ghi cảnh báo, bỏ qua mục, tiếp tục |
| **Xác thực** | Phản hồi 401/403 | Cảnh báo admin, tắt adapter |
| **Anti-Bot** | Thử thách Cloudflare | Chuyển sang chế độ trình duyệt, cảnh báo admin |
| **Chất lượng dữ liệu** | Tìm thấy 0 công việc | Cảnh báo admin ngay |

### 8.2 Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time = None
        self.recovery_timeout = recovery_timeout

    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenError()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

---

## 9. Giám sát & Cảnh báo

### 9.1 Chỉ số cần theo dõi

```
Chỉ số tác vụ cào:
├── Tổng số công việc đã cào (mỗi run)
├── Số công việc mới phát hiện
├── Số công việc đã đóng (không thấy trong run hiện tại)
├── Thời lượng theo công ty
└── Tỉ lệ thành công/thất bại theo adapter

Chỉ số hệ thống:
├── Sức khoẻ scheduler (thời điểm chạy cuối)
├── Tốc độ tăng dung lượng cơ sở dữ liệu
├── Xu hướng tỉ lệ lỗi
└── Tình trạng khả dụng của adapter

Điều kiện kích hoạt cảnh báo:
├── Trả về 0 công việc (vấn đề chất lượng dữ liệu)
├── Tỉ lệ thất bại của adapter > 50%
├── Thời lượng run > ngưỡng
└── Lỗi kết nối cơ sở dữ liệu
```

### 9.2 Kênh cảnh báo

| Kênh | Trường hợp sử dụng |
|---------|----------|
| **Email** | Lỗi nghiêm trọng, cảnh báo 0 công việc |
| **Slack** | Cập nhật trạng thái thời gian thực |
| **File log** | Tất cả sự kiện để gỡ lỗi |

---

## 10. Chiến lược kiểm thử

### 10.1 Tháp kiểm thử

```
         ┌─────────────┐
         │     E2E     │  ← Kiểm thử toàn pipeline (1 adapter)
         │   Tests     │
         ├─────────────┤
         │ Tích hợp   │  ← Tích hợp Adapter + DB
         │   Tests     │
         ├─────────────┤
         │   Đơn vị   │  ← Từng thành phần
         │   Tests     │
         └─────────────┘
```

### 10.2 Mục tiêu phủ kiểm thử

| Thành phần | Mục tiêu |
|-----------|--------|
| Adapters | 80% |
| Transformer | 90% |
| Loader | 85% |
| Utils | 90% |

---

## 11. Cân nhắc bảo mật

1. **Giới hạn tần suất**: Tôn trọng máy chủ đích, tránh bị cấm IP
2. **Luân phiên User-Agent**: Mô phỏng trình duyệt thật
3. **Hỗ trợ Proxy**: (Tương lai) Luân phiên IP cho trang có anti-bot
4. **Lưu trữ credential**: Biến môi trường, không bao giờ hardcode
5. **Quyền riêng tư dữ liệu**: Không lưu PII ngoài URL công việc
6. **Kiểm tra request**: Kiểm tra mọi phản hồi từ bên ngoài

---

## 12. Tuỳ chọn triển khai

### 12.1 Phát triển cục bộ
```bash
# Một máy, cron job
python -m src.scheduler
```

### 12.2 Docker Container
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN poetry install --no-dev
COPY src/ ./src/
CMD ["python", "-m", "src.scheduler"]
```

### 12.3 Tuỳ chọn Cloud
- **AWS Lambda**: Serverless, triển khai theo adapter
- **Google Cloud Run**: Container hoá, tự động scale
- **Railway/Render**: Triển khai đơn giản

---

## 13. Tóm tắt

| Hạng mục | Quyết định |
|----------|----------|
| **Ngôn ngữ** | Python 3.11+ |
| **Kiến trúc** | ETL + Plugin/Adapter Pattern |
| **Cơ sở dữ liệu** | SQLite (dev) → PostgreSQL (prod) |
| **Async** | asyncio + httpx |
| **Tự động hoá trình duyệt** | Playwright |
| **Lập lịch** | APScheduler |
| **Kiểm thử** | pytest + pytest-asyncio |
| **Pattern trọng tâm** | Adapter Pattern, Strategy Pattern, Observer Pattern |

---

> **Bước tiếp theo:**
> 1. Khởi tạo cấu trúc dự án
> 2. Thiết lập Poetry + phụ thuộc
> 3. Triển khai schema cơ sở dữ liệu
> 4. Xây dựng lớp adapter cơ sở
> 5. Triển khai adapter đầu tiên (OPSWAT - dễ nhất)
> 6. Xây dựng pipeline ETL
> 7. Thêm giám sát & cảnh báo
> 8. Thêm scheduler
> 9. Viết kiểm thử
> 10. Triển khai
