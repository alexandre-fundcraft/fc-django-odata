# API Contracts: Filter Error Handling

## Error Response Contracts

### Invalid Filter Expression (400 Bad Request)

**Request:**
```
GET /api/blogposts?$filter=invalid_field eq 'value'
```

**Response:**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

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

### Malformed Filter Syntax (400 Bad Request)

**Request:**
```
GET /api/blogposts?$filter=status eq
```

**Response:**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "BadRequest",
    "message": "Invalid filter expression: $filter=status eq",
    "details": [
      {
        "code": "InvalidFilterSyntax",
        "message": "Incomplete filter expression near 'eq'",
        "target": "$filter"
      }
    ]
  }
}
```

### Invalid Operator (400 Bad Request)

**Request:**
```
GET /api/blogposts?$filter=status invalid 'value'
```

**Response:**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "BadRequest",
    "message": "Invalid filter expression: $filter=status invalid 'value'",
    "details": [
      {
        "code": "InvalidOperator",
        "message": "Unknown operator 'invalid'. Valid operators: eq, ne, gt, ge, lt, le, and, or, not",
        "target": "$filter"
      }
    ]
  }
}
```

## Contract Specifications

### Error Response Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "error": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "enum": ["BadRequest"]
        },
        "message": {
          "type": "string",
          "description": "Human-readable error message including the problematic filter expression"
        },
        "details": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "code": {
                "type": "string",
                "enum": ["FieldNotFound", "InvalidFilterSyntax", "InvalidOperator", "InvalidValue"]
              },
              "message": {
                "type": "string",
                "description": "Detailed error description"
              },
              "target": {
                "type": "string",
                "enum": ["$filter"],
                "description": "The OData query parameter that caused the error"
              }
            },
            "required": ["code", "message", "target"]
          }
        }
      },
      "required": ["code", "message", "details"]
    }
  },
  "required": ["error"]
}
```

### Error Code Definitions

| Error Code | Description | Example |
|------------|-------------|---------|
| `FieldNotFound` | Referenced field does not exist on the entity | `invalid_field` |
| `InvalidFilterSyntax` | Malformed OData filter syntax | `status eq` (missing value) |
| `InvalidOperator` | Unknown or unsupported operator | `status invalid 'value'` |
| `InvalidValue` | Invalid value format for the field type | `status eq 123` (string expected) |

### HTTP Status Codes

- **400 Bad Request**: All filter validation and parsing errors
- **Content-Type**: `application/json`
- **No Data Returned**: Error responses never include partial or unfiltered data

## Backward Compatibility

### Breaking Changes
- **Before**: Invalid filters returned unfiltered data with 200 OK
- **After**: Invalid filters return 400 Bad Request with error details

### Migration Guide
Clients must update error handling to:
1. Check for 400 status codes on filter requests
2. Parse error response structure according to OData v4.0 specification
3. Display meaningful error messages to users
4. Log errors for debugging purposes

## Testing Contracts

### Contract Tests Required
- All error response formats match the JSON schema
- All error codes are properly mapped from odata-query exceptions
- HTTP status codes are correct (400 for all filter errors)
- Error messages include the original filter expression
- No sensitive information is exposed in error responses