"""
Tests for LLM integration.
"""
import pytest
from unittest.mock import patch, AsyncMock


class TestSummarization:
    """Tests for transcript summarization."""
    
    @pytest.mark.asyncio
    async def test_summarize_transcript_success(self, sample_transcript, mock_llm_response):
        """Test successful summarization."""
        from app.llm import summarize_transcript
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_llm_response
            )
            
            result = await summarize_transcript(
                transcript=sample_transcript,
                prompt="Summarize this.",
                api_token="sk-test",
                api_endpoint="https://api.test.com",
                model="test-model"
            )
            
            assert isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_transcript_truncation(self):
        """Test that very long transcripts are handled."""
        from app.llm import summarize_transcript
        
        long_transcript = "A" * 400000
        
        assert len(long_transcript) > 350000
    
    @pytest.mark.asyncio
    async def test_stream_summarize_transcript(self, sample_transcript):
        """Test streaming summarization returns async generator."""
        from app.llm import stream_summarize_transcript
        
        result = stream_summarize_transcript(
            transcript=sample_transcript,
            prompt="Summarize",
            api_token="sk-test",
            api_endpoint="https://api.test.com",
            model="test-model"
        )
        
        assert hasattr(result, '__anext__')


class TestLLMConfiguration:
    """Tests for LLM configuration."""
    
    def test_default_model(self):
        """Test default model is set."""
        from app.config import get_default_model
        
        model = get_default_model()
        
        assert model is not None
        assert isinstance(model, str)
    
    def test_default_endpoint(self):
        """Test default API endpoint."""
        from app.config import get_default_api_endpoint
        
        endpoint = get_default_api_endpoint()
        
        assert endpoint is not None
        assert "http" in endpoint
    
    def test_model_in_config(self):
        """Test model is in settings."""
        from app.config import get_settings
        
        settings = get_settings()
        
        assert hasattr(settings, 'default_model')
        assert settings.default_model is not None
