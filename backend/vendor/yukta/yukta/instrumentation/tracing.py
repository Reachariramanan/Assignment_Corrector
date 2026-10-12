import functools
from opentelemetry import trace
from openinference.semconv.trace import SpanAttributes, OpenInferenceSpanKindValues

tracer = trace.get_tracer("yukta-framework")

def traced_span(kind: OpenInferenceSpanKindValues, name: str = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Dynamic name if none provided
            span_name = name or f"{args[0].__class__.__name__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, kind)
                
                # Capture metadata from the class instance (e.g., model_name)
                if hasattr(args[0], 'model_name'):
                    span.set_attribute(SpanAttributes.LLM_MODEL_NAME, args[0].model_name)

                # Capture Input
                input_val = kwargs.get('messages') or (args[1] if len(args) > 1 else str(kwargs))
                span.set_attribute(SpanAttributes.INPUT_VALUE, str(input_val))
                
                try:
                    result = func(*args, **kwargs)
                    
                    # --- LLM SPECIFIC CAPTURE ---
                    if kind == OpenInferenceSpanKindValues.LLM and hasattr(result, 'usage'):
                        usage = result.usage
                        # Use these specific keys which Arize Phoenix looks for
                        span.set_attribute("llm.usage.prompt_tokens", usage.get("prompt_tokens", 0))
                        span.set_attribute("llm.usage.completion_tokens", usage.get("completion_tokens", 0))
                        span.set_attribute("llm.usage.total_tokens", usage.get("total_tokens", 0))
                        
                        # For the model name
                        if hasattr(args[0], 'model_name'):
                            span.set_attribute("llm.model_name", args[0].model_name)
                        
                        span.set_attribute(SpanAttributes.OUTPUT_VALUE, result.content)
                    else:
                        span.set_attribute(SpanAttributes.OUTPUT_VALUE, str(result))
                        
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise e
        return wrapper
    return decorator