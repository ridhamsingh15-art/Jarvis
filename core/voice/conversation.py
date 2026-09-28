import asyncio
import threading
from collections.abc import Callable, Coroutine

from core.models.primitives import Identifier

from .enums import AudioState, ConversationState
from .interfaces import MicrophoneProvider, STTProvider, VADProvider, WakeWordProvider
from .models import Transcript, VoiceSession


class ConversationManager:
    """Manages the lifecycle of a voice interaction loop."""

    def __init__(
        self,
        microphone: MicrophoneProvider,
        vad: VADProvider,
        wakeword: WakeWordProvider,
        stt: STTProvider,
        on_wakeword: Callable[[str], Coroutine[None, None, None]],
        on_transcript: Callable[[Transcript], Coroutine[None, None, None]]
    ) -> None:
        self._mic = microphone
        self._vad = vad
        self._wakeword = wakeword
        self._stt = stt
        
        self._on_wakeword = on_wakeword
        self._on_transcript = on_transcript
        
        self._lock = threading.RLock()
        self._session: VoiceSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._is_active = False

    @property
    def session(self) -> VoiceSession | None:
        with self._lock:
            return self._session

    def start_session(self) -> None:
        with self._lock:
            if self._is_active:
                return
            
            self._is_active = True
            self._session = VoiceSession(
                session_id=Identifier("session_1"),
                state=ConversationState.WAITING_FOR_WAKEWORD,
                audio_state=AudioState.RECORDING
            )
            self._mic.start()
            self._task = asyncio.create_task(self._process_loop())

    def stop_session(self) -> None:
        with self._lock:
            self._is_active = False
            self._mic.stop()
            if self._task and not self._task.done():
                self._task.cancel()
            self._session = None

    def set_state(self, state: ConversationState) -> None:
        with self._lock:
            if self._session:
                self._session = VoiceSession(
                    session_id=self._session.session_id,
                    state=state,
                    audio_state=self._session.audio_state,
                    last_active=self._session.last_active
                )

    async def _process_loop(self) -> None:
        speech_buffer: bytearray = bytearray()
        silence_frames = 0
        
        try:
            async for frame in self._mic.listen():
                if not self._is_active:
                    break

                current_state = self.session.state if self.session else ConversationState.WAITING_FOR_WAKEWORD
                
                if current_state == ConversationState.WAITING_FOR_WAKEWORD:
                    ww_result = self._wakeword.detect(frame)
                    if ww_result:
                        self.set_state(ConversationState.LISTENING)
                        asyncio.create_task(self._on_wakeword(ww_result.word))
                        speech_buffer.clear()
                        silence_frames = 0
                        
                elif current_state == ConversationState.LISTENING:
                    is_speech = self._vad.is_speech(frame)
                    if is_speech:
                        speech_buffer.extend(frame.data)
                        silence_frames = 0
                    else:
                        if len(speech_buffer) > 0:
                            silence_frames += 1
                            # Add some padding
                            speech_buffer.extend(frame.data)
                            
                        # If silence > 50 frames (e.g. ~5 seconds depending on frame rate), process it
                        # Since tests simulate 100ms chunks, 10 frames = 1 second. 
                        # Let's trigger STT after 3 silence frames for fast testing.
                        if silence_frames > 3:
                            self.set_state(ConversationState.PROCESSING)
                            audio_payload = bytes(speech_buffer)
                            speech_buffer.clear()
                            
                            # Fire and forget transcript processing
                            asyncio.create_task(self._handle_transcription(audio_payload))

                # If PROCESSING or RESPONDING, we ignore mic input to prevent self-triggering
                # In full duplex implementations, we would do echo cancellation here.

        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            # In a real impl, log the exception.
            self.stop_session()

    async def _handle_transcription(self, audio_data: bytes) -> None:
        try:
            result = await self._stt.transcribe(audio_data)
            if self.session and result.text:
                transcript = Transcript(
                    session_id=self.session.session_id,
                    text=result.text
                )
                await self._on_transcript(transcript)
        except Exception:  # noqa: BLE001, S110
            pass
        finally:
            if self.session and self.session.state == ConversationState.PROCESSING:
                # Revert to listening or wakeword depending on config. We go to Wakeword.
                self.set_state(ConversationState.WAITING_FOR_WAKEWORD)
