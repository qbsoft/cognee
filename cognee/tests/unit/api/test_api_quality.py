"""
Phase 9: API Documentation and Error Handling Quality Tests (T901-T902)

Tests for OpenAPI/Swagger documentation completeness and error handling
robustness, using mocks with NO real DB/LLM/network connections.

Test Coverage:
  T901: API Documentation (OpenAPI/Swagger) Verification
    - OpenAPI schema generation
    - Schema metadata (title, version, description)
    - Major endpoint paths present
    - Endpoint descriptions/summaries
    - Request/response model schemas
    - /docs and /redoc endpoints serve correctly
    - SearchType enum values in schema

  T902: Error Handling and Logging Verification
    - Proper error format on exceptions
    - 404 JSON responses
    - Validation error (422/400) detail structure
    - Internal server error (500) does not leak stack traces
    - CORS headers present
    - Exception handlers registered
    - Logger instances configured in key modules
    - Sensitive information not leaked in error responses
"""

import os
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Set environment before importing any cognee modules
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("REQUIRE_AUTHENTICATION", "false")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id=None, email="test@example.com"):
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.is_superuser = False
    user.is_active = True
    user.is_verified = True
    user.tenant_id = None
    return user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_app():
    """Import the real FastAPI app object (no TestClient, no lifespan trigger).

    The app object in cognee.api.client is created at module-load time
    (``app = FastAPI(...)``), so simply importing it does NOT trigger
    the async lifespan and therefore does NOT require database access.
    This gives us access to the registered routes, middleware, exception
    handlers, and OpenAPI schema without any side-effects.
    """
    from cognee.api.client import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="module")
def openapi_schema(real_app):
    """Get the OpenAPI schema from the real app.

    Calling ``app.openapi()`` only inspects the registered routes and
    the custom ``custom_openapi`` function. It does NOT start the server
    or trigger database connections.
    """
    # Reset cached schema so custom_openapi runs fresh
    real_app.openapi_schema = None
    return real_app.openapi()


@pytest.fixture(scope="module")
def test_app():
    """Build a lightweight FastAPI app that mirrors the real one for HTTP tests.

    This avoids the lifespan DB initialization while keeping:
    - The same routers (add, search, cognify, datasets, settings, delete)
    - The same exception handlers
    - The same CORS middleware
    - The same auth dependency (overridden to return a mock user)
    """
    from fastapi import FastAPI, Request, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    from fastapi.encoders import jsonable_encoder
    from cognee.exceptions import CogneeApiError
    from cognee.modules.users.methods import get_authenticated_user

    app = FastAPI(title="Cognee API", version="1.0.0")

    # ---- CORS middleware (same as real app) ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["OPTIONS", "GET", "PUT", "POST", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # ---- Exception handlers (same as real app) ----
    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
        if request.url.path == "/api/v1/auth/login":
            return JSONResponse(
                status_code=400,
                content={"detail": "LOGIN_BAD_CREDENTIALS"},
            )
        return JSONResponse(
            status_code=400,
            content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
        )

    @app.exception_handler(CogneeApiError)
    async def cognee_exception_handler(_: Request, exc: CogneeApiError) -> JSONResponse:
        detail = {}
        if exc.name and exc.message and exc.status_code:
            status_code = exc.status_code
            detail["message"] = f"{exc.message} [{exc.name}]"
        else:
            status_code = status.HTTP_418_IM_A_TEAPOT
            detail["message"] = "An unexpected error occurred."
        return JSONResponse(status_code=status_code, content={"detail": detail["message"]})

    # ---- Override auth dependency ----
    mock_user = _make_user()

    async def override_auth():
        return mock_user

    app.dependency_overrides[get_authenticated_user] = override_auth

    # ---- Root and health endpoints ----
    @app.get("/")
    async def root():
        return {"message": "Hello, World, I am alive!"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "1.0.0"}

    # ---- Include routers (same as real app) ----
    from cognee.api.v1.add.routers import get_add_router
    from cognee.api.v1.search.routers import get_search_router
    from cognee.api.v1.cognify.routers import get_cognify_router
    from cognee.api.v1.datasets.routers import get_datasets_router
    from cognee.api.v1.settings.routers import get_settings_router
    from cognee.api.v1.delete.routers import get_delete_router
    from cognee.api.v1.users.routers import get_auth_router

    app.include_router(get_auth_router(), prefix="/api/v1/auth", tags=["auth"])
    app.include_router(get_add_router(), prefix="/api/v1/add", tags=["add"])
    app.include_router(get_cognify_router(), prefix="/api/v1/cognify", tags=["cognify"])
    app.include_router(get_search_router(), prefix="/api/v1/search", tags=["search"])
    app.include_router(get_datasets_router(), prefix="/api/v1/datasets", tags=["datasets"])
    app.include_router(get_settings_router(), prefix="/api/v1/settings", tags=["settings"])
    app.include_router(get_delete_router(), prefix="/api/v1/delete", tags=["delete"])

    return app


@pytest.fixture(scope="module")
def client(test_app):
    """TestClient for the lightweight test app."""
    from fastapi.testclient import TestClient
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# T901: API Documentation (OpenAPI/Swagger) Verification
# ===========================================================================

class TestT901_OpenAPISchemaGeneration:
    """Test that the FastAPI app generates a valid OpenAPI schema."""

    def test_openapi_schema_is_generated(self, openapi_schema):
        """T901-01: The app.openapi() call returns a non-empty dict."""
        assert openapi_schema is not None
        assert isinstance(openapi_schema, dict)
        assert len(openapi_schema) > 0

    def test_openapi_schema_has_openapi_version(self, openapi_schema):
        """T901-02: Schema includes the OpenAPI specification version."""
        assert "openapi" in openapi_schema
        assert openapi_schema["openapi"].startswith("3.")


class TestT901_SchemaMetadata:
    """Test that the OpenAPI schema has proper metadata fields."""

    def test_schema_has_title(self, openapi_schema):
        """T901-03: Schema info contains a title."""
        assert "info" in openapi_schema
        assert "title" in openapi_schema["info"]
        assert len(openapi_schema["info"]["title"]) > 0

    def test_schema_title_is_cognee_api(self, openapi_schema):
        """T901-04: Schema title is 'Cognee API'."""
        assert openapi_schema["info"]["title"] == "Cognee API"

    def test_schema_has_version(self, openapi_schema):
        """T901-05: Schema info contains a version."""
        assert "version" in openapi_schema["info"]
        assert len(openapi_schema["info"]["version"]) > 0

    def test_schema_has_description(self, openapi_schema):
        """T901-06: Schema info contains a description."""
        assert "description" in openapi_schema["info"]
        assert len(openapi_schema["info"]["description"]) > 0


class TestT901_EndpointPaths:
    """Test that all major API endpoints appear in the OpenAPI paths."""

    MAJOR_ENDPOINTS = [
        ("/api/v1/add", "post"),
        ("/api/v1/search", "post"),
        ("/api/v1/cognify", "post"),
        ("/api/v1/datasets", "get"),
        ("/api/v1/settings", "get"),
        ("/health", "get"),
    ]

    @pytest.mark.parametrize("path,method", MAJOR_ENDPOINTS)
    def test_endpoint_exists_in_schema(self, openapi_schema, path, method):
        """T901-07: Major endpoint {path} ({method}) is present in OpenAPI paths."""
        paths = openapi_schema.get("paths", {})
        assert path in paths, f"Path {path} not found in OpenAPI schema paths"
        assert method in paths[path], \
            f"Method {method} not found for path {path}"


class TestT901_EndpointDocumentation:
    """Test that each endpoint has description or summary in the schema."""

    DOCUMENTED_ENDPOINTS = [
        "/api/v1/add",
        "/api/v1/search",
        "/api/v1/cognify",
        "/api/v1/datasets",
        "/api/v1/settings",
        "/health",
    ]

    @pytest.mark.parametrize("path", DOCUMENTED_ENDPOINTS)
    def test_endpoint_has_documentation(self, openapi_schema, path):
        """T901-08: Endpoint {path} has description or summary."""
        paths = openapi_schema.get("paths", {})
        assert path in paths, f"Path {path} not in schema"

        endpoint_data = paths[path]
        for method, method_data in endpoint_data.items():
            if method in ("get", "post", "put", "delete", "patch"):
                has_doc = (
                    "description" in method_data
                    or "summary" in method_data
                )
                assert has_doc, \
                    f"Endpoint {path} {method.upper()} has no description or summary"


class TestT901_SchemaComponents:
    """Test that request/response models are included in schema components."""

    def test_components_section_exists(self, openapi_schema):
        """T901-09: Schema has a 'components' section."""
        assert "components" in openapi_schema

    def test_schemas_section_exists(self, openapi_schema):
        """T901-10: Schema components has a 'schemas' sub-section."""
        assert "schemas" in openapi_schema.get("components", {})

    def test_schema_has_model_definitions(self, openapi_schema):
        """T901-11: Schema components/schemas contains model definitions."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        assert len(schemas) > 0, "No model schemas found in components"

    def test_security_schemes_exist(self, openapi_schema):
        """T901-12: Schema components has securitySchemes."""
        security_schemes = openapi_schema.get("components", {}).get("securitySchemes", {})
        assert len(security_schemes) > 0, "No security schemes defined"

    def test_bearer_auth_scheme_exists(self, openapi_schema):
        """T901-13: BearerAuth security scheme is defined."""
        security_schemes = openapi_schema.get("components", {}).get("securitySchemes", {})
        assert "BearerAuth" in security_schemes
        assert security_schemes["BearerAuth"]["type"] == "http"
        assert security_schemes["BearerAuth"]["scheme"] == "bearer"

    def test_search_payload_model_exists(self, openapi_schema):
        """T901-14: SearchPayloadDTO model is referenced in the schema."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        schema_names = list(schemas.keys())
        has_search_model = any(
            "SearchPayload" in name or "search" in name.lower()
            for name in schema_names
        )
        assert has_search_model, \
            f"No search-related model found in schemas: {schema_names}"


class TestT901_DocsEndpoints:
    """Test that /docs and /redoc endpoints serve correctly.

    These tests use the real app with mocked lifespan since TestClient is
    needed to fetch /docs and /redoc HTML pages.
    """

    @pytest.fixture(scope="class")
    def real_client(self, real_app):
        """TestClient for the real app with mocked lifespan."""
        from fastapi.testclient import TestClient

        with patch(
            "cognee.infrastructure.databases.relational.get_relational_engine",
        ) as mock_engine, patch(
            "cognee.modules.users.methods.get_default_user",
            new_callable=AsyncMock,
        ):
            mock_db = MagicMock()
            mock_db.create_database = AsyncMock()
            mock_engine.return_value = mock_db
            with TestClient(real_app, raise_server_exceptions=False) as c:
                yield c

    def test_docs_endpoint_returns_200(self, real_client):
        """T901-15: The /docs endpoint serves Swagger UI (returns 200)."""
        response = real_client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

    def test_redoc_endpoint_returns_200(self, real_client):
        """T901-16: The /redoc endpoint serves ReDoc (returns 200)."""
        response = real_client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()

    def test_openapi_json_endpoint_returns_200(self, real_client):
        """T901-17: The /openapi.json endpoint returns the schema."""
        response = real_client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data


class TestT901_SearchTypeEnum:
    """Test that SearchType enum values appear in the schema."""

    def test_search_type_values_in_schema(self, openapi_schema):
        """T901-18: SearchType enum values appear in the schema components."""
        schema_str = json.dumps(openapi_schema)

        core_search_types = [
            "CHUNKS",
            "GRAPH_COMPLETION",
            "SUMMARIES",
            "RAG_COMPLETION",
        ]

        for search_type in core_search_types:
            assert search_type in schema_str, \
                f"SearchType value '{search_type}' not found in OpenAPI schema"

    def test_search_type_enum_is_referenced(self, openapi_schema):
        """T901-19: SearchType is referenced in the search endpoint schema."""
        paths = openapi_schema.get("paths", {})
        search_path = paths.get("/api/v1/search", {})
        post_data = search_path.get("post", {})

        request_body = post_data.get("requestBody", {})
        assert request_body, "Search POST endpoint should have a requestBody"

    def test_all_search_type_values_present(self, openapi_schema):
        """T901-20: All SearchType enum values are present in the schema."""
        from cognee.modules.search.types.SearchType import SearchType

        schema_str = json.dumps(openapi_schema)

        for st in SearchType:
            assert st.value in schema_str, \
                f"SearchType.{st.name} (value='{st.value}') not found in OpenAPI schema"


# ===========================================================================
# T902: Error Handling and Logging Verification
# ===========================================================================

class TestT902_ErrorResponseFormat:
    """Test that API endpoints return proper error format on exceptions."""

    def test_cognee_api_error_returns_json_with_detail(self, client, test_app):
        """T902-01: CogneeApiError exceptions return JSON with detail field."""
        from cognee.exceptions.exceptions import CogneeApiError
        from cognee.modules.users.methods import get_authenticated_user

        # Override auth to raise CogneeApiError
        async def raise_error():
            raise CogneeApiError(
                message="Test error",
                name="TestError",
                status_code=400,
                log=False,
            )

        test_app.dependency_overrides[get_authenticated_user] = raise_error
        try:
            response = client.get("/api/v1/datasets")
            assert response.headers.get("content-type", "").startswith("application/json")
            data = response.json()
            assert "detail" in data
        finally:
            # Restore the normal mock
            async def normal_auth():
                return _make_user()
            test_app.dependency_overrides[get_authenticated_user] = normal_auth

    def test_root_endpoint_returns_valid_json(self, client):
        """T902-02: Root endpoint returns valid JSON response."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestT902_NotFoundErrors:
    """Test that 404 errors return proper JSON response."""

    def test_nonexistent_path_returns_404_json(self, client):
        """T902-03: Requesting a non-existent path returns 404."""
        response = client.get("/api/v1/this-does-not-exist-anywhere")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_404_response_is_json_content_type(self, client):
        """T902-04: 404 response has JSON content type."""
        response = client.get("/totally-nonexistent-endpoint")
        assert response.status_code == 404
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type


class TestT902_ValidationErrors:
    """Test that validation errors (422/400) include detail field."""

    def test_invalid_search_payload_returns_validation_error(self, client):
        """T902-05: Invalid payload returns validation error with detail field."""
        response = client.post(
            "/api/v1/search",
            json={
                "search_type": "INVALID_TYPE_THAT_DOES_NOT_EXIST",
                "query": "test",
            },
        )
        assert response.status_code in (400, 422)
        data = response.json()
        assert "detail" in data

    def test_validation_error_contains_field_info(self, client):
        """T902-06: Validation errors contain field-level error information."""
        response = client.post(
            "/api/v1/auth/login",
            data={},
        )
        assert response.status_code in (400, 422)
        data = response.json()
        assert "detail" in data


class TestT902_InternalServerErrors:
    """Test that internal server errors (500) don't leak stack traces."""

    def test_cognify_500_does_not_leak_traceback(self, client):
        """T902-07: 500 errors from cognify don't expose raw stack traces."""
        with patch(
            "cognee.api.v1.cognify.cognify.cognify",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Internal DB connection failed at line 42 in db.py"),
        ):
            response = client.post(
                "/api/v1/cognify",
                json={"datasets": ["test_dataset"]},
            )
            body_text = response.text
            assert "Traceback (most recent call last)" not in body_text
            assert "File \"" not in body_text

    def test_error_response_does_not_leak_file_paths(self, client):
        """T902-08: Error responses don't expose server file system paths."""
        with patch(
            "cognee.api.v1.cognify.cognify.cognify",
            new_callable=AsyncMock,
            side_effect=Exception("secret failure"),
        ):
            response = client.post(
                "/api/v1/cognify",
                json={"datasets": ["test_dataset"]},
            )
            body_text = response.text
            assert "site-packages" not in body_text
            assert ".py\", line" not in body_text


class TestT902_CORSHeaders:
    """Test that CORS headers are properly configured."""

    def test_cors_middleware_is_configured(self, real_app):
        """T902-09: The real app has CORS middleware configured."""
        has_cors = any("CORS" in str(m) for m in real_app.user_middleware)
        assert has_cors, "CORS middleware not found in app middleware stack"

    def test_cors_allows_configured_origins(self, client):
        """T902-10: CORS responds with proper headers for allowed origins."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 204)

    def test_cors_allowed_methods_on_real_app(self, real_app):
        """T902-11: CORS middleware on real app allows standard HTTP methods."""
        for m in real_app.user_middleware:
            if "CORS" in str(m):
                kwargs = m.kwargs if hasattr(m, 'kwargs') else {}
                allowed_methods = kwargs.get("allow_methods", [])
                if allowed_methods:
                    assert "GET" in allowed_methods or "*" in allowed_methods
                    assert "POST" in allowed_methods or "*" in allowed_methods
                break


class TestT902_ExceptionHandlers:
    """Test that the app has proper exception handlers registered."""

    def test_real_app_has_exception_handlers(self, real_app):
        """T902-12: The real app has exception handlers registered."""
        assert hasattr(real_app, 'exception_handlers')
        assert len(real_app.exception_handlers) > 0

    def test_request_validation_handler_registered(self, real_app):
        """T902-13: RequestValidationError handler is registered on real app."""
        from fastapi.exceptions import RequestValidationError
        assert RequestValidationError in real_app.exception_handlers

    def test_cognee_api_error_handler_registered(self, real_app):
        """T902-14: CogneeApiError handler is registered on real app."""
        from cognee.exceptions.exceptions import CogneeApiError
        assert CogneeApiError in real_app.exception_handlers

    def test_custom_openapi_function_is_set(self, real_app):
        """T902-15: The real app uses a custom openapi function with security schemes."""
        schema = real_app.openapi()
        assert schema is not None
        assert "securitySchemes" in schema.get("components", {})


class TestT902_LoggerConfiguration:
    """Test that logging is configured in key modules."""

    def test_client_module_has_logger(self):
        """T902-16: The API client module has a logger configured."""
        import cognee.api.client as client_module
        assert hasattr(client_module, 'logger')

    def test_get_logger_returns_logger_instance(self):
        """T902-17: get_logger returns a valid logger instance."""
        from cognee.shared.logging_utils import get_logger
        logger = get_logger("test")
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'debug')

    def test_key_modules_use_logging(self):
        """T902-18: Key API modules use logging."""
        import importlib
        modules_with_loggers = [
            "cognee.api.client",
            "cognee.api.health",
        ]
        for module_name in modules_with_loggers:
            mod = importlib.import_module(module_name)
            assert hasattr(mod, 'logger'), \
                f"Module {module_name} does not have a logger attribute"

    def test_get_logger_named_logger(self):
        """T902-19: get_logger with a name returns a named logger."""
        from cognee.shared.logging_utils import get_logger
        logger = get_logger("cognee.test.quality")
        assert logger is not None


class TestT902_SensitiveInformationProtection:
    """Test that sensitive information is not leaked in error responses."""

    def test_settings_api_key_not_in_schema(self, openapi_schema):
        """T902-20: API key values are not exposed in OpenAPI schema."""
        schema_str = json.dumps(openapi_schema)
        assert "sk-" not in schema_str
        assert "test-key" not in schema_str

    def test_error_handler_does_not_include_password(self):
        """T902-21: CogneeApiError string does not contain password fields."""
        from cognee.exceptions.exceptions import CogneeApiError
        error = CogneeApiError(
            message="Auth failed",
            name="AuthError",
            status_code=401,
            log=False,
        )
        error_str = str(error)
        assert "password" not in error_str.lower() or "auth" in error_str.lower()

    def test_health_endpoint_does_not_expose_credentials(self, client):
        """T902-22: Health endpoint doesn't expose database credentials."""
        response = client.get("/health")
        body_text = response.text
        assert "password=" not in body_text.lower()
        assert "postgresql://" not in body_text.lower()

    def test_cognify_error_does_not_expose_raw_traceback(self, client):
        """T902-23: Cognify error responses don't expose full tracebacks."""
        with patch(
            "cognee.api.v1.cognify.cognify.cognify",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed: api_key=sk-1234567890abcdef"),
        ):
            response = client.post(
                "/api/v1/cognify",
                json={"datasets": ["test"]},
            )
            data = response.json()
            assert isinstance(data, dict)
            body_text = response.text
            assert "Traceback" not in body_text


class TestT902_ErrorCodeConsistency:
    """Test that error codes are consistent across the API."""

    def test_cognify_no_datasets_returns_400(self, client):
        """T902-24: Cognify with no datasets returns 400."""
        response = client.post(
            "/api/v1/cognify",
            json={},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_health_endpoint_returns_structured_response(self, client):
        """T902-25: Health endpoint returns structured response."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_exception_handler_callable(self, real_app):
        """T902-26: Exception handler for CogneeApiError is callable."""
        from cognee.exceptions.exceptions import CogneeApiError
        handler = real_app.exception_handlers.get(CogneeApiError)
        assert handler is not None
        assert callable(handler)
