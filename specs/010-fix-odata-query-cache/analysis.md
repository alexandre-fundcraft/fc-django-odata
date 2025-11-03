# Analysis: Fix Repeated OData Query Processing Without Caching

**Feature**: `010-fix-odata-query-cache`
**Date**: 2025-11-01
**Analyst**: Kilo Code

## Current Implementation Analysis

### Function Structure

The `apply_odata_query_params` function in `django_odata/utils.py` (lines 286-314) currently:

1. **Takes inputs**: `queryset: QuerySet` and `query_params: Dict[str, Any]`
2. **Applies operations sequentially**:
   - `_apply_filter()` - Uses external `odata_query.django.apply_odata_query()`
   - `_apply_orderby()` - Parses and applies ordering
   - `_apply_skip()` - Applies offset/pagination
   - `_apply_top()` - Applies limit/pagination
3. **Returns**: Modified QuerySet

### Performance Bottlenecks Identified

1. **No Caching**: Every call re-processes the same query parameters
2. **Expensive Operations**:
   - OData filter parsing and application (external library)
   - String parsing for `$orderby` expressions
   - Repeated QuerySet modifications
3. **Repeated Work**: Identical queries get processed multiple times

### Caching Opportunities

#### 1. Query Parameter Parsing Cache
- **Target**: Parse OData query strings once and cache results
- **Scope**: `$filter`, `$orderby`, `$select`, `$expand` parsing
- **Cache Key**: Hash of raw query parameter strings
- **Cache Value**: Parsed parameter dictionaries

#### 2. QuerySet Transformation Cache
- **Target**: Cache the result of applying query parameters to a base QuerySet
- **Scope**: Complete QuerySet after all transformations
- **Cache Key**: Combination of base QuerySet identifier + query parameters hash
- **Cache Value**: Final QuerySet object

#### 3. Intermediate Result Cache
- **Target**: Cache results after each transformation step
- **Scope**: QuerySet state after filter, orderby, skip, top operations
- **Cache Key**: Step-specific + parameters hash

### Recommended Caching Strategy

#### Primary Strategy: Request-Scoped QuerySet Cache

**Why this approach (addressing user feedback):**
- **Request lifecycle alignment**: Cache lifetime matches the HTTP request, ensuring data consistency
- **Use-case scoped**: Each logical operation (API call) gets fresh data while benefiting from repeated query processing within that operation
- **Eliminates stale data risks**: No cross-request data contamination
- **Preserves performance benefits**: Still caches repeated identical queries within the same request
- **Thread-safe**: Request-local storage avoids concurrency issues

**Implementation:**
```python
from contextvars import ContextVar

# ContextVar for request-scoped cache
_request_cache: ContextVar[Dict[str, QuerySet]] = ContextVar('odata_cache', default={})

def apply_odata_query_params(
    queryset: QuerySet, query_params: Dict[str, Any]
) -> QuerySet:
    # Get current request cache (creates new dict if not set)
    cache = _request_cache.get()

    # Generate request-scoped cache key
    cache_key = _generate_request_cache_key(queryset, query_params)

    # Check request-local cache first
    if cache_key in cache:
        return cache[cache_key]

    # Apply transformations
    result = _apply_all_transformations(queryset, query_params)

    # Update cache with new result
    new_cache = cache.copy()
    new_cache[cache_key] = result
    _request_cache.set(new_cache)

    return result
```

#### Cache Key Generation

**Components:**
1. **Model identifier**: `queryset.model._meta.label_lower`
2. **Query parameters hash**: SHA256 of sorted, JSON-serialized `query_params`
3. **Base QuerySet identifier**: Hash of base QuerySet's essential properties

**Format**: `req_odata:{model}:{params_hash}:{queryset_id}`

**Request-scoped benefits:**
- Keys are unique per request automatically
- No need for complex invalidation logic
- Memory automatically freed when request ends

#### Cache Storage Strategy

**Options:**
1. **ContextVar (asyncio context)** (proper async support, request-scoped)
2. **Thread-local storage** (simple, automatic cleanup)
3. **Django request context** (middleware-based, request-scoped)
4. **Context manager** (explicit scope control)

**Recommended**: ContextVar for modern Python async/await support and proper request scoping.

#### Cache Lifecycle Management

**Automatic Lifecycle:**
- **Request start**: Initialize empty cache
- **Request end**: Automatically garbage collected (in Django/sync contexts)
- **ContextVar scope**: Cache lives as long as the async context/task

**Important Considerations for Different Frameworks:**

**Django (Sync Views):**
- Cache automatically cleared at request end ✅
- No memory leaks in typical usage ✅

**Django (Async Views):**
- Cache lives for the duration of the async task ✅
- Automatic cleanup when task completes ✅

**FastAPI/Other Async Frameworks:**
- ⚠️ **Potential Issue**: Long-running async tasks may retain cache indefinitely
- **Solution Needed**: Manual cache clearing or task-scoped cleanup

**Solutions for Long-Running Contexts:**

1. **Manual Cache Clearing:**
```python
from django_odata.utils import clear_odata_cache

# Clear cache manually when needed
clear_odata_cache()
```

2. **Context Manager for Task Scoping:**
```python
from django_odata.utils import odata_cache_context

async def my_endpoint():
    with odata_cache_context():
        # Cache only lives within this context
        result1 = apply_odata_query_params(queryset, params)
        result2 = apply_odata_query_params(queryset, params)  # Uses cache
    # Cache automatically cleared here
```

3. **Middleware-Based Clearing:**
```python
# In FastAPI middleware
@app.middleware("http")
async def clear_cache_after_request(request, call_next):
    response = await call_next(request)
    clear_odata_cache()  # Clear after each request
    return response
```

**Benefits:**
- **Data consistency**: Each request sees current data
- **Memory efficiency**: Cache only lives for request duration (with proper cleanup)
- **Thread safety**: Isolated per thread/request
- **Performance**: Still benefits from repeated queries in same request

### Implementation Considerations

#### Thread Safety
- ContextVar provides proper async context isolation
- Each async context/task gets its own cache automatically
- Django QuerySets are generally thread-safe
- No cross-context contamination

#### Memory Management
- **Automatic cleanup**: Cache freed at request end
- **Per-request limits**: Monitor memory usage per request
- **No persistent storage**: Memory only lives for request duration

#### Cache Hit Scenarios
- **High hit rate expected** in complex API calls with multiple similar queries
- **Low hit rate** in simple requests with unique queries
- **Perfect for**: Expand operations, complex filtering, repeated lookups

#### Performance Trade-offs
- **Cache overhead**: Minimal (hash computation + dict lookup)
- **Memory usage**: Temporary per-request storage
- **Cache misses**: Full processing still required but only once per request
- **Benefits**: Significant speedup for repeated queries within same request

### Alternative Approaches Considered

#### 1. Query String Caching Only
- Cache parsed parameters, not QuerySets
- Lower memory usage but less performance gain
- Still requires QuerySet transformation on each call

#### 2. SQL Query Caching
- Cache final SQL queries
- Highest performance but complex implementation
- Requires careful handling of parameter binding

#### 3. Global Application Cache (Previous Recommendation)
- Persistent across requests
- Higher performance for cross-request caching
- **Rejected due to user feedback**: Cache lifecycle should match request/use-case
- Risk of stale data and complex invalidation

#### 4. No Caching (Current)
- Zero memory overhead
- Maximum correctness
- Poor performance for repeated queries

### Success Metrics

- **Cache hit rate**: Target >80% for repeated query scenarios
- **Performance improvement**: >50% faster for cached queries
- **Memory usage**: <100MB for 1000 cached QuerySets
- **Correctness**: 100% query result accuracy

### Risks and Mitigations

#### Risk: Memory Leaks (Per Request)
**Mitigation**: Automatic cleanup at request end, monitor per-request memory usage

#### Risk: Cache Key Collisions
**Mitigation**: Include model identifier, use cryptographic hashing, request-scoped keys

#### Risk: Thread Safety Issues
**Mitigation**: Thread-local storage provides natural isolation

#### Risk: Large Request Memory Usage
**Mitigation**: Monitor cache size per request, implement reasonable limits if needed

**Note**: Stale data risk eliminated by request-scoped caching approach

### Next Steps

1. Implement request-scoped QuerySet caching with ContextVar
2. Add ContextVar-based cache storage
3. Implement cache key generation for request scope
4. Add async context support and testing
5. Performance testing with repeated queries in same request
6. Memory usage monitoring per request/context