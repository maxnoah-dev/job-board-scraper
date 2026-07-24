"""ETL package for job extraction, transformation, and loading."""

from job_board_scraper.etl.multi_adapter import (
    AdapterMetrics,
    AdapterRunStatus,
    AdapterSelector,
    AggregatedMetrics,
    MultiAdapterOrchestrator,
    MultiAdapterResult,
)
from job_board_scraper.etl.pipeline import (
    PipelineExitCode,
    PipelineResult,
    ScrapeResult,
    ScrapingPipeline,
    create_pipeline,
)
from job_board_scraper.etl.transformer import Transformer, create_transformer

__all__ = [
    "PipelineExitCode",
    "PipelineResult",
    "ScrapingPipeline",
    "ScrapeResult",
    "create_pipeline",
    "AdapterMetrics",
    "AdapterRunStatus",
    "AdapterSelector",
    "AggregatedMetrics",
    "MultiAdapterOrchestrator",
    "MultiAdapterResult",
    "Transformer",
    "create_transformer",
]
