#!/usr/bin/env python3
"""Genera la voce intro di Eternal Fall via ElevenLabs, riusando key/voce del factory."""
import os, sys, base64
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

FACTORY_ENV = Path("/Users/gennaroferrara/explain/explain-factory/automations/python/.env")
OUT = Path("/Users/gennaroferrara/explain/caduta-eterna/assets/voice/intro.mp3")

load_dotenv(FACTORY_ENV)
api_key = os.environ.get("ELEVENLABS_API_KEY")
voice_id = os.environ.get("ELEVEN_VOICE_ID")
if not api_key or not voice_id:
    sys.exit("Chiave/voce mancanti nel .env del factory")

TEXT = ("This is Eternal Fall. Space Radio, still transmitting from the dark. "
        "A new chapter begins now... so let go, and fall with us.")

client = ElevenLabs(api_key=api_key)
settings = VoiceSettings(stability=0.42, similarity_boost=0.78, style=0.35,
                         use_speaker_boost=True, speed=0.98)
print("voce:", voice_id, "| genero intro...")
resp = client.text_to_speech.convert(
    voice_id=voice_id, model_id="eleven_multilingual_v2", text=TEXT,
    output_format="mp3_44100_128", voice_settings=settings,
)
data = resp if isinstance(resp, (bytes, bytearray)) else b"".join(c for c in resp if c)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(data)
print("scritto:", OUT, "(", len(data), "byte )")
