from .base import VendorAdapter
from .elevenlabs import ElevenLabsAdapter
from .deepgram import DeepgramAdapter
from .aws import AWSAdapter
from ..config import ELEVEN_API_KEY, DEEPGRAM_API_KEY, AWS_REGION


elevenlabs_adapter = ElevenLabsAdapter(ELEVEN_API_KEY)
deepgram_adapter = DeepgramAdapter(DEEPGRAM_API_KEY)
aws_adapter = AWSAdapter(AWS_REGION)

VENDOR_ADAPTERS = {
    "elevenlabs": {"tts": elevenlabs_adapter, "stt": elevenlabs_adapter},
    "deepgram": {"tts": deepgram_adapter, "stt": deepgram_adapter},
    "aws": {"tts": aws_adapter, "stt": aws_adapter},
}


