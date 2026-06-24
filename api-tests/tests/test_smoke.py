import pytest


class TestSmoke:
    """
    Smoke tests - basic connectivity and auth verification.
    These run first to confirm the dev environment is alive.
    """

    @pytest.mark.smoke
    def test_api_is_reachable(self, api, base_url):
        """Verify the dev API responds at all."""
        response = api.get(f"{base_url}/public/p2/v2/consumer", 
                          params={"page": 0, "size": 1})
        assert response.status_code != 503, "API is down (503)"
        assert response.status_code != 404, "API endpoint not found (404)"
        print(f"\nAPI status: {response.status_code}")

    @pytest.mark.smoke
    def test_auth_token_is_valid(self, api, base_url):
        """Verify Bearer token is accepted (not expired)."""
        response = api.get(f"{base_url}/public/p2/v2/consumer",
                          params={"page": 0, "size": 1})
        assert response.status_code != 401, \
            "Token is invalid or expired — update BEARER_TOKEN in .env"
        assert response.status_code != 403, \
            "Token has no permission for this endpoint"
        print(f"\nAuth status: {response.status_code}")

    @pytest.mark.smoke
    def test_api_returns_json(self, api, base_url):
        """Verify API returns valid JSON response."""
        response = api.get(f"{base_url}/public/p2/v2/consumer",
                          params={"page": 0, "size": 1})
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.text}"
        
        json_response = response.json()
        assert json_response is not None, "Response is not valid JSON"
        print(f"\nResponse keys: {list(json_response.keys())}")

    @pytest.mark.smoke  
    def test_response_has_pagination(self, api, base_url):
        """Verify paginated response structure."""
        response = api.get(f"{base_url}/public/p2/v2/consumer",
                          params={"page": 0, "size": 1})
        assert response.status_code == 200

        data = response.json()
        # Spring Boot pagination standard fields
        assert "content" in data or "data" in data, \
            f"No pagination in response. Keys: {list(data.keys())}"
        print(f"\nPagination response structure: {list(data.keys())}")