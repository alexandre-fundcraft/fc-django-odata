# Quickstart: Filter Error Handling with 4xx Responses

## Overview

This feature modifies django-odata to return proper HTTP 4xx error responses when OData filter errors occur, instead of silently returning unfiltered data. This ensures clients can properly handle and display meaningful error messages.

## What Changed

### Before (Old Behavior)
```python
# Invalid filter: returns all data with 200 OK
GET /api/blogposts?$filter=invalid_field eq 'value'
# Response: 200 OK with all blog posts
```

### After (New Behavior)
```python
# Invalid filter: returns error with 400 Bad Request
GET /api/blogposts?$filter=invalid_field eq 'value'
# Response: 400 Bad Request with OData error format
```

## Migration Guide

### For API Clients

Update your client error handling code:

```javascript
// Before
fetch('/api/blogposts?$filter=invalid_field eq "value"')
  .then(response => response.json())
  .then(data => {
    // Always got data, even with invalid filters
    displayPosts(data.value);
  });

// After
fetch('/api/blogposts?$filter=invalid_field eq "value"')
  .then(response => {
    if (!response.ok) {
      return response.json().then(error => {
        throw new Error(error.error.message);
      });
    }
    return response.json();
  })
  .then(data => {
    displayPosts(data.value);
  })
  .catch(error => {
    displayError(error.message); // Now shows meaningful error
  });
```

### For Django Developers

No code changes required! The error handling is automatic. However, you may want to customize error responses:

```python
# In your viewset (optional customization)
class BlogPostViewSet(ODataModelViewSet):
    def handle_exception(self, exc):
        if isinstance(exc, ODataFilterError):
            # Custom error handling if needed
            return Response(
                {"error": {"message": "Custom filter error message"}},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().handle_exception(exc)
```

## Error Response Format

All filter errors now return OData v4.0 compliant error responses:

```json
{
  "error": {
    "code": "BadRequest",
    "message": "Invalid filter expression: $filter=invalid_field eq 'value'",
    "details": [
      {
        "code": "FieldNotFound",
        "message": "Field 'invalid_field' does not exist on entity 'BlogPost'",
        "target": "$filter"
      }
    ]
  }
}
```

## Common Error Scenarios

### 1. Field Not Found
```
GET /api/blogposts?$filter=invalid_field eq 'value'
```
Response: `Field 'invalid_field' does not exist on entity 'BlogPost'`

### 2. Invalid Syntax
```
GET /api/blogposts?$filter=status eq
```
Response: `Incomplete filter expression near 'eq'`

### 3. Invalid Operator
```
GET /api/blogposts?$filter=status invalid 'value'
```
Response: `Unknown operator 'invalid'. Valid operators: eq, ne, gt, ge, lt, le, and, or, not`

## Testing Your Migration

### 1. Test Valid Filters Still Work
```bash
curl "http://localhost:8000/api/blogposts?$filter=status eq 'published'"
# Should return 200 OK with filtered data
```

### 2. Test Invalid Filters Return Errors
```bash
curl "http://localhost:8000/api/blogposts?$filter=invalid_field eq 'value'"
# Should return 400 Bad Request with error details
```

### 3. Verify Error Format
```bash
curl -s "http://localhost:8000/api/blogposts?$filter=invalid_field eq 'value'" | jq .error
# Should show properly formatted OData error
```

## Breaking Changes

- **Filter errors now return 400 instead of 200**: Clients must handle 4xx responses
- **No unfiltered data on errors**: Empty responses instead of fallback data
- **OData error format**: Error structure follows OData v4.0 specification

## Rollback (If Needed)

To temporarily revert to old behavior (not recommended):

```python
# In your viewset
class BlogPostViewSet(ODataModelViewSet):
    def apply_odata_query(self, queryset):
        try:
            return super().apply_odata_query(queryset)
        except Exception as e:
            # Log error but return unfiltered data
            logger.warning(f"Filter error (returning unfiltered): {e}")
            return queryset
```

## Next Steps

1. Update client applications to handle 4xx responses
2. Test all existing OData filter usage
3. Monitor error logs for any unexpected filter issues
4. Consider adding client-side filter validation to prevent errors

## Support

If you encounter issues:
1. Check the error response format matches the OData specification
2. Verify your client handles HTTP 4xx status codes
3. Review server logs for additional error details
4. Ensure you're using the latest django-odata version