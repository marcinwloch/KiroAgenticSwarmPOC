# Weather Data Collection — Technical Design

## Overview

The Weather Data Collection feature extends the FastAPI task tracker with comprehensive weather data management capabilities. This design implements a complete REST API for weather data CRUD operations, integrated with the existing application architecture following the Nortal Swarm Constitution.

The feature provides:
- **Weather Data Endpoints**: Full CRUD operations on weather records with location-based filtering
- **Data Models & Validation**: SQLAlchemy ORM models and Pydantic schemas with comprehensive validation
- **Rate Limiting**: Per-IP rate limiting with environment-based configuration
- **Error Handling**: Consistent error envelopes with domain-specific exception mapping
- **Database Integration**: Async SQLAlchemy with automatic timestamp management
- **Structured Logging**: JSON-formatted logs for CloudWatch Logs Insights filtering
- **API Documentation**: Complete OpenAPI documentation with proper response schemas

## Architecture

### Layered Architecture

The weather feature follows the existing FastAPI layered architecture:

```
┌─────────────────────────────────────────────────────────────┐
│ HTTP Layer (FastAPI Routers)                                │
│ - /weather endpoints with rate limiting decorators          │
│ - Request/response validation via Pydantic                  │
│ - Exception handlers for domain errors                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Service Layer (Business Logic)                              │
│ - Weather CRUD operations                                   │
│ - Location-based filtering with tolerance                   │
│ - Domain-specific exceptions (WeatherNotFoundError)         │
│ - Structured logging for observability                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Data Access Layer (SQLAlchemy)                              │
│ - Async session management                                  │
│ - ORM model definitions                                     │
│ - Automatic timestamp management (created_at, updated_at)   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Database Layer (SQLite)                                     │
│ - Weather table with indexed location columns               │
│ - Automatic schema creation on startup                      │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Routers handle HTTP concerns, services handle business logic, models handle data persistence
2. **Dependency Injection**: Database sessions and rate limiter passed via FastAPI dependencies
3. **Configuration as Code**: All tunables via environment variables (12-factor)
4. **Structured Logging**: JSON-formatted logs with consistent field structure for CloudWatch filtering
5. **Error Handling**: Domain exceptions mapped to HTTP status codes in a single exception handler layer

## Components and Interfaces

### 1. Data Models (SQLAlchemy ORM)

**File**: `app/models/weather.py`

```python
class Weather(Base):
    __tablename__ = "weather"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    temperature: Mapped[float] = mapped_column(nullable=False)
    humidity: Mapped[int] = mapped_column(nullable=False)  # 0-100
    pressure: Mapped[float] = mapped_column(nullable=False)
    wind_speed: Mapped[float] = mapped_column(nullable=False)
    location_latitude: Mapped[float] = mapped_column(nullable=False, index=True)
    location_longitude: Mapped[float] = mapped_column(nullable=False, index=True)
    weather_condition: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
```

**Key Features**:
- Indexed location columns for efficient filtering
- Automatic timestamp management via SQLAlchemy server defaults
- Humidity constrained to 0-100 range
- Weather condition as string (validated in Pydantic layer)

### 2. Pydantic Schemas

**File**: `app/schemas/weather.py`

Three schemas for different use cases:

**WeatherCreate** (POST request):
- Validates latitude: -90 to 90
- Validates longitude: -180 to 180
- Validates humidity: 0 to 100
- Validates temperature: float
- Validates weather_condition: enum of ["clear", "cloudy", "rainy", "snowy", "stormy", "foggy"]
- Rejects unknown fields

**WeatherUpdate** (PUT request):
- All fields optional
- Same validation rules as WeatherCreate
- Supports partial updates

**WeatherRead** (GET response):
- Includes all fields plus id, created_at, updated_at
- Uses `ConfigDict(from_attributes=True)` for SQLAlchemy model conversion
- Read-only (no validation needed)

**ErrorResponse**:
- Consistent error envelope with `detail` and `code` fields
- Used for all error responses (400, 404, 429, 500)

### 3. Service Layer

**File**: `app/services/weather.py`

Domain-specific exception:
```python
class WeatherNotFoundError(Exception):
    pass
```

Service functions:
- `list_weather(session, lat=None, lon=None, tolerance=0.01)` → List with optional location filtering
- `get_weather(session, weather_id)` → Get single record or raise WeatherNotFoundError
- `create_weather(session, data: WeatherCreate)` → Create and return new record
- `update_weather(session, weather_id, data: WeatherUpdate)` → Update and return record
- `delete_weather(session, weather_id)` → Delete record or raise WeatherNotFoundError

**Structured Logging**:
- Create: logs event="weather_created" with weather_id, location_latitude, location_longitude, metric, metric_value
- Retrieve: logs event="weather_retrieved" with weather_id, route, metric, metric_value
- Validation errors: logs event="validation_error" with error_code, error_detail, metric, metric_value

### 4. Router/Endpoints

**File**: `app/routers/weather.py`

Endpoints:
- `POST /weather` → Create weather record (rate limited: RATE_LIMIT_WEATHER_WRITE)
- `GET /weather` → List weather records with optional location filtering (rate limited: RATE_LIMIT_WEATHER_READ)
- `GET /weather/{weather_id}` → Get single record (rate limited: RATE_LIMIT_WEATHER_READ)
- `PUT /weather/{weather_id}` → Update record (rate limited: RATE_LIMIT_WEATHER_WRITE)
- `DELETE /weather/{weather_id}` → Delete record (rate limited: RATE_LIMIT_WEATHER_WRITE)

**Rate Limiting**:
- All endpoints require API key authentication via `require_api_key` dependency
- All endpoints subject to rate limiting except `/health`
- Rate limits configured via environment variables

**Response Codes**:
- 201: Created (POST)
- 200: Success (GET, PUT)
- 204: No Content (DELETE)
- 400: Validation error (invalid coordinates, weather_condition, unknown fields)
- 404: Not found (GET/PUT/DELETE non-existent record)
- 429: Rate limit exceeded (with Retry-After header)
- 500: Internal server error

### 5. Configuration

**File**: `app/config.py` (extended)

New settings:
```python
rate_limit_weather_read: str = "30/minute"
rate_limit_weather_write: str = "10/minute"
weather_collection_enabled: bool = True
```

All settings read from environment variables with sensible defaults.

### 6. Exception Handlers

**File**: `app/main.py` (extended)

New exception handler:
```python
@app.exception_handler(WeatherNotFoundError)
async def weather_not_found_handler(request: Request, exc: WeatherNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"Weather record {exc.args[0]} not found", "code": "WEATHER_NOT_FOUND"},
    )
```

Existing rate limit handler already handles 429 responses with Retry-After header.

## Data Models

### Weather Record Structure

```
Weather {
  id: integer (primary key)
  temperature: float (°C or °F, unit not enforced)
  humidity: integer (0-100, percentage)
  pressure: float (hPa or similar)
  wind_speed: float (m/s or similar)
  location_latitude: float (-90 to 90)
  location_longitude: float (-180 to 180)
  weather_condition: string (enum: clear, cloudy, rainy, snowy, stormy, foggy)
  created_at: datetime (UTC, auto-set)
  updated_at: datetime (UTC, auto-updated)
}
```

### Location Filtering

Filtering supports tolerance-based range queries:
- Query: `GET /weather?lat=52.5&lon=13.4&tolerance=0.01`
- Returns all records where:
  - `abs(latitude - 52.5) <= 0.01` AND
  - `abs(longitude - 13.4) <= 0.01`
- Default tolerance: 0.01 degrees (~1.1 km at equator)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Weather Record Creation

*For any* valid weather data (coordinates within valid ranges, humidity 0-100, valid weather condition), creating a weather record SHALL result in HTTP 201 response with the created record containing all provided fields plus auto-generated id, created_at, and updated_at.

**Validates: Requirements 1.1, 2.1, 2.3, 2.4**

### Property 2: Weather Record Retrieval

*For any* created weather record, retrieving it by ID SHALL return HTTP 200 with the complete record. Retrieving a non-existent ID SHALL return HTTP 404 with error code "WEATHER_NOT_FOUND".

**Validates: Requirements 1.2, 4.3**

### Property 3: Weather Record Listing with Filtering

*For any* set of weather records with different locations, filtering by location coordinates with tolerance SHALL return only records within the tolerance range, and all returned records SHALL match the filter criteria.

**Validates: Requirements 1.3, 5.6**

### Property 4: Weather Record Update

*For any* created weather record, updating it with new valid data SHALL return HTTP 200 with the updated record. The updated_at timestamp SHALL be newer than the original. Updating a non-existent record SHALL return HTTP 404.

**Validates: Requirements 1.4, 5.4**

### Property 5: Weather Record Deletion

*For any* created weather record, deleting it SHALL return HTTP 204 and subsequent retrieval SHALL return HTTP 404. Deleting a non-existent record SHALL return HTTP 404.

**Validates: Requirements 1.5**

### Property 6: Location Coordinate Validation

*For any* request with invalid coordinates (latitude outside -90 to 90 or longitude outside -180 to 180), the system SHALL return HTTP 400 with a descriptive error message indicating the valid range.

**Validates: Requirements 2.3, 4.1**

### Property 7: Weather Condition Validation

*For any* request with an invalid weather_condition value (not in ["clear", "cloudy", "rainy", "snowy", "stormy", "foggy"]), the system SHALL return HTTP 400 with a list of valid condition values.

**Validates: Requirements 2.4, 4.2**

### Property 8: Humidity Validation

*For any* request with humidity outside 0-100 range, the system SHALL return HTTP 400 with a descriptive error message.

**Validates: Requirements 2.3**

### Property 9: Rate Limiting Enforcement

*For any* client IP address, after exceeding the configured rate limit for an endpoint, subsequent requests SHALL return HTTP 429 with a Retry-After header. Requests within the limit SHALL succeed.

**Validates: Requirements 3.1, 3.2**

### Property 10: Rate Limit Error Response Format

*For any* rate limit exceeded response, the response SHALL include HTTP 429 status, Retry-After header, and error envelope with detail and code fields.

**Validates: Requirements 3.2, 3.6**

### Property 11: Unknown Field Rejection

*For any* request body containing unknown fields, the system SHALL return HTTP 422 with a validation error message.

**Validates: Requirements 4.5**

### Property 12: Timestamp Automation

*For any* created weather record, created_at SHALL be set to the current timestamp. *For any* updated weather record, updated_at SHALL be newer than the previous value.

**Validates: Requirements 5.3, 5.4**

### Property 13: API Key Authentication

*For any* weather endpoint request without a valid API key, the system SHALL return HTTP 403. Requests with valid API key SHALL proceed to rate limiting and business logic.

**Validates: Requirements 6.3**

### Property 14: Configuration Defaults

*When* environment variables for rate limits are not set, the system SHALL use default values: RATE_LIMIT_WEATHER_READ="30/minute", RATE_LIMIT_WEATHER_WRITE="10/minute".

**Validates: Requirements 7.2**

## Error Handling

### Error Response Format

All errors return a consistent envelope:
```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE"
}
```

### Error Codes and HTTP Status

| HTTP Status | Error Code | Scenario |
|-------------|-----------|----------|
| 400 | VALIDATION_ERROR | Invalid coordinates, humidity, weather_condition, or unknown fields |
| 403 | UNAUTHORIZED | Missing or invalid API key |
| 404 | WEATHER_NOT_FOUND | Weather record does not exist |
| 429 | RATE_LIMIT_EXCEEDED | Rate limit exceeded (includes Retry-After header) |
| 500 | INTERNAL_SERVER_ERROR | Database or unexpected error |

### Exception Mapping

Domain exceptions are mapped to HTTP responses in the exception handler layer:
- `WeatherNotFoundError` → 404 with code "WEATHER_NOT_FOUND"
- `RateLimitExceeded` → 429 with code "RATE_LIMIT_EXCEEDED" (existing handler)
- Pydantic `ValidationError` → 400 with code "VALIDATION_ERROR" (FastAPI default)
- Unexpected exceptions → 500 with code "INTERNAL_SERVER_ERROR"

## Testing Strategy

### Test Pyramid

| Layer | Target | Tools | Count |
|-------|--------|-------|-------|
| Unit | Service functions, validation logic | pytest, mocks | ~15 |
| Integration | API endpoints + database | pytest, httpx.AsyncClient, in-memory SQLite | ~20 |
| E2E | Full workflow (create → list → update → delete) | pytest, httpx.AsyncClient | ~3 |

### Acceptance Criteria Coverage

Every acceptance criterion from the requirements maps to at least one test:

**Requirement 1 (Endpoints)**: 6 tests covering POST/GET/PUT/DELETE with success and error cases
**Requirement 2 (Models & Schemas)**: 6 tests covering model structure, schema validation, field types
**Requirement 3 (Rate Limiting)**: 6 tests covering rate limit enforcement, response format, configuration
**Requirement 4 (Validation & Error Handling)**: 6 tests covering validation errors, error codes, error format
**Requirement 5 (Database)**: 6 tests covering model creation, timestamps, filtering, async sessions
**Requirement 6 (API Integration)**: 6 tests covering router registration, authentication, error patterns
**Requirement 7 (Configuration)**: 6 tests covering environment variables, defaults, validation
**Requirement 8 (Structured Logging)**: 6 integration tests covering log events and fields
**Requirement 9 (API Documentation)**: 6 tests covering OpenAPI schema, tags, descriptions

### Test Examples

**Unit Test**: Validate location coordinates
```python
def test_weather_create_invalid_latitude():
    # Arrange: invalid latitude > 90
    data = WeatherCreate(latitude=91, longitude=0, ...)
    # Act & Assert: validation should fail
    with pytest.raises(ValidationError):
        WeatherCreate(**data.dict())
```

**Integration Test**: Create and retrieve weather record
```python
async def test_create_and_retrieve_weather(client, session):
    # Arrange: valid weather data
    weather_data = {...}
    # Act: POST to create
    response = await client.post("/weather", json=weather_data)
    assert response.status_code == 201
    created = response.json()
    # Act: GET to retrieve
    response = await client.get(f"/weather/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created
```

**Rate Limit Test**: Exceed rate limit
```python
async def test_rate_limit_exceeded(client):
    # Arrange: make requests up to limit
    for i in range(30):  # RATE_LIMIT_WEATHER_READ = "30/minute"
        response = await client.get("/weather")
        assert response.status_code == 200
    # Act: exceed limit
    response = await client.get("/weather")
    # Assert: 429 with Retry-After
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.json()["code"] == "RATE_LIMIT_EXCEEDED"
```

## Implementation Notes

### File Structure

```
app/
├── models/
│   └── weather.py          # Weather ORM model
├── schemas/
│   └── weather.py          # WeatherCreate, WeatherUpdate, WeatherRead, ErrorResponse
├── services/
│   └── weather.py          # Business logic, domain exceptions
├── routers/
│   └── weather.py          # Endpoints, rate limiting, authentication
├── config.py               # Extended with weather settings
├── main.py                 # Extended with WeatherNotFoundError handler
└── db.py                   # No changes needed (async sessions already available)

tests/
├── test_weather_models.py
├── test_weather_schemas.py
├── test_weather_service.py
├── test_weather_endpoints.py
├── test_weather_rate_limiting.py
├── test_weather_validation.py
├── test_weather_database.py
├── test_weather_logging.py
└── test_weather_documentation.py
```

### Key Implementation Details

1. **Async SQLAlchemy**: All database operations use async sessions from existing `get_session()` dependency
2. **Rate Limiting**: Uses existing `limiter` instance with environment-based configuration
3. **Authentication**: Uses existing `require_api_key` dependency
4. **Structured Logging**: Uses stdlib `logging` module with JSON formatting via `extra` parameter
5. **Timestamps**: SQLAlchemy server defaults handle automatic timestamp management
6. **Location Filtering**: Implemented as optional query parameters with tolerance-based range queries
7. **Error Handling**: Domain exceptions mapped in single exception handler layer in `main.py`

### Configuration Environment Variables

```bash
# Rate limiting (defaults shown)
RATE_LIMIT_WEATHER_READ=30/minute
RATE_LIMIT_WEATHER_WRITE=10/minute

# Feature flag
WEATHER_COLLECTION_ENABLED=true

# Existing variables (no changes)
API_KEY=dev-secret-key
DATABASE_URL=sqlite+aiosqlite:///./tasks.db
RATE_LIMIT_ENABLED=true
```

### OpenAPI Documentation

The weather router includes:
- Tag: "weather" for all endpoints
- Descriptions for each endpoint
- Request/response schemas with examples
- 429 response with Retry-After header documented
- 404 response with error code documented
- 400 response with validation error details documented

## Design Decisions

### Why Tolerance-Based Location Filtering?

Exact coordinate matching is impractical due to floating-point precision. Tolerance-based filtering allows queries like "all weather records near Berlin" without requiring exact matches. Default tolerance of 0.01 degrees (~1.1 km) provides reasonable geographic precision.

### Why Separate Rate Limit Settings for Read/Write?

Different operations have different resource costs. Write operations (create, update, delete) are more expensive than reads, so lower rate limits for writes protect the system from abuse while allowing more generous read access.

### Why Structured Logging with Extra Fields?

CloudWatch Logs Insights requires consistent field structure for filtering. Using the `extra` parameter in stdlib logging allows us to emit JSON-formatted logs with consistent fields without adding external dependencies like structlog.

### Why Domain-Specific Exceptions?

Domain exceptions (WeatherNotFoundError) make the service layer's contract explicit and allow the HTTP layer to map them to appropriate status codes. This separation keeps business logic independent of HTTP concerns.

### Why Pydantic ConfigDict(from_attributes=True)?

This allows Pydantic to read attributes from SQLAlchemy ORM models directly, enabling seamless conversion from database models to API response schemas without manual mapping.

## Nortal Swarm Constitution Compliance

✅ **SOLID**: Single responsibility per module (models, schemas, services, routers)
✅ **DDD**: Domain logic in services layer, HTTP concerns in routers
✅ **Layering**: Routers → Services → Repositories/DB
✅ **Configuration**: 12-factor via pydantic-settings, no hardcoded values
✅ **Dependencies**: Uses existing stack (FastAPI, SQLAlchemy, slowapi, Pydantic)
✅ **Code Quality**: Type hints on public functions, structured logging, domain exceptions
✅ **Testing**: Test pyramid with unit, integration, and E2E tests
✅ **Security**: API key authentication, input validation, no secrets in logs
✅ **API Design**: Resource-oriented URLs, correct HTTP verbs/status codes, consistent error envelope
✅ **Git & Delivery**: Focused scope, logical commits, spec-driven implementation
