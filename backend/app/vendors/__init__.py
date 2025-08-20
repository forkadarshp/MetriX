from .base import VendorAdapter
from .elevenlabs import ElevenLabsAdapter
from .deepgram import DeepgramAdapter
from .aws import AWSAdapter
from .azure_openai import AzureOpenAIAdapter
from ..config import ELEVEN_API_KEY, DEEPGRAM_API_KEY, AWS_REGION, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_STT_MODEL


elevenlabs_adapter = ElevenLabsAdapter(ELEVEN_API_KEY)
deepgram_adapter = DeepgramAdapter(DEEPGRAM_API_KEY)
aws_adapter = AWSAdapter(AWS_REGION)
azure_openai_adapter = AzureOpenAIAdapter(AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_STT_MODEL)

VENDOR_ADAPTERS = {
    "elevenlabs": {"tts": elevenlabs_adapter, "stt": elevenlabs_adapter},
    "deepgram": {"tts": deepgram_adapter, "stt": deepgram_adapter},
    "aws": {"tts": aws_adapter, "stt": aws_adapter},
    "azure_openai": {"tts": azure_openai_adapter, "stt": azure_openai_adapter},
}


