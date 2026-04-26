# src/services/tracing.py
# 全链路追踪系统

import os
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
import contextvars

from src.config import config

current_span = contextvars.ContextVar('current_span', default=None)

class Tracing:
    def __init__(self, service_name: str = "aagent"):
        self.service_name = service_name
        self.tracer = None
        self._setup()

    def _setup(self):
        try:
            resource = Resource(attributes={
                SERVICE_NAME: self.service_name
            })

            tracer_provider = TracerProvider(resource=resource)

            # 优先尝试 Jaeger 导出
            try:
                jaeger_exporter = JaegerExporter(
                    agent_host_name=config.JAEGER_HOST,
                    agent_port=config.JAEGER_PORT,
                )
                span_processor = BatchSpanProcessor(jaeger_exporter)
                tracer_provider.add_span_processor(span_processor)
                print(f"[Tracing] Jaeger 导出器已配置: {config.JAEGER_HOST}:{config.JAEGER_PORT}")
            except Exception as e:
                print(f"[Tracing] Jaeger 导出器配置失败: {e}")
                console_exporter = ConsoleSpanExporter()
                span_processor = BatchSpanProcessor(console_exporter)
                tracer_provider.add_span_processor(span_processor)
                print("[Tracing] 回退到控制台导出器")

            trace.set_tracer_provider(tracer_provider)
            self.tracer = trace.get_tracer(__name__)
            print(f"[Tracing] 初始化成功: {self.service_name}")
        except Exception as e:
            print(f"[Tracing] 初始化失败: {e}")
            print("[Tracing] 将使用模拟追踪")
            self.tracer = None

    def start_span(self, name: str, attributes: dict = None):
        if not self.tracer:
            class MockSpan:
                def __init__(self, name):
                    self.name = name
                def set_attribute(self, key, value):
                    pass
                def end(self):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    self.end()
            return MockSpan(name)

        class SpanContextManager:
            def __init__(self, tracer, name, attributes):
                self.tracer = tracer
                self.name = name
                self.attributes = attributes
                self.span = None

            def __enter__(self):
                parent_span = current_span.get()
                if parent_span:
                    self.span = self.tracer.start_span(self.name)
                else:
                    self.span = self.tracer.start_span(self.name)

                if self.attributes:
                    for key, value in self.attributes.items():
                        self.span.set_attribute(key, value)

                current_span.set(self.span)
                return self.span

            def __exit__(self, *args):
                if self.span:
                    self.span.end()

        return SpanContextManager(self.tracer, name, attributes)

    def end_span(self, span):
        if span:
            try:
                span.end()
            except Exception:
                pass

    def get_current_span(self):
        return current_span.get()

tracing = Tracing()