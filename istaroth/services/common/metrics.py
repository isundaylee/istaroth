"""Shared Prometheus metric definitions for Istaroth services."""

import prometheus_client

http_requests_total = prometheus_client.Counter(
    "istaroth_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)

http_request_duration_seconds = prometheus_client.Histogram(
    "istaroth_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path", "status"],
)

rag_pipeline_duration_seconds = prometheus_client.Histogram(
    "istaroth_rag_pipeline_duration_seconds",
    "RAG pipeline end-to-end duration in seconds",
    ["model", "language"],
)

rag_pipeline_stage_preprocessing_duration_seconds = prometheus_client.Histogram(
    "istaroth_rag_pipeline_stage_preprocessing_duration_seconds",
    "RAG preprocessing step duration in seconds",
)

rag_pipeline_stage_generation_duration_seconds = prometheus_client.Histogram(
    "istaroth_rag_pipeline_stage_generation_duration_seconds",
    "RAG generation step duration in seconds",
    ["model", "language"],
)

rag_pipeline_stage_retrieval_duration_seconds = prometheus_client.Histogram(
    "istaroth_rag_pipeline_stage_retrieval_duration_seconds",
    "RAG retrieval phase duration in seconds",
    ["model", "language"],
)

retrieval_duration_seconds = prometheus_client.Histogram(
    "istaroth_retrieval_duration_seconds",
    "Retrieval operation duration in seconds",
    ["operation", "language"],
)
