"""
Django OData package for creating OData-compliant REST API endpoints.

This package provides native OData v4 implementation with:
- Native field selection and expansion (no external dependencies)
- Full OData query parameter support ($filter, $orderby, $top, $skip, $select, $expand, $count)
- Automatic Django ORM query translation and optimization
- Field-level query optimization with .only() and Prefetch
- Standards-compliant OData response format
- Extensible architecture for custom OData features
"""

__version__ = "2.0.0"
__author__ = "Alexandre Busquets"

from .mixins import ODataMixin, ODataSerializerMixin
from .serializers import ODataModelSerializer, ODataSerializer
from .utils import apply_odata_query_params, parse_odata_query
from .viewsets import ODataModelViewSet, ODataViewSet

__all__ = [
    "ODataModelSerializer",
    "ODataSerializer",
    "ODataModelViewSet",
    "ODataViewSet",
    "ODataMixin",
    "ODataSerializerMixin",
    "apply_odata_query_params",
    "parse_odata_query",
]
