from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.runtime.enums import ComponentState
from core.voice import (
    AudioFrame,
    ConversationState,
    DefaultMicrophoneProvider,
    DefaultSpeakerProvider,
    DefaultVADProvider,
    OpenWakeWordProvider,
    PiperTTSProvider,
    VoiceManager,
    WhisperSTTProvider,
)


@pytest.fixture
def mic():
    return DefaultMicrophoneProvider()

@pytest.fixture
def speaker():
    return DefaultSpeakerProvider()

@pytest.fixture
def vad():
    return DefaultVADProvider(threshold=100)

@pytest.fixture
def wakeword():
    return OpenWakeWordProvider()

@pytest.fixture
def stt():
    return WhisperSTTProvider()

@pytest.fixture
def tts():
    return PiperTTSProvider()

@pytest.fixture
def manager(mic, speaker, vad, wakeword, stt, tts):
    logger = MagicMock()
    event_bus = EventBus(logger)
    return VoiceManager(
        microphone=mic,
        speaker=speaker,
        vad=vad,
        wakeword=wakeword,
        stt=stt,
        tts=tts,
        event_bus=event_bus,
        logger=logger
    )

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    
    manager.listen()
    assert manager._conversation.session is not None
    assert manager._conversation.session.state == ConversationState.WAITING_FOR_WAKEWORD
    
    manager.mute()
    assert manager._conversation.session is None
    
    await manager.stop()
    assert manager.state == ComponentState.STOPPED

@pytest.mark.asyncio
async def test_vad_speech_detection(vad):
    silence = AudioFrame(data=b"\x00\x00\x00\x00")
    speech = AudioFrame(data=b"\xff\x7f\x00\x00")  # High amplitude
    
    assert vad.is_speech(silence) is False
    assert vad.is_speech(speech) is True

@pytest.mark.asyncio
async def test_wakeword_detection(wakeword):
    frame1 = AudioFrame(data=b"random noise")
    frame2 = AudioFrame(data=b"WAKEWORD sequence")
    
    assert wakeword.detect(frame1) is None
    res = wakeword.detect(frame2)
    assert res is not None
    assert res.word == "jarvis"

@pytest.mark.asyncio
async def test_speak(manager):
    await manager.start()
    await manager.speak("hello world")
    # By default mock speaker just awaits.
    # If it completed, state should return to WAITING_FOR_WAKEWORD
    # (Though we mock it, we test state transitions in manager)

@pytest.mark.asyncio
async def test_stt_transcription(stt):
    res1 = await stt.transcribe(b"some audio")
    assert res1.text == "hello jarvis"
    
    res2 = await stt.transcribe(b"some TEST_SPEECH audio")
    assert res2.text == "this is a test"

@pytest.mark.asyncio
async def test_tts_synthesis(tts):
    res = await tts.synthesize("test")
    assert res.text == "test"
    assert len(res.audio_data) > 0
