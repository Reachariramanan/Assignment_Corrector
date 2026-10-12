import json
import logging
import traceback
import contextlib
from typing import Any
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from openinference.semconv.trace import OpenInferenceSpanKindValues

logger = logging.getLogger(__name__)

class YuktaJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to safely serialize yukta objects."""
    def default(self, obj: Any) -> Any:
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

def safe_json_dumps(obj: Any) -> str:
    """Safely converts any object to a JSON string for trace attributes."""
    if isinstance(obj, str):
        return obj  
    try:
        return json.dumps(obj, cls=YuktaJSONEncoder, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"JSON serialization failed: {e}")
        return str(obj)

class YuktaTracer:
    """Centralized OpenInference Tracer for the Yukta Framework."""
    def __init__(self, tracer_name: str = "yukta-framework"):
        self.tracer = trace.get_tracer(tracer_name)

    @contextlib.contextmanager
    def start_span(self, name: str, kind: OpenInferenceSpanKindValues):
        # FIX: start_as_current_span creates the proper parent-child nesting
        with self.tracer.start_as_current_span(name) as span:
            # FIX: Hardcode string attribute to guarantee Phoenix recognizes it
            kind_str = kind.value if hasattr(kind, 'value') else str(kind)
            span.set_attribute("openinference.span.kind", kind_str)
            yield span

    def record_exception(self, span: trace.Span, error: Exception):
        span.record_exception(error)
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.set_attribute("exception.type", error.__class__.__name__)
        span.set_attribute("exception.message", str(error))
        span.set_attribute("exception.stacktrace", traceback.format_exc())

# Instantiate the global tracer here
yukta_tracer = YuktaTracer()