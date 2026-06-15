"""
Cohere Transcribe Daemon - keeps model loaded in memory
Run once, communicate via stdin/stdout
"""
import sys
import warnings
warnings.filterwarnings("ignore")

print("Loading Cohere Transcribe model...", file=sys.stderr)
from transformers import AutoProcessor, CohereAsrForConditionalGeneration
from transformers.audio_utils import load_audio

processor = AutoProcessor.from_pretrained("CohereLabs/cohere-transcribe-03-2026")
model = CohereAsrForConditionalGeneration.from_pretrained("CohereLabs/cohere-transcribe-03-2026", device_map="cpu")
print("Model loaded. Ready for transcription.", file=sys.stderr)

# Signal ready
print("READY", flush=True)

for line in sys.stdin:
    wav_path = line.strip()
    if wav_path == "QUIT":
        break
    if not wav_path:
        continue
    try:
        audio = load_audio(wav_path, sampling_rate=16000)
        inputs = processor(audio, sampling_rate=16000, return_tensors="pt", language="en")
        inputs.to(model.device, dtype=model.dtype)
        outputs = model.generate(**inputs, max_new_tokens=256)
        text = processor.decode(outputs, skip_special_tokens=True)
        print(f"OK:{text}", flush=True)
    except Exception as e:
        print(f"ERR:{e}", flush=True)
