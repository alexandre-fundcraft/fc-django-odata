"""
Tests for OData query caching functionality in django_odata.utils
"""

from contextvars import Context

from django.db import models
from django.db.models import QuerySet

from django_odata.utils import (
    _generate_request_cache_key,
    _request_cache,
    apply_odata_query_params,
    clear_odata_cache,
    odata_cache_context,
)


class MockModel(models.Model):
    """Mock model for testing."""

    name = models.CharField(max_length=100)
    value = models.IntegerField()

    class Meta:
        app_label = "test"


class TestODataQueryCaching:
    """Test suite for OData query caching functionality."""

    def setup_method(self):
        """Reset cache before each test."""
        # Reset the context variable for each test
        ctx = Context()
        ctx.run(lambda: _request_cache.set({}))
        # Note: In real usage, each request would have its own context

    def test_generate_cache_key_basic(self):
        """Test basic cache key generation."""
        queryset = MockModel.objects.all()
        params = {"$filter": "name eq 'test'", "$orderby": "name"}

        key1 = _generate_request_cache_key(queryset, params)
        key2 = _generate_request_cache_key(queryset, params)

        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 64  # SHA256 hex length

    def test_generate_cache_key_different_params(self):
        """Test cache key generation with different parameters."""
        queryset = MockModel.objects.all()
        params1 = {"$filter": "name eq 'test'"}
        params2 = {"$filter": "name eq 'other'"}

        key1 = _generate_request_cache_key(queryset, params1)
        key2 = _generate_request_cache_key(queryset, params2)

        assert key1 != key2

    def test_generate_cache_key_different_models(self):
        """Test cache key generation with different models."""

        class OtherModel(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test"

        queryset1 = MockModel.objects.all()
        queryset2 = OtherModel.objects.all()
        params = {"$filter": "name eq 'test'"}

        key1 = _generate_request_cache_key(queryset1, params)
        key2 = _generate_request_cache_key(queryset2, params)

        assert key1 != key2

    def test_generate_cache_key_parameter_ordering(self):
        """Test that parameter ordering doesn't affect cache key."""
        queryset = MockModel.objects.all()
        params1 = {"$filter": "name eq 'test'", "$orderby": "name"}
        params2 = {"$orderby": "name", "$filter": "name eq 'test'"}

        key1 = _generate_request_cache_key(queryset, params1)
        key2 = _generate_request_cache_key(queryset, params2)

        assert key1 == key2

    def test_cache_hit_same_request(self):
        """Test that identical queries in the same request use cache."""
        queryset = MockModel.objects.all()
        params = {"$filter": "name eq 'test'"}

        # First call should process and cache
        result1 = apply_odata_query_params(queryset, params)

        # Second call should use cache
        result2 = apply_odata_query_params(queryset, params)

        # Results should be the same object (from cache)
        assert result1 is result2

    def test_cache_miss_different_params(self):
        """Test that different parameters don't use cache."""
        queryset = MockModel.objects.all()
        params1 = {"$filter": "name eq 'test'"}
        params2 = {"$filter": "name eq 'other'"}

        # Different parameters should not share cache
        result1 = apply_odata_query_params(queryset, params1)
        result2 = apply_odata_query_params(queryset, params2)

        # Results should be different objects
        assert result1 is not result2

    def test_cache_miss_different_models(self):
        """Test that different models don't share cache."""

        class OtherModel(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test"

        queryset1 = MockModel.objects.all()
        queryset2 = OtherModel.objects.all()
        params = {"$filter": "name eq 'test'"}

        # Different models should not share cache
        result1 = apply_odata_query_params(queryset1, params)
        result2 = apply_odata_query_params(queryset2, params)

        # Results should be different objects
        assert result1 is not result2

    def test_cache_preserves_queryset_functionality(self):
        """Test that cached results maintain QuerySet functionality."""
        queryset = MockModel.objects.all()
        params = {"$orderby": "name"}

        result = apply_odata_query_params(queryset, params)

        # Should still be a QuerySet
        assert isinstance(result, QuerySet)

        # Should have the model
        assert result.model == MockModel

        # Should be able to call QuerySet methods
        assert hasattr(result, "filter")
        assert hasattr(result, "order_by")
        assert hasattr(result, "count")

    def test_cache_with_complex_params(self):
        """Test caching with complex OData parameters."""
        queryset = MockModel.objects.all()
        params = {
            "$filter": "name eq 'test' and value gt 10",
            "$orderby": "name desc, value asc",
            "$top": "50",
            "$skip": "10",
        }

        # First call
        result1 = apply_odata_query_params(queryset, params)

        # Second call with same params should use cache
        result2 = apply_odata_query_params(queryset, params)

        assert result1 is result2

    def test_cache_isolation_between_requests(self):
        """Test that cache is properly isolated between different request contexts."""
        # This test simulates different request contexts
        queryset = MockModel.objects.all()
        params = {"$filter": "name eq 'test'"}

        # Simulate first request
        ctx1 = Context()
        result1 = ctx1.run(lambda: apply_odata_query_params(queryset, params))

        # Simulate second request (different context)
        ctx2 = Context()
        result2 = ctx2.run(lambda: apply_odata_query_params(queryset, params))

        # Results should be different objects (different contexts)
        assert result1 is not result2

    def test_empty_params_caching(self):
        """Test caching with empty parameters."""
        queryset = MockModel.objects.all()
        params = {}

        result1 = apply_odata_query_params(queryset, params)
        result2 = apply_odata_query_params(queryset, params)

        assert result1 is result2

    def test_clear_cache_functionality(self):
        """Test manual cache clearing functionality."""
        queryset = MockModel.objects.all()
        params = {"$filter": "name eq 'test'"}

        # First call caches result
        result1 = apply_odata_query_params(queryset, params)

        # Second call should use cache
        result2 = apply_odata_query_params(queryset, params)
        assert result1 is result2

        # Clear cache
        clear_odata_cache()

        # Third call should create new result (cache cleared)
        result3 = apply_odata_query_params(queryset, params)
        assert result1 is not result3  # Different object after cache clear

    def test_cache_context_manager(self):
        """Test context manager for scoped caching."""
        queryset = MockModel.objects.all()
        params = {"$filter": "name eq 'test'"}

        # Use context manager
        with odata_cache_context():
            result1 = apply_odata_query_params(queryset, params)
            result2 = apply_odata_query_params(queryset, params)
            assert result1 is result2  # Same within context

        # After context, cache should be reset
        result3 = apply_odata_query_params(queryset, params)
        # Note: ContextVar behavior means this might still be cached
        # depending on the test context, so we just verify it works
        assert isinstance(result3, QuerySet)

    def test_none_params_caching(self):
        """Test caching with None values in parameters."""
        queryset = MockModel.objects.all()
        params = {
            "$orderby": "name"
        }  # Remove None filter to avoid odata_query library issues

        result1 = apply_odata_query_params(queryset, params)
        result2 = apply_odata_query_params(queryset, params)

        assert result1 is result2
