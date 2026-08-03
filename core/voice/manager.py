from core.events.bus import EventBus
from core.models.domain import Event
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .conversation import ConversationManager
from .enums import ConversationState
from .interfaces import (
    MicrophoneProvider,
    SpeakerProvider,
    STTProvider,
    TTSProvider,
    VADProvider,
    WakeWordProvider,
)
from .models import Transcript


class VoiceManager(RuntimeComponent):
    """Orchestrates the Voice Subsystem."""

    def __init__(
        self,
        microphone: MicrophoneProvider,
        speaker: SpeakerProvider,
        vad: VADProvider,
        wakeword: WakeWordProvider,
        stt: STTProvider,
        tts: TTSProvider,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._speaker = speaker
        self._tts = tts
        self._event_bus = event_bus
        self._logger = logger

        self._conversation = ConversationManager(
            microphone=microphone,
            vad=vad,
            wakeword=wakeword,
            stt=stt,
            on_wakeword=self._on_wakeword,
            on_transcript=self._on_transcript
        )

        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.voice",
            name="Voice System",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return

        self._state = ComponentState.STARTING
        self._logger.info("Starting Voice System...")
        
        # We don't automatically listen until requested, but subsystem is running
        self._state = ComponentState.RUNNING
        self._publish_event("voice.started", {})
        self._logger.info("Voice System started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Voice System...")
        
        self._conversation.stop_session()
        self._speaker.stop()
        
        self._state = ComponentState.STOPPED
        self._publish_event("voice.stopped", {})
        self._logger.info("Voice System stopped.")

    async def health(self) -> HealthReport:
        try:
            active = self._conversation.session is not None
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={"listening": active}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def listen(self) -> None:
        """Activates microphone and Wakeword detection."""
        if self._state == ComponentState.RUNNING:
            self._conversation.start_session()
            self._logger.info("Voice system is now listening.")

    def mute(self) -> None:
        """Stops microphone processing."""
        self._conversation.stop_session()
        self._logger.info("Voice system muted.")

    def unmute(self) -> None:
        """Resumes microphone processing."""
        self.listen()
        
    def interrupt(self) -> None:
        """Interrupts ongoing speech."""
        self._speaker.stop()
        if self._conversation.session:
            self._conversation.set_state(ConversationState.WAITING_FOR_WAKEWORD)

    async def speak(self, text: str) -> None:
        """Synthesizes text to speech and plays it."""
        if self._state != ComponentState.RUNNING:
            return
            
        self._conversation.set_state(ConversationState.RESPONDING)
        try:
            response = await self._tts.synthesize(text)
            self._publish_event("voice.response", {"text": text})
            await self._speaker.play(response.audio_data)
        except Exception as e:  # noqa: BLE001
            self._logger.error(f"Failed to speak: {e}")
        finally:
            self._conversation.set_state(ConversationState.WAITING_FOR_WAKEWORD)

    async def _on_wakeword(self, word: str) -> None:
        self._logger.info(f"Wake word detected: {word}")
        self._publish_event("voice.wakeword", {"word": word})

    async def _on_transcript(self, transcript: Transcript) -> None:
        self._logger.info(f"Transcript generated: {transcript.text}")
        self._publish_event("voice.transcript", {"text": transcript.text, "session_id": transcript.session_id.value})

    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)
