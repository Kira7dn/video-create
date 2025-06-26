"""
Comprehensive test suite for the improved Video Creation API
"""

import os
import sys
import pytest
import json
import tempfile
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

client = TestClient(app)


@pytest.fixture
def sample_json_path():
    """Fixture providing path to sample JSON file"""
    return os.path.join(os.path.dirname(__file__), "..", "input_sample.json")


@pytest.fixture
def result_dir():
    """Fixture providing result directory for test outputs"""
    result_dir = os.path.join(os.path.dirname(__file__), "result")
    os.makedirs(result_dir, exist_ok=True)
    return result_dir


class TestVideoCreationAPI:
    """Test class for Video Creation API endpoints"""

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "video-creation-api"
        assert "version" in data
        print("✅ Health check passed")

    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"
        print("✅ Root endpoint passed")

    def test_api_create_video_success(self, sample_json_path, result_dir):
        """Test successful video creation with valid JSON"""
        if not os.path.exists(sample_json_path):
            pytest.skip(f"Sample JSON file not found: {sample_json_path}")

        with open(sample_json_path, "rb") as f:
            files = {"input_json": ("input_sample.json", f, "application/json")}
            response = client.post("/api/create-video", files=files)

        assert response.status_code == 200, f"API failed: {response.text}"
        assert response.headers["content-type"] == "video/mp4"
        assert "X-Video-ID" in response.headers
        assert "Content-Disposition" in response.headers

        # Save result for manual verification
        out_path = os.path.join(result_dir, "test_success_result.mp4")
        with open(out_path, "wb") as fout:
            fout.write(response.content)

        assert os.path.exists(out_path) and os.path.getsize(out_path) > 0
        print(f"✅ Video creation success test passed. Output: {out_path}")

    def test_api_create_video_invalid_file_format(self):
        """Test with invalid file format"""
        # Create a text file instead of JSON
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"This is not a JSON file")
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                files = {"input_json": ("test.txt", f, "text/plain")}
                response = client.post("/api/create-video", files=files)

            print(f"Debug - Status: {response.status_code}")
            print(f"Debug - Response: {response.text}")

            assert response.status_code == 400
            error_data = response.json()
            print(f"Debug - Error data: {error_data}")

            # Check different possible response structures
            if "detail" in error_data:
                if isinstance(error_data["detail"], dict):
                    assert "error" in error_data["detail"]
                    assert "File validation failed" in error_data["detail"]["error"]
                else:
                    assert "File validation failed" in str(error_data["detail"])
            else:
                assert "File validation failed" in str(error_data)

            print("✅ Invalid file format test passed")
        finally:
            os.unlink(tmp_path)

    def test_api_create_video_malformed_json(self):
        """Test with malformed JSON"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b'{"invalid": json syntax}')  # Malformed JSON
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                files = {"input_json": ("invalid.json", f, "application/json")}
                response = client.post("/api/create-video", files=files)

            assert response.status_code == 500
            error_data = response.json()
            assert "error" in error_data["detail"]
            print("✅ Malformed JSON test passed")
        finally:
            os.unlink(tmp_path)

    def test_api_create_video_empty_array(self):
        """Test with empty JSON array"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b"[]")  # Empty array
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                files = {"input_json": ("empty.json", f, "application/json")}
                response = client.post("/api/create-video", files=files)

            assert response.status_code == 400
            error_data = response.json()
            assert "Empty input" in error_data["detail"]["error"]
            print("✅ Empty array test passed")
        finally:
            os.unlink(tmp_path)

    def test_api_create_video_invalid_json_structure(self):
        """Test with JSON that's not an array"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(b'{"not": "an array"}')  # Object instead of array
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                files = {"input_json": ("object.json", f, "application/json")}
                response = client.post("/api/create-video", files=files)

            assert response.status_code == 400
            error_data = response.json()
            assert "Invalid input format" in error_data["detail"]["error"]
            print("✅ Invalid JSON structure test passed")
        finally:
            os.unlink(tmp_path)

    def test_api_create_video_large_file(self):
        """Test with file exceeding size limit"""
        # Create a large JSON file (>100MB)
        large_data = [{"test": "x" * (1024 * 1024)}] * 101  # > 100MB

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(json.dumps(large_data).encode())
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                files = {"input_json": ("large.json", f, "application/json")}
                response = client.post("/api/create-video", files=files)

            print(f"Debug - Large file test status: {response.status_code}")
            print(f"Debug - Large file test response: {response.text}")

            # File size validation returns 400, not 413
            assert response.status_code == 400
            error_data = response.json()
            print(f"Debug - Large file error data: {error_data}")
            assert "File too large" in error_data["detail"]["details"]
            print("✅ Large file test passed")
        finally:
            os.unlink(tmp_path)

    def test_api_create_video_missing_file(self):
        """Test without providing required file"""
        response = client.post("/api/create-video")
        assert response.status_code == 422  # Unprocessable Entity
        error_data = response.json()
        assert "detail" in error_data
        assert any("Field required" in str(error) for error in error_data["detail"])
        print("✅ Missing file test passed")

    def test_api_create_video_with_transitions(self, sample_json_path, result_dir):
        """Test video creation with transitions parameter"""
        if not os.path.exists(sample_json_path):
            pytest.skip(f"Sample JSON file not found: {sample_json_path}")

        with open(sample_json_path, "rb") as f:
            files = {"input_json": ("input_sample.json", f, "application/json")}
            data = {"transitions": "fade"}
            response = client.post("/api/create-video", files=files, data=data)

        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"

        # Save result
        out_path = os.path.join(result_dir, "test_transitions_result.mp4")
        with open(out_path, "wb") as fout:
            fout.write(response.content)

        assert os.path.exists(out_path) and os.path.getsize(out_path) > 0
        print(f"✅ Transitions test passed. Output: {out_path}")


class TestVideoCreationAPIEdgeCases:
    """Additional edge case tests"""

    def test_concurrent_requests(self, sample_json_path):
        """Test handling multiple concurrent requests"""
        if not os.path.exists(sample_json_path):
            pytest.skip(f"Sample JSON file not found: {sample_json_path}")

        import threading
        import time

        results = []

        def make_request():
            with open(sample_json_path, "rb") as f:
                files = {"input_json": ("input_sample.json", f, "application/json")}
                response = client.post("/api/create-video", files=files)
                results.append(response.status_code)

        # Create multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(results) == 3
        # At least some should succeed (depending on system resources)
        assert any(status == 200 for status in results)
        print("✅ Concurrent requests test passed")


if __name__ == "__main__":
    # Run specific tests
    test_api = TestVideoCreationAPI()

    print("Running Video Creation API Tests...")
    print("=" * 50)

    # Basic tests
    test_api.test_health_check()
    test_api.test_root_endpoint()
    test_api.test_api_create_video_missing_file()
    test_api.test_api_create_video_invalid_file_format()
    test_api.test_api_create_video_malformed_json()
    test_api.test_api_create_video_empty_array()
    test_api.test_api_create_video_invalid_json_structure()
    test_api.test_api_create_video_large_file()

    # Success tests (if sample file exists)
    sample_json = "input_sample.json"  # File in root directory
    result_dir = os.path.join(os.path.dirname(__file__), "result")
    os.makedirs(result_dir, exist_ok=True)

    if os.path.exists(sample_json):
        test_api.test_api_create_video_success(sample_json, result_dir)
        test_api.test_api_create_video_with_transitions(sample_json, result_dir)
    else:
        print("⚠️  Skipping success tests - input_sample.json not found")

    print("=" * 50)
    print("✅ All tests completed!")
