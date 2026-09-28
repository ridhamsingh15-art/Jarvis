"""
Tests for Production Voice Integration.
"""
import pytest
from unittest.mock import Mock, patch

from core.integrations.voice.manager import VoiceManager
from core.integrations.voice.models import VoiceRequest, ProviderType
from core.integrations.voice.exceptions import SynthesisFailedError, VoiceProviderOfflineError

class TestVoiceManager:
    
    @patch("core.integrations.voice.manager.ProviderHealthCheck.check_elevenlabs")
    @patch("core.integrations.voice.elevenlabs.client.ElevenLabsClient.synthesize")
    def test_elevenlabs_success(self, mock_synth, mock_health):
        mock_health.return_value = True
        mock_synth.return_value = Mock(audio_data=b"AUDIO", provider_used=ProviderType.ELEVENLABS)
        
        manager = VoiceManager()
        req = VoiceRequest(text="Hello", provider=ProviderType.ELEVENLABS)
        resp = manager.generate(req)
        
        assert resp.audio_data == b"AUDIO"
        assert resp.provider_used == ProviderType.ELEVENLABS
        mock_synth.assert_called_once()
        
    @patch("core.integrations.voice.manager.ProviderHealthCheck.check_elevenlabs")
    @patch("core.integrations.voice.elevenlabs.client.ElevenLabsClient.synthesize")
    @patch("core.integrations.voice.piper.client.PiperClient.synthesize")
    def test_fallback_to_piper(self, mock_piper_synth, mock_eleven_synth, mock_eleven_health):
        # Force ElevenLabs health check to fail
        mock_eleven_health.side_effect = VoiceProviderOfflineError("Offline")
        
        # Mock Piper success
        mock_piper_synth.return_value = Mock(audio_data=b"PIPER_AUDIO", provider_used=ProviderType.PIPER)
        
        manager = VoiceManager()
        req = VoiceRequest(text="Hello", provider=ProviderType.ELEVENLABS, allow_fallback=True)
        resp = manager.generate(req)
        
        assert resp.audio_data == b"PIPER_AUDIO"
        assert resp.provider_used == ProviderType.PIPER
        # verify elevenlabs synth was never called due to health check failing
        mock_eleven_synth.assert_not_called()
        mock_piper_synth.assert_called_once()
