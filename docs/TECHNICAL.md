# Technical Architecture Document

**Version:** 1.0  
**Date:** 2026-07-15  
**Author:** Technical Architect  
**Based on:** PLAN.md (Business Analysis)

---

## 1. Tech Stack Selection

### 1.1 Language: Python 3.11+

| Tiêu chí | Lựa chọn | Lý do |
|----------|----------|-------|
| **Ngôn ngữ chính** | Python 3.11+ | Rich ecosystem cho scraping (BeautifulSoup, Playwright, Scrapy, httpx) |
| **Async Runtime** | asyncio + aiohttp | Xử lý concurrent nhiều scraper cùng lúc |
| **Type Safety** | Pyright/Mypy | Đảm bảo type consistency cho 11 adapters khác nhau |

### 1.2 Core Libraries

```
Web Scraping:
├── httpx          # Async HTTP client (API scrapers)
├── beautifulsoup4 # HTML parsing (static pages)
├── playwright     # Browser automation (anti-bot sites)
└── scrapy         # (optional) cho complex crawling

Data Processing:
├── pydantic       # Data validation & standardization
├── pandas         # Data manipulation
└── dateparser     # Multi-format date parsing

Database:
├── sqlalchemy     # ORM (SQLite/PostgreSQL)
└── aiosqlite      # Async SQLite operations

Scheduler & Alerts:
├── apscheduler    # Job scheduling
└── notifiers      # Email/Slack notifications
```

### 1.3 Development Tools

| Tool | Purpose |
|------|---------|
| **Poetry** | Dependency management |
| **Pytest + pytest-asyncio** | Testing framework |
| **Black + Ruff** | Code formatting & linting |
| **Pre-commit** | Git hooks |
| **Loguru** | Structured logging |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR                                   │
│                    (APScheduler + Event Loop)                            │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ETL PIPELINE                                      │
│  ┌─────────┐    ┌─────────────┐    ┌────────────┐    ┌───────────────┐  │
│  │ EXTRACT │───▶│ TRANSFORM   │───▶│ DEDUPE     │───▶│ LOAD          │  │
│  │ (11     │    │ (Normalize │    │ (Job_URL   │    │ (Database +   │  │
│  │ Adapters)│    │  + Validate)│    │  unique)   │    │  Report)      │  │
│  └─────────┘    └─────────────┘    └────────────┘    └───────────────┘  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MONITORING LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ Error Tracker│  │ Alert Manager│  │ Metrics Collector            │  │
│  │ (0 jobs      │  │ (Email/Slack)│  │ (success rate, duration)      │  │
│  │  detection)  │  │              │  │                              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Adapter Pattern (Plugin Architecture)

```
adapters/
├── __init__.py
├── base.py              # Abstract base class
├── protocols/
│   ├── api_adapter.py   # API/ATS integrations
│   ├── html_adapter.py  # Static HTML scrapers
│   └── browser_adapter.py # Anti-bot sites
└── implementations/
    ├── opswat_adapter.py      # API Adapter
    ├── vancity_adapter.py     # API Adapter
    ├── tiktok_adapter.py      # Browser Adapter
    ├── northrop_adapter.py    # Browser Adapter
    └── ... (7 more adapters)
```

### 2.3 Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Source    │────▶│   Adapter   │────▶│ Transformer │────▶│  Normalized │
│  (Raw Data) │     │  (Extract)  │     │  (Clean)    │     │  JobRecord  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                                       │
                           ▼                                       ▼
                    ┌─────────────┐                         ┌─────────────┐
                    │ Error Log   │                         │  Database   │
                    │ (per source)│                         │  (Upsert)  │
                    └─────────────┘                         └─────────────┘
```

---

## 3. Database Schema

### 3.1 Entity Relationship

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

### 3.2 Tables Definition

#### Table: `companies`
```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    adapter_type TEXT NOT NULL CHECK(adapter_type IN ('api', 'html', 'browser')),
    base_url TEXT NOT NULL,
    config JSON,  -- Adapter-specific config (headers, selectors, etc.)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Table: `jobs`
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    location TEXT,
    job_url TEXT NOT NULL UNIQUE,
    date_posted DATE,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    raw_data JSON,  -- Original data before normalization
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_posted ON jobs(date_posted);
```

#### Table: `scrape_logs`
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

## 4. Directory Structure

```
job-board-scraper/
│
├── docs/                       # Documentation
│   ├── PLAN.md                 # Business Analysis
│   └── TECHNICAL.md            # This document
│
├── src/                        # Source code
│   ├── __init__.py
│   │
│   ├── core/                   # Core application logic
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database connection
│   │   └── logging.py          # Logging setup
│   │
│   ├── etl/                    # ETL Pipeline
│   │   ├── __init__.py
│   │   ├── base.py             # Base ETL class
│   │   ├── extractor.py        # Extraction orchestration
│   │   ├── transformer.py      # Data transformation
│   │   ├── loader.py           # Data loading
│   │   └── deduplicator.py     # Deduplication logic
│   │
│   ├── adapters/               # Plugin System (Adapter Pattern)
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract BaseAdapter
│   │   ├── registry.py         # Adapter registry
│   │   ├── protocols/
│   │   │   ├── __init__.py
│   │   │   ├── api_adapter.py   # API protocol
│   │   │   ├── html_adapter.py  # HTML scraping protocol
│   │   │   └── browser_adapter.py # Browser automation protocol
│   │   │
│   │   └── implementations/    # Concrete adapters
│   │       ├── __init__.py
│   │       ├── opswat_adapter.py
│   │       ├── vancity_adapter.py
│   │       ├── tiktok_adapter.py
│   │       ├── northrop_adapter.py
│   │       └── ...             # 7 more adapters
│   │
│   ├── models/                 # Data models (Pydantic + SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── job.py              # JobRecord schema
│   │   ├── company.py          # Company schema
│   │   └── scrape_log.py      # ScrapeLog schema
│   │
│   ├── scheduler/              # Job scheduling
│   │   ├── __init__.py
│   │   ├── scheduler.py        # APScheduler setup
│   │   └── jobs.py            # Job definitions
│   │
│   ├── monitoring/             # Monitoring & Alerting
│   │   ├── __init__.py
│   │   ├── alert_manager.py   # Alert dispatching
│   │   ├── metrics.py          # Metrics collection
│   │   └── detectors.py        # Anomaly detection
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── rate_limiter.py     # Rate limiting
│       ├── retry.py            # Retry logic
│       └── user_agents.py      # User agent rotation
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_adapters/
│   │   ├── test_transformer/
│   │   └── test_utils/
│   ├── integration/
│   │   └── test_etl_pipeline/
│   └── fixtures/              # Test data
│
├── scripts/                    # Operational scripts
│   ├── init_db.py             # Database initialization
│   ├── seed_companies.py      # Seed company data
│   └── run_scrape.py          # Manual scrape trigger
│
├── config/                     # Configuration files
│   ├── settings.yaml          # Main settings
│   └── adapters/              # Per-adapter configs
│       ├── opswat.yaml
│       ├── tiktok.yaml
│       └── ...
│
├── logs/                       # Application logs
├── data/                       # Export files (CSV, Excel)
│
├── pyproject.toml             # Poetry configuration
├── README.md                  # Project documentation
└── .env.example               # Environment template
```

---

## 5. Design Patterns

### 5.1 Adapter Pattern (Plugin System)

```python
# Base interface - tất cả adapters phải implement
class BaseAdapter(ABC):
    @abstractmethod
    async def fetch_jobs(self) -> List[RawJobData]:
        pass

    @abstractmethod
    async def validate_response(self, response: Any) -> bool:
        pass

# Specialized protocols cho 3 nhóm
class ApiAdapter(BaseAdapter):
    """Nhóm Dễ: API/ATS integrations"""
    async def fetch_jobs(self) -> List[RawJobData]:
        ...

class HtmlAdapter(BaseAdapter):
    """Nhóm Trung bình: HTML scraping"""
    async def fetch_jobs(self) -> List[RawJobData]:
        ...

class BrowserAdapter(BaseAdapter):
    """Nhóm Khó: Anti-bot sites"""
    async def fetch_jobs(self) -> List[RawJobData]:
        ...
```

### 5.2 Strategy Pattern (Transformer)

```python
# Mỗi company có strategy riêng để transform
class TransformerStrategy(ABC):
    @abstractmethod
    def normalize(self, raw_data: RawJobData) -> JobRecord:
        pass

class TikTokTransformer(TransformerStrategy):
    def normalize(self, raw_data: RawJobData) -> JobRecord:
        # TikTok-specific logic
        ...

class DefaultTransformer(TransformerStrategy):
    def normalize(self, raw_data: RawJobData) -> JobRecord:
        # Generic logic
        ...
```

### 5.3 Observer Pattern (Monitoring)

```python
# Alert listeners subscribe to events
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

# AlertManager notifies all observers
class AlertManager:
    def __init__(self):
        self._observers: List[AlertObserver] = []

    def subscribe(self, observer: AlertObserver):
        self._observers.append(observer)

    async def notify(self, event: AlertEvent):
        await asyncio.gather(*[o.on_alert(event) for o in self._observers])
```

### 5.4 Repository Pattern (Data Access)

```python
# abstraction layer between business logic and database
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

## 6. Configuration Management

### 6.1 Environment Variables

```bash
# .env.example

# Database
DATABASE_URL=sqlite:///./data/jobs.db

# Scheduler
SCHEDULE_CRON=0 2 * * *  # 2:00 AM daily
TIMEZONE=UTC

# Alerting
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=admin@example.com
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/...

# Rate Limiting
REQUEST_DELAY_MIN=2  # seconds
REQUEST_DELAY_MAX=5  # seconds

# Browser (Anti-bot)
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30000  # ms

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/scraper.log
```

### 6.1 Adapter Configuration Example

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

## 7. Concurrency Model

### 7.1 Async Architecture

```
Main Event Loop
│
├── asyncio.gather() - Chạy tất cả adapters concurrently
│   │
│   ├── Adapter 1 (API) - fast, ~500ms
│   ├── Adapter 2 (HTML) - medium, ~2s
│   ├── Adapter 3 (Browser) - slow, ~30s
│   └── ... (8 more)
│
└── Semaphore limit = 5 (prevent overwhelming)
```

### 7.2 Rate Limiting Strategy

```
Per-Adapter Rate Limiting:
┌─────────────────────────────────────────────────────┐
│ Adapter         │ Min Delay │ Max Delay │ Max Conc  │
├─────────────────────────────────────────────────────┤
│ API Adapters    │ 0.5s      │ 1s        │ 3         │
│ HTML Adapters   │ 2s        │ 4s        │ 2         │
│ Browser Adapters│ 3s        │ 6s        │ 1         │
└─────────────────────────────────────────────────────┘
```

---

## 8. Error Handling Strategy

### 8.1 Error Categories

| Category | Example | Recovery Strategy |
|----------|---------|-------------------|
| **Transient** | Network timeout | Retry 3x with exponential backoff |
| **Parse Error** | Selector not found | Log warning, skip item, continue |
| **Authentication** | 401/403 response | Alert admin, disable adapter |
| **Anti-Bot** | Cloudflare challenge | Switch to browser mode, alert admin |
| **Data Quality** | 0 jobs found | Alert admin immediately |

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

## 9. Monitoring & Alerting

### 9.1 Metrics to Track

```
Scrape Job Metrics:
├── Total jobs scraped (per run)
├── New jobs discovered
├── Jobs closed (not seen in current run)
├── Duration per company
└── Success/failure rate per adapter

System Metrics:
├── Scheduler health (last run time)
├── Database size growth
├── Error rate trend
└── Adapter availability

Alert Triggers:
├── 0 jobs returned (data quality issue)
├── Adapter failure rate > 50%
├── Run duration > threshold
└── Database connection failure
```

### 9.2 Alert Channels

| Channel | Use Case |
|---------|----------|
| **Email** | Critical failures, 0 jobs alert |
| **Slack** | Real-time status updates |
| **Log file** | All events for debugging |

---

## 10. Testing Strategy

### 10.1 Test Pyramid

```
         ┌─────────────┐
         │     E2E     │  ← Full pipeline test (1 adapter)
         │   Tests     │
         ├─────────────┤
         │ Integration │  ← Adapter + DB integration
         │   Tests     │
         ├─────────────┤
         │   Unit      │  ← Individual components
         │   Tests     │
         └─────────────┘
```

### 10.2 Test Coverage Target

| Component | Target |
|-----------|--------|
| Adapters | 80% |
| Transformer | 90% |
| Loader | 85% |
| Utils | 90% |

---

## 11. Security Considerations

1. **Rate Limiting**: Respect target servers, prevent IP ban
2. **User-Agent Rotation**: Mimic real browsers
3. **Proxy Support**: (Future) Rotate IPs for anti-bot sites
4. **Credential Storage**: Environment variables, never hardcode
5. **Data Privacy**: No PII storage beyond job URLs
6. **Request Validation**: Validate all external responses

---

## 12. Deployment Options

### 12.1 Local Development
```bash
# Single machine, cron job
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

### 12.3 Cloud Options
- **AWS Lambda**: Serverless, per-adapter deployment
- **Google Cloud Run**: Containerized, auto-scaling
- **Railway/Render**: Simple deployment

---

## 13. Summary

| Category | Decision |
|----------|----------|
| **Language** | Python 3.11+ |
| **Architecture** | ETL + Plugin/Adapter Pattern |
| **Database** | SQLite (dev) → PostgreSQL (prod) |
| **Async** | asyncio + aiohttp |
| **Browser Automation** | Playwright |
| **Scheduling** | APScheduler |
| **Testing** | pytest + pytest-asyncio |
| **Pattern Focus** | Adapter Pattern, Strategy Pattern, Observer Pattern |

---

> **Next Steps:**
> 1. Initialize project structure
> 2. Set up Poetry + dependencies
> 3. Implement database schema
> 4. Build base adapter classes
> 5. Implement first adapter (OPSWAT - easiest)
> 6. Build ETL pipeline
> 7. Add monitoring & alerting
> 8. Add scheduler
> 9. Write tests
> 10. Deploy
