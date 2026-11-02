import pytest
from fulfillment.resilience import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_breaker_awaits_a_synchronous_sdk_wrapper():
    completed = []
    async def operation():
        completed.append(True)
        return "real result"
    def decorated_sdk_method():
        return operation()
    breaker = CircuitBreaker("decorated-success")
    assert await breaker.call(decorated_sdk_method) == "real result"
    assert completed == [True]
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_breaker_counts_failure_from_wrapped_coroutine():
    async def operation():
        raise RuntimeError("fixture failure")
    def decorated_sdk_method():
        return operation()
    breaker = CircuitBreaker("decorated-failure", failure_threshold=1)
    with pytest.raises(RuntimeError):
        await breaker.call(decorated_sdk_method)
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_breaker_preserves_synchronous_callables():
    breaker = CircuitBreaker("synchronous-success")
    assert await breaker.call(lambda: 7) == 7
