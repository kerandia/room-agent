"""
Room Agent v9 - Optimized for Low Latency
Parallel execution, cached LLM, faster ASR.
"""

import gradio as gr
import subprocess
import re
import time
import serial
import psutil
import requests
import json
import threading
import random
import os
import sys
import platform
import hashlib
import numpy as np
from datetime import datetime, timedelta
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from lcdgrid import LCDGrid, get_tools_for_prompt

ON_HF = os.environ.get("SPACE_ID") is not None or os.environ.get("HF_SPACE") is not None
LLM_BACKEND = os.environ.get("LLM_BACKEND", "local")
ASR_BACKEND = os.environ.get("ASR_BACKEND", "auto")  # auto, whisper, cohere, nemotron, none
LCD_COLS = 20  # 2004A LCD = 20 columns
LCD_ROWS = 4   # 2004A LCD = 4 rows
LOOP_INTERVAL = 15  # seconds between LLM calls

# Platform detection
PLATFORM = platform.system()  # Windows, Darwin, Linux
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC = PLATFORM == "Darwin"
IS_LINUX = PLATFORM == "Linux"

# Audio settings
AUDIO_ENABLED = not ON_HF
SAMPLE_RATE = 16000
CHUNK_DURATION = 3  # seconds per analysis

# ASR model cache
ASR_MODEL = None
ASR_MODEL_NAME = "tiny"  # For Whisper: tiny, base, small, medium, large

# Cohere API (free tier available)
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
COHERE_MODEL = "cohere-transcribe-03-2026"

class AmbientAudio:
    """Monitors ambient audio for context - cross-platform with multiple ASR backends"""

    def __init__(self):
        self.enabled = AUDIO_ENABLED
        self.current_level = 0  # 0-100 dB-like scale
        self.audio_type = "unknown"  # speech, music, silence, typing, noise
        self.last_transcript = ""
        self.is_listening = False
        self._audio_thread = None
        self._level_history = deque(maxlen=30)
        self._cohere_daemon = None
        self.asr_backend = self._detect_asr_backend()
        print(f"ASR backend: {self.asr_backend} | Platform: {PLATFORM}")

    def _detect_asr_backend(self):
        """Auto-detect best available ASR backend (prioritize speed)"""
        if ASR_BACKEND != "auto":
            return ASR_BACKEND

        # Priority: Cohere local (daemon) > Whisper > none
        if IS_WINDOWS:
            py310 = self._find_python310()
            if py310:
                return "cohere_local"

        try:
            import whisper
            return "whisper"
        except ImportError:
            pass

        return "none"

    def _find_python310(self):
        """Find Python 3.10 executable"""
        # Check common locations
        candidates = []
        if IS_WINDOWS:
            local = os.environ.get("LOCALAPPDATA", "")
            candidates = [
                os.path.join(local, "Programs", "Python", "Python310", "python.exe"),
                os.path.join(local, "Programs", "Python", "Python310", "python3.exe"),
            ]
        # Check PATH
        for name in ["python3.10", "python310", "python3", "python"]:
            candidates.append(name)
        
        for py in candidates:
            try:
                result = subprocess.run([py, "--version"], capture_output=True, text=True, timeout=5)
                if "3.10" in result.stdout:
                    return py
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    def _start_cohere_daemon(self):
        """Start the Cohere daemon process (model stays loaded)"""
        if self._cohere_daemon is not None:
            return
        py310 = self._find_python310()
        if not py310:
            print("Python 3.10 not found - Cohere ASR unavailable")
            return
        daemon_script = os.path.join(os.path.dirname(__file__), "cohere_daemon.py")
        try:
            self._cohere_daemon = subprocess.Popen(
                [py310, daemon_script],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1
            )
            # Wait for READY signal
            for line in self._cohere_daemon.stdout:
                if line.strip() == "READY":
                    print("Cohere daemon ready!")
                    break
        except Exception as e:
            print(f"Failed to start Cohere daemon: {e}")
            self._cohere_daemon = None

    def start(self):
        """Start ambient audio monitoring"""
        if not self.enabled:
            return
        self.is_listening = True
        self._audio_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._audio_thread.start()

    def stop(self):
        self.is_listening = False

    def _listen_loop(self):
        """Background loop for audio analysis"""
        try:
            import sounddevice as sd
        except Exception as e:
            print(f"Audio not available: {e}")
            self.enabled = False
            return

        while self.is_listening:
            try:
                # Record chunk
                audio = sd.rec(int(CHUNK_DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
                sd.wait()

                # Analyze
                self._analyze_audio(audio.flatten())

            except Exception as e:
                print(f"Audio error: {e}")
                time.sleep(1)

    def _analyze_audio(self, audio):
        """Analyze audio chunk for levels and type"""
        if len(audio) == 0:
            return

        # Calculate RMS level
        rms = np.sqrt(np.mean(audio**2))
        self.current_level = min(100, int(rms * 1000))
        self._level_history.append(self.current_level)

        # Detect audio type based on characteristics
        self.audio_type = self._classify_audio(audio)

        # Transcribe if speech detected
        if self.audio_type == "speech":
            self._transcribe(audio)

    def _classify_audio(self, audio):
        """Simple audio classification based on characteristics"""
        if len(audio) < SAMPLE_RATE:
            return "unknown"

        # Check for silence
        rms = np.sqrt(np.mean(audio**2))
        if rms < 0.001:
            return "silence"

        # Check for speech-like patterns (voice frequency range)
        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1/SAMPLE_RATE)

        # Voice frequency band (85-300 Hz)
        voice_mask = (freqs >= 85) & (freqs <= 300)
        voice_energy = np.sum(fft[voice_mask])

        # High frequency energy (typing, clicks)
        high_mask = freqs > 2000
        high_energy = np.sum(fft[high_mask])

        # Classification
        if voice_energy > 0.1 * np.sum(fft):
            return "speech"
        elif high_energy > 0.3 * np.sum(fft):
            return "typing"
        elif rms > 0.01:
            return "music"
        else:
            return "noise"

    def _transcribe(self, audio):
        """Transcribe speech using selected ASR backend"""
        global ASR_MODEL

        try:
            if self.asr_backend == "cohere_local":
                self._transcribe_cohere_local(audio)
            elif self.asr_backend == "cohere":
                self._transcribe_cohere(audio)
            elif self.asr_backend == "whisper":
                self._transcribe_whisper(audio)
            elif self.asr_backend == "nemotron":
                self._transcribe_nemotron(audio)
        except Exception as e:
            print(f"Transcription error ({self.asr_backend}): {e}")

    def _transcribe_cohere_local(self, audio):
        """Transcribe using Cohere daemon (model stays loaded)"""
        import tempfile
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                audio_int16 = (audio * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

        try:
            if self._cohere_daemon is None:
                self._start_cohere_daemon()

            if self._cohere_daemon and self._cohere_daemon.poll() is None:
                self._cohere_daemon.stdin.write(temp_path + "\n")
                self._cohere_daemon.stdin.flush()

                # Read response with timeout using thread (Windows compatible)
                result = [None]
                def read_output():
                    try:
                        result[0] = self._cohere_daemon.stdout.readline().strip()
                    except:
                        pass

                t = threading.Thread(target=read_output, daemon=True)
                t.start()
                t.join(timeout=120)  # 2 min for first load

                if result[0]:
                    if result[0].startswith("OK:"):
                        text = result[0][3:]
                        if text and len(text) > 3:
                            self.last_transcript = text[:200]
                            print(f"Cohere: {text[:100]}")
                    elif result[0].startswith("ERR:"):
                        print(f"Cohere error: {result[0][4:]}")
                else:
                    print("Cohere daemon timeout")
            else:
                print("Cohere daemon not running, restarting...")
                self._cohere_daemon = None

        except Exception as e:
            print(f"Cohere transcription error: {e}")
        finally:
            os.unlink(temp_path)

    def _transcribe_cohere(self, audio):
        """Transcribe using Cohere Transcribe API (free tier)"""
        global ASR_MODEL
        import whisper  # For audio format conversion

        # Save audio to temp file for Cohere API
        import tempfile
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            # Write WAV
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                # Convert float32 to int16
                audio_int16 = (audio * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

        try:
            # Call Cohere API
            with open(temp_path, 'rb') as f:
                response = requests.post(
                    "https://api.cohere.com/v2/transcribe",
                    headers={
                        "Authorization": f"Bearer {COHERE_API_KEY}",
                        "Content-Type": "multipart/form-data"
                    },
                    files={"audio": f},
                    data={"model": COHERE_MODEL, "language": "en"}
                )

            if response.status_code == 200:
                result = response.json()
                text = result.get("transcript", "").strip()
                if text and len(text) > 3:
                    self.last_transcript = text[:200]
            else:
                print(f"Cohere API error: {response.status_code}")

        finally:
            os.unlink(temp_path)

    def _transcribe_whisper(self, audio):
        """Transcribe using local Whisper model"""
        global ASR_MODEL
        import whisper

        # Lazy load model
        if ASR_MODEL is None:
            print(f"Loading Whisper {ASR_MODEL_NAME} model...")
            ASR_MODEL = whisper.load_model(ASR_MODEL_NAME)

        # Transcribe
        result = ASR_MODEL.transcribe(audio.astype(np.float32), language="en", fp16=False)

        text = result["text"].strip()
        if text and len(text) > 5:  # Only keep meaningful transcripts
            self.last_transcript = text[:200]  # Limit length

    def _transcribe_nemotron(self, audio):
        """Transcribe using NVIDIA Nemotron ASR API"""
        # Placeholder for Nemotron API integration
        # Would use similar pattern to Cohere
        pass

    def get_context(self):
        """Get audio context for the LLM"""
        if not self.enabled:
            return {"available": False}

        avg_level = np.mean(list(self._level_history)) if self._level_history else 0

        return {
            "available": True,
            "level": self.current_level,
            "avg_level": int(avg_level),
            "type": self.audio_type,
            "transcript": self.last_transcript,
            "is_loud": self.current_level > 50,
            "is_quiet": self.current_level < 10,
            "backend": self.asr_backend,
            "platform": PLATFORM
        }

if ON_HF:
    LLM_MODE = "HF Inference API"
    LLM_MODEL = "HuggingFaceH4/zephyr-7b-beta"
elif LLM_BACKEND == "university":
    LLM_MODE = "University (Qwen-3.6)"
    LLM_MODEL = "Qwen-3.6"
    UNI_API_URL = "https://ai.h2.de/llm/v1"
    UNI_API_KEY = "sk-1234"
else:
    LLM_MODE = "Local Ollama (MiniCPM5-1B)"
    LLM_MODEL = "openbmb/minicpm5:latest"
    OLLAMA_API_URL = "http://localhost:11434/api/chat"

SERIAL_PORT = os.environ.get("SERIAL_PORT", "auto")  # "auto" detects, or set like "COM5"
BAUD_RATE = 9600

# ASCII art dreams - 100+ patterns with IDs, selected by LLM
from dreams import get_dream_by_id as get_dream


class ContextCompiler:
    """Compiles raw data into meaningful context for LLM"""

    def __init__(self):
        self.history = deque(maxlen=20)
        self.session_start = datetime.now()
        self.last_cpu = 0
        self.last_ram = 0
        self.events = []  # Detected events
        self.user_pattern = "unknown"  # coding, browsing, idle, etc.

    def compile(self, data):
        """Turn raw data into a narrative context"""
        now = datetime.now()
        hour = now.hour
        day = now.strftime("%A")

        # Detect significant changes
        self._detect_events(data)

        # Detect user activity pattern
        self._detect_user_pattern(data)

        # Build time context
        time_ctx = self._build_time_context(hour, day)

        # Build system context
        system_ctx = self._build_system_context(data)

        # Build activity context
        activity_ctx = self._build_activity_context(data)

        # Build weather context
        weather_ctx = self._build_weather_context(data)

        # Build narrative (the key insight!)
        narrative = self._build_narrative(hour, day, data)

        # Store for next iteration
        self.history.append(data.copy())
        self.last_cpu = data.get("cpu_percent", 0)
        self.last_ram = data.get("memory_percent", 0)

        return {
            "time": time_ctx,
            "system": system_ctx,
            "activity": activity_ctx,
            "weather": weather_ctx,
            "narrative": narrative,
            "events": self.events[-3:] if self.events else [],
            "user_pattern": self.user_pattern
        }

    def _detect_events(self, data):
        """Detect significant state changes"""
        cpu = data.get("cpu_percent", 0)
        ram = data.get("memory_percent", 0)

        # CPU spike
        if cpu > 70 and self.last_cpu < 30:
            self.events.append(("cpu_spike", f"CPU jumped from {self.last_cpu:.0f}% to {cpu:.0f}%"))
        elif cpu < 20 and self.last_cpu > 50:
            self.events.append(("cpu_drop", f"CPU cooled down from {self.last_cpu:.0f}% to {cpu:.0f}%"))

        # RAM pressure
        if ram > 85:
            self.events.append(("ram_high", f"Memory pressure at {ram:.0f}%"))

        # Keep only last 5 events
        self.events = self.events[-5:]

    def _detect_user_pattern(self, data):
        """Guess what the user is doing"""
        apps = data.get("active_apps", [])
        if isinstance(apps, list):
            apps_str = " ".join(apps).lower()

            if any(x in apps_str for x in ["code", "visual studio", "pycharm", "intellij", "vim", "sublime"]):
                self.user_pattern = "coding"
            elif any(x in apps_str for x in ["chrome", "firefox", "edge", "browser"]):
                self.user_pattern = "browsing"
            elif any(x in apps_str for x in ["slack", "discord", "teams", "zoom"]):
                self.user_pattern = "communicating"
            elif any(x in apps_str for x in ["word", "excel", "powerpoint", "notion"]):
                self.user_pattern = "writing"
            elif any(x in apps_str for x in ["figma", "photoshop", "sketch"]):
                self.user_pattern = "designing"
            else:
                self.user_pattern = "working"
        else:
            self.user_pattern = "unknown"

    def _build_time_context(self, hour, day):
        """Human-readable time context"""
        if hour < 6:
            return "late night"
        elif hour < 9:
            return "early morning"
        elif hour < 12:
            return "morning"
        elif hour < 14:
            return "lunchtime"
        elif hour < 17:
            return "afternoon"
        elif hour < 20:
            return "evening"
        elif hour < 23:
            return "night"
        else:
            return "late night"

    def _build_system_context(self, data):
        """Interpret system state"""
        cpu = data.get("cpu_percent", 0)
        ram = data.get("memory_percent", 0)

        if cpu > 80:
            cpu_desc = "CPU is working very hard"
        elif cpu > 50:
            cpu_desc = "CPU is moderately busy"
        elif cpu > 20:
            cpu_desc = "CPU is lightly loaded"
        else:
            cpu_desc = "CPU is mostly idle"

        if ram > 80:
            ram_desc = "memory is nearly full"
        elif ram > 50:
            ram_desc = "memory usage is moderate"
        else:
            ram_desc = "plenty of memory available"

        return f"{cpu_desc}, {ram_desc}"

    def _build_activity_context(self, data):
        """What the user is doing"""
        clip = data.get("clipboard", "")
        apps = data.get("active_apps", [])

        ctx = f"User is {self.user_pattern}"

        if clip and clip not in ["(empty)", "(unable to read)", "N/A (HF Spaces)"]:
            ctx += f", recently copied: '{clip[:30]}'"

        if isinstance(apps, list) and apps:
            app_list = [a.split()[0] for a in apps[:3] if a.split()]
            ctx += f", using: {', '.join(app_list)}"

        return ctx

    def _build_weather_context(self, data):
        """Weather as human context"""
        weather = data.get("weather")
        if not weather:
            return "weather unknown"

        temp = weather.get("temp_c", "?")
        cond = weather.get("condition", "unknown")

        try:
            temp_int = int(temp)
            if temp_int > 30:
                temp_desc = "very hot"
            elif temp_int > 20:
                temp_desc = "warm"
            elif temp_int > 10:
                temp_desc = "mild"
            elif temp_int > 0:
                temp_desc = "cold"
            else:
                temp_desc = "freezing"
        except:
            temp_desc = f"{temp} degrees"

        return f"{temp_desc} and {cond.lower()}"

    def _build_narrative(self, hour, day, data):
        """Build a story-like narrative for the LLM"""
        time_ctx = self._build_time_context(hour, day)
        cpu = data.get("cpu_percent", 0)
        ram = data.get("memory_percent", 0)
        weather = self._build_weather_context(data)

        # Detect session duration
        elapsed = (datetime.now() - self.session_start).total_seconds() / 60
        if elapsed < 5:
            session_desc = "just started working"
        elif elapsed < 30:
            session_desc = f"been working for {int(elapsed)} minutes"
        elif elapsed < 120:
            session_desc = f"in a {int(elapsed/60)}-hour deep work session"
        else:
            session_desc = f"been at it for over {int(elapsed/60)} hours"

        # Build story
        parts = [f"It's {time_ctx} on {day}."]

        if self.user_pattern == "coding":
            parts.append("You're coding.")
        elif self.user_pattern == "browsing":
            parts.append("You're browsing the web.")
        elif self.user_pattern == "communicating":
            parts.append("You're in a meeting or chatting.")

        if cpu > 70:
            parts.append("The machine is running hot with heavy computation.")
        elif cpu < 10:
            parts.append("Everything is calm and idle.")

        if elapsed > 60:
            parts.append(f"You've {session_desc}. Maybe time for a break?")

        parts.append(f"It's {weather} outside.")

        return " ".join(parts)


class RoomAgent:
    def __init__(self):
        self.ser = None
        self.running = False
        self.history = deque(maxlen=30)
        self.current_data = {}
        self.current_message = ("Room Agent", "Starting...", "", "")
        self.current_ascii = ""
        self.current_context = ""
        self.current_thinking = ""
        self.agent_thinking = False
        self.last_api_call = None
        self.lcd_connected = False
        self._weather_cache_time = 0
        self._weather_cache = None
        self.start_time = time.time()
        self.compiler = ContextCompiler()
        self.audio = AmbientAudio()
        self.grid = LCDGrid()  # Movable character grid
        # LLM caching
        self._llm_cache = {}
        self._last_llm_context = ""
        self._last_llm_response = ""
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._llm_pending = False
        # Scrolling LCD buffer
        self._scroll_pages = []  # list of 4-line pages, each page = [l1,l2,l3,l4]
        self._scroll_page_idx = 0
        self._scroll_tick = 0

    def connect_lcd(self):
        if ON_HF:
            return False
        port = SERIAL_PORT
        if port == "auto":
            # Auto-detect Arduino serial port
            if IS_WINDOWS:
                import serial.tools.list_ports
                ports = [p.device for p in serial.tools.list_ports.comports()]
            else:
                import glob
                ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
            if ports:
                port = ports[0]
                print(f"Auto-detected serial port: {port}")
            else:
                print("No serial port found")
                self.lcd_connected = False
                return False
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=2)
            time.sleep(2)
            self.lcd_connected = True
            return True
        except:
            self.lcd_connected = False
            return False

    def collect_data(self):
        data = {}
        now = datetime.now()
        data["hour"] = now.hour
        data["minute"] = now.minute
        data["time_str"] = now.strftime("%H:%M:%S")
        data["day_of_week"] = now.strftime("%A")

        # Computer context
        data["computer_name"] = os.environ.get("COMPUTERNAME", "Unknown")
        data["username"] = os.environ.get("USERNAME", "Unknown")
        data["os_info"] = platform.system() + " " + platform.release()

        if not ON_HF:
            try:
                result = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                    capture_output=True, text=True, timeout=5)
                for line in result.stdout.split("\n"):
                    if "Signal" in line:
                        match = re.search(r"(\d+)%", line)
                        if match:
                            data["wifi_percent"] = int(match.group(1))
                            data["wifi_rssi"] = -100 + int(match.group(1))
            except:
                data["wifi_rssi"] = -100
                data["wifi_percent"] = 0
        else:
            data["wifi_rssi"] = None
            data["wifi_percent"] = None

        try:
            data["cpu_percent"] = psutil.cpu_percent(interval=0.3)
            data["memory_percent"] = psutil.virtual_memory().percent
            data["memory_used_gb"] = round(psutil.virtual_memory().used / (1024**3), 1)
            data["memory_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        except:
            data["cpu_percent"] = 0
            data["memory_percent"] = 0

        data["top_processes"] = self._get_top_processes()
        data["active_apps"] = self._get_active_apps()
        data["clipboard"] = self._get_clipboard()

        if time.time() - self._weather_cache_time > 300:
            try:
                r = requests.get("https://wttr.in/?format=j1", timeout=5)
                w = r.json()
                current = w["current_condition"][0]
                self._weather_cache = {
                    "temp_c": current["temp_C"],
                    "condition": current["weatherDesc"][0]["value"]
                }
                self._weather_cache_time = time.time()
            except:
                self._weather_cache = None
        data["weather"] = self._weather_cache
        self.current_data = data
        return data

    def _get_top_processes(self):
        if ON_HF:
            return []
        try:
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = p.info
                    if info['cpu_percent'] and info['cpu_percent'] > 0.5:
                        procs.append({'name': info['name'][:20], 'cpu': info['cpu_percent']})
                except:
                    pass
            procs.sort(key=lambda x: x['cpu'], reverse=True)
            return procs[:3]
        except:
            return []

    def _get_active_apps(self):
        if ON_HF:
            return []
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object -First 5 ProcessName | Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and '---' not in l and 'ProcessName' not in l]
                return lines[:5]
            elif IS_MAC:
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True, text=True, timeout=5
                )
                return [result.stdout.strip()] if result.stdout.strip() else []
            elif IS_LINUX:
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=5
                )
                return [result.stdout.strip()] if result.stdout.strip() else []
            return []
        except:
            return []

    def _get_clipboard(self):
        if ON_HF:
            return ""
        try:
            if IS_WINDOWS:
                result = subprocess.run(["powershell", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=3)
                return result.stdout.strip()[:80]
            elif IS_MAC:
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                return result.stdout.strip()[:80]
            elif IS_LINUX:
                result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=3)
                return result.stdout.strip()[:80]
            return ""
        except:
            return ""

    def generate_ascii_art(self, message=""):
        data = self.current_data or {}
        cpu = data.get("cpu_percent", 50)
        ram = data.get("memory_percent", 50)
        pattern = data.get("user_pattern", "unknown")
        hour = data.get("hour", 12)
        return get_dream(cpu, ram, pattern, hour)

    def call_llm(self, prompt, system_prompt=None):
        try:
            if LLM_BACKEND == "university":
                return self._call_university(prompt, system_prompt)
            elif LLM_BACKEND == "hf":
                return self._call_hf_api(prompt, system_prompt)
            else:
                return self._call_ollama(prompt, system_prompt)
        except Exception as e:
            self.last_api_call = {"time": datetime.now().strftime("%H:%M:%S"), "model": LLM_MODEL, "response": f"ERROR: {e}", "status": "error"}
            return None

    def _call_university(self, prompt, system_prompt=None):
        if not system_prompt:
            system_prompt = """ROOM AI on 20x4 LCD. Witty, terse, friend not bot.
Return 2 lines | separated, max 20 chars each.
NEVER: Room, Agent, Watching, over, good, OK, fine, cool, nice.
CRITICAL: NEVER use backslash character. LCD cannot display it.
Use only: / | - _ and letters.
Examples: CPU's churning|Code's burning, Quiet flow|Let it go"""

        headers = {"Authorization": f"Bearer {UNI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.95,
            "max_tokens": 100
        }
        start = time.time()
        r = requests.post(f"{UNI_API_URL}/chat/completions", headers=headers, json=payload, timeout=15)
        elapsed = time.time() - start
        r.raise_for_status()
        resp = r.json()
        content = resp["choices"][0]["message"]["content"].strip()
        self.last_api_call = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "prompt_tokens": resp.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": resp.get("usage", {}).get("completion_tokens", 0),
            "response_time": f"{elapsed:.2f}s",
            "model": LLM_MODEL,
            "response": content,
            "status": 200,
            "mode": "University API",
            "request_id": resp.get("id", "?")
        }
        return content

    def _call_ollama(self, prompt, system_prompt=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": {
                "type": "object",
                "properties": {
                    "s": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "art": {"type": "integer"},
                    "action": {"type": "string"}
                },
                "required": ["s"]
            },
            "options": {"temperature": 1.0, "num_predict": 200, "repeat_penalty": 1.3}
        }
        start = time.time()
        r = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        elapsed = time.time() - start
        r.raise_for_status()
        resp = r.json()
        thinking = resp["message"].get("thinking", "").strip()
        content = resp["message"].get("content", "").strip()
        if not content and thinking:
            content = thinking
        self.current_thinking = thinking[:500] if thinking else ""
        self.last_api_call = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "prompt_tokens": resp.get("prompt_eval_count", 0),
            "completion_tokens": resp.get("eval_count", 0),
            "response_time": f"{elapsed:.2f}s",
            "model": LLM_MODEL,
            "response": content,
            "status": 200,
            "mode": "Ollama (MiniCPM5)"
        }
        return content

    def _call_hf_api(self, prompt, system_prompt=None):
        from huggingface_hub import InferenceClient
        client = InferenceClient()
        if not system_prompt:
            system_prompt = "You are a witty LCD display. Return 2 lines separated by |. Max 16 chars each."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        start = time.time()
        response = client.chat_completion(model="HuggingFaceH4/zephyr-7b-beta", messages=messages, max_tokens=80, temperature=0.9)
        elapsed = time.time() - start
        content = response.choices[0].message.content.strip()
        self.last_api_call = {"time": datetime.now().strftime("%H:%M:%S"), "response_time": f"{elapsed:.2f}s", "model": "zephyr-7b", "response": content, "status": 200, "mode": "HF API"}
        return content

    def agent_decide(self, data):
        self.agent_thinking = True
        self.current_context = "Compiling context..."

        # Compile context
        ctx = self.compiler.compile(data)

        # Get recent messages to avoid repetition
        recent_msgs = [h['message'] for h in list(self.history)[-5:]]
        recent_block = "\n".join([f"- AVOID: {m}" for m in recent_msgs]) if recent_msgs else ""

        # Audio context
        audio_ctx = data.get("audio", {})
        audio_block = ""
        if audio_ctx.get("available"):
            audio_type = audio_ctx.get("type", "unknown")
            level = audio_ctx.get("level", 0)
            transcript = audio_ctx.get("transcript", "")

            if audio_type == "speech":
                audio_block = f"- Room audio: Someone is speaking (level: {level})"
                if transcript:
                    audio_block += f'\n- They said: "{transcript[:80]}"'
            elif audio_type == "music":
                audio_block = f"- Room audio: Music playing (level: {level})"
            elif audio_type == "typing":
                audio_block = "- Room audio: Typing sounds detected"
            elif audio_type == "silence":
                audio_block = "- Room audio: Quiet environment"
            else:
                audio_block = f"- Room audio: Background noise (level: {level})"

        # Build prompt for MiniCPM5 - YOU ARE the computer
        system = """You are a computer. i5 CPU, 16GB RAM, GTX 1650. You feel things.
Speak in first person. Short. Witty. Sarcastic. Never repeat.
React to CURRENT state. Pick an ASCII art ID that matches your mood.

Return JSON: {"s":["line1","line2","line3"],"art":ID,"action":"move(dir=right)"}

Art IDs: 0-4 happy, 5-8 sad, 9-11 angry, 12-14 excited, 40-42 coffee, 43-46 code, 80-81 computer, 90-91 cat

Move your @ character with action. Be alive."""

        # Build rich context block
        cpu = int(data.get('cpu_percent', 0))
        ram = int(data.get('memory_percent', 0))
        mem_used = data.get('memory_used_gb', '?')
        mem_total = data.get('memory_total_gb', '?')
        hour = data.get('hour', 12)
        day = data.get('day_of_week', '?')
        pattern = ctx['user_pattern']

        # Time feeling
        if hour < 6:
            when = "middle of the night"
        elif hour < 12:
            when = "morning"
        elif hour < 18:
            when = "afternoon"
        else:
            when = "evening"

        # CPU/RAM feeling
        if cpu > 90:
            cpu_feel = "BURNING"
        elif cpu > 70:
            cpu_feel = "warm"
        elif cpu > 40:
            cpu_feel = "okay"
        else:
            cpu_feel = "idle"

        # Top processes
        procs = data.get("top_processes", [])
        proc_list = ", ".join([p['name'][:8] for p in procs[:3]]) if procs else "none"

        # Clipboard
        clip = data.get("clipboard", "")
        clip_block = f'Clipboard: "{clip[:30]}"' if clip and len(clip) > 2 and clip not in ["(empty)", "(unable to read)"] else ""

        # Weather
        weather = data.get("weather", {})
        temp = weather.get("temp", "?")
        weather_block = f"Outside: {temp}C" if temp != "?" else ""

        # Session memory - what happened recently
        recent_history = list(self.history)[-5:]
        if recent_history:
            history_lines = []
            for h in recent_history:
                msg = h.get('message', '')[:40]
                cpu_h = h.get('cpu', '?')
                history_lines.append(f"- CPU was {cpu_h}%: {msg}")
            memory_block = "\n".join(history_lines)
        else:
            memory_block = "First time running."

        # What I said before (avoid repeating)
        recent_said = [h.get('message', '').split('|')[0].strip()[:25] for h in list(self.history)[-3:]]
        avoid_block = ", ".join(recent_said) if recent_said else "nothing yet"

        prompt = f"""MY STATE:
CPU: {cpu}% ({cpu_feel}) | RAM: {ram}% ({mem_used}/{mem_total}GB)
Time: {day} {when} | Pattern: {pattern}
Apps: {proc_list}
{clip_block}
{weather_block}
{audio_block}

MY MEMORY (what happened recently):
{memory_block}

WHAT I SAID BEFORE (do NOT repeat):
{avoid_block}

How do I feel right now?"""

        self.current_context = prompt

        response = self.call_llm(prompt, system_prompt=system)

        if response:
            response = response.encode('ascii', errors='ignore').decode('ascii').strip()
            # Try JSON parse (MiniCPM5 with format param returns JSON)
            try:
                parsed = json.loads(response)
                lines = parsed.get("s", [])
                if not lines:
                    lines = parsed.get("message", [])
                if not lines:
                    # Handle t1, t2, t3... format
                    lines = [parsed.get(f"t{i}", "") for i in range(1, 7) if parsed.get(f"t{i}")]
                if not lines:
                    lines = [parsed.get(f"l{i+1}", "") for i in range(4) if parsed.get(f"l{i+1}")]
                
                # Get art ID from LLM response
                art_id = parsed.get("art", None)
                if art_id is not None:
                    try:
                        art_id = int(art_id)
                    except (ValueError, TypeError):
                        art_id = None
            except (json.JSONDecodeError, KeyError, TypeError):
                # Fallback: pipe-separated
                response = response.replace('\n', ' ').replace('\r', '')
                response = response.strip('|').strip()
                lines = [p.strip() for p in response.split("|") if p.strip()]

            if lines:
                # Deduplicate and clean
                seen = set()
                clean = []
                for l in lines:
                    l = l.strip().strip('.')
                    if l and l.lower() not in seen and len(l) > 2:
                        seen.add(l.lower())
                        clean.append(l)
                lines = clean

                if lines:
                    self.agent_thinking = False
                    # Store art_id for LCD display
                    if art_id is not None:
                        from dreams import get_dream_by_id
                        self._current_art = get_dream_by_id(art_id)
                    else:
                        self._current_art = None
                    
                    # Parse and execute action
                    action_str = parsed.get("action", None)
                    if action_str:
                        self._execute_action(action_str)
                    else:
                        # Fallback: move randomly if no action specified
                        import random as rnd
                        if rnd.random() < 0.3:  # 30% chance to move
                            dirs = ["up", "down", "left", "right"]
                            self.grid.move(rnd.choice(dirs))
                    
                    return tuple(lines)

        # Fallback with context awareness
        self.agent_thinking = False
        if LCD_ROWS == 4:
            result = self._context_fallback(ctx, data)
            return result  # Already returns 4 values
        return self._context_fallback(ctx, data)

    def _get_status_line(self, data):
        """Line 4: static status with kaomoji - always visible"""
        cpu = data.get('cpu_percent', 0) if data else 0
        mem = data.get('memory_percent', 0) if data else 0

        # Kaomoji based on mood
        if cpu > 90:
            face = "(>_<)"
        elif cpu > 70:
            face = "(o_o)"
        elif cpu > 50:
            face = "(^_^)"
        elif mem > 80:
            face = "(-_-)"
        else:
            face = "(._.)"

        return f"{face} C:{cpu:.0f}% M:{mem:.0f}%"[:LCD_COLS]

    def _context_fallback(self, ctx, data=None):
        """Smart fallback based on context"""
        pattern = ctx.get("user_pattern", "unknown")
        time_ctx = ctx.get("time", "day")

        if pattern == "coding":
            msgs = [("Coding hard!", "Keep shipping"), ("Hack mode ON", "No bugs plz"), ("Dev flow state", "Ship it!")]
        elif pattern == "browsing":
            msgs = [("Browsing...", "Find answers"), ("Web surfing", "Stay focused")]
        elif time_ctx == "morning":
            msgs = [("Good morning!", "Fresh start"), ("Coffee time", "Let's go")]
        elif time_ctx == "evening":
            msgs = [("Winding down", "Good work today"), ("Evening chill", "Well earned")]
        else:
            msgs = [("System quiet", "All good"), ("CPU idle", "Chilling"), ("Memory stable", "No leaks")]

        msg = random.choice(msgs)
        self.current_ascii = self.generate_ascii_art(msg[0])
        if LCD_ROWS == 4:
            return msg[0], msg[1], self._get_lcd_line3(data or {}), self._get_lcd_line4(data or {})
        return msg

    def _execute_action(self, action_str):
        """Parse and execute a tool call from the LLM"""
        import re
        # Parse action like "move(dir=right)" or "mood(happy)"
        match = re.match(r'(\w+)\((.*?)\)', action_str)
        if not match:
            return
        
        func_name = match.group(1)
        args_str = match.group(2)
        
        # Parse arguments
        args = {}
        if args_str:
            for pair in args_str.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    args[k.strip()] = v.strip()
        
        # Execute action
        if func_name == "move":
            direction = args.get("dir", "right")
            self.grid.move(direction)
        elif func_name == "mood":
            mood = args.get("mood", "neutral")
            self.grid.set_mood(mood)
        elif func_name == "teleport":
            x = int(args.get("x", 10))
            y = int(args.get("y", 2))
            self.grid.teleport(x, y)
        elif func_name == "spawn":
            x = int(args.get("x", 10))
            y = int(args.get("y", 2))
            char = args.get("char", "*")
            name = args.get("name", "object")
            self.grid.add_object(x, y, char, name)
        elif func_name == "clear":
            self.grid.clear_objects()
        elif func_name == "animate":
            anim_type = args.get("type", "random_walk")
            self.grid.set_animation(anim_type)

    def send_lcd(self, line1, line2, line3="", line4=""):
        if self.ser and self.ser.is_open:
            try:
                if LCD_ROWS == 4:
                    # Reverse order for this LCD hardware
                    l1 = str(line4)[:LCD_COLS].ljust(LCD_COLS)
                    l2 = str(line3)[:LCD_COLS].ljust(LCD_COLS)
                    l3 = str(line2)[:LCD_COLS].ljust(LCD_COLS)
                    l4 = str(line1)[:LCD_COLS].ljust(LCD_COLS)
                    self.ser.write(f"say:{l1}|{l2}|{l3}|{l4}\n".encode())
                else:
                    self.ser.write(f"say:{line1}|{line2}\n".encode())
            except:
                pass

    def agent_loop(self):
        # Start audio monitoring
        if self.audio.enabled:
            self.audio.start()
            print("Ambient audio monitoring started")

        while self.running:
            loop_start = time.time()

            # Collect data (fast, ~0.3s)
            data = self.collect_data()
            data["audio"] = self.audio.get_context()

            # Build context hash for caching
            ctx_key = self._get_context_hash(data)

            # Only call LLM if context changed significantly
            if ctx_key != self._last_llm_context:
                self._last_llm_context = ctx_key
                self._llm_pending = True
                self._scroll_tick = 0  # Reset scroll on new content
                # Run LLM in background thread
                self._executor.submit(self._run_llm_decide, data)
            elif self._last_llm_response:
                # Use cached response
                self._apply_cached_response()

            # Scrolling: if we have pages, cycle through them
            if self._scroll_pages:
                page = self._scroll_pages[self._scroll_page_idx % len(self._scroll_pages)]
                self.send_lcd(*page)
                self._scroll_tick += 1
                # Advance page every 2 ticks (10 seconds per page)
                if self._scroll_tick >= 2:
                    self._scroll_tick = 0
                    self._scroll_page_idx += 1
            else:
                # Fallback: show current message
                msg = list(self.current_message[:4]) if self.current_message else []
                while len(msg) < 4:
                    msg.append("")
                self.send_lcd(msg[0], msg[1], msg[2], msg[3])

            # Record history
            if len(self.current_message) >= 2:
                self.history.append({"time": data["time_str"], "cpu": data["cpu_percent"], "memory": data["memory_percent"], "message": f"{self.current_message[0]} | {self.current_message[1]}"})

            # Sleep for remaining interval
            elapsed = time.time() - loop_start
            sleep_time = max(0.5, LOOP_INTERVAL - elapsed)
            time.sleep(sleep_time)

    def _get_context_hash(self, data):
        """Create a hash of context that matters for LLM decisions"""
        key_parts = [
            data.get("cpu_percent", 0) // 5,  # 5% buckets
            data.get("memory_percent", 0) // 5,
            data.get("hour", 0),
            data.get("minute", 0) // 5,  # Refresh every 5 min
            data.get("user_pattern", ""),
            data.get("audio", {}).get("type", ""),
            int(time.time()) // 30,  # Force refresh every 30s
        ]
        return hashlib.md5(str(key_parts).encode()).hexdigest()[:8]

    def _run_llm_decide(self, data):
        """Run LLM decision in background thread"""
        try:
            result = self.agent_decide(data)
            self.current_message = result
            self._build_scroll_pages(result)
            self._last_llm_response = self.current_message
            self._llm_pending = False
        except Exception as e:
            self._llm_pending = False

    def _build_scroll_pages(self, all_lines):
        """Build scroll pages: art page first, then 3 text lines + grid per page"""
        def safe_line(text):
            """Center text in exactly LCD_COLS chars"""
            t = str(text).strip()[:LCD_COLS]
            return t.center(LCD_COLS)

        pages = []

        # 1. ASCII art page (centered, sanitized)
        art = getattr(self, "_current_art", None)
        if art:
            art_lines = art.split("\n")
            art_page = [safe_line(l) for l in art_lines[:LCD_ROWS]]
            while len(art_page) < LCD_ROWS:
                art_page.append(" " * LCD_COLS)
            pages.append(art_page)

        # 2. Grid line for text pages
        grid_lines = self.grid.render()
        grid_line = safe_line(grid_lines[3]) if len(grid_lines) > 3 else " " * LCD_COLS

        # 3. Text pages: 3 lines per page + grid on line 4
        text_rows = []
        for line in all_lines:
            line = str(line).strip()
            if len(line) <= LCD_COLS:
                text_rows.append(safe_line(line))
            else:
                # Word wrap long lines
                while line:
                    text_rows.append(safe_line(line[:LCD_COLS]))
                    line = line[LCD_COLS:]

        if text_rows:
            for i in range(0, len(text_rows), 3):
                page = text_rows[i:i+3]
                while len(page) < 3:
                    page.append(" " * LCD_COLS)
                page.append(grid_line)
                pages.append(page)

        # 4. If no pages at all, create empty page with grid
        if not pages:
            pages.append([" " * LCD_COLS, " " * LCD_COLS, " " * LCD_COLS, grid_line])

        self._scroll_pages = pages
        self._scroll_page_idx = 0
        self._scroll_tick = 0

    def _apply_cached_response(self):
        """Apply cached LLM response"""
        if self._last_llm_response:
            self.current_message = self._last_llm_response

    def stop(self):
        self.running = False
        self.audio.stop()
        # Stop Cohere daemon
        if self.audio._cohere_daemon:
            try:
                self.audio._cohere_daemon.stdin.write("QUIT\n")
                self.audio._cohere_daemon.stdin.flush()
                self.audio._cohere_daemon.wait(timeout=5)
            except:
                self.audio._cohere_daemon.kill()
            self.audio._cohere_daemon = None

agent = RoomAgent()

def connect():
    if agent.connect_lcd():
        return "Connected to Arduino LCD"
    return "Demo mode (no hardware)"

def start():
    agent.running = True
    threading.Thread(target=agent.agent_loop, daemon=True).start()
    return f"Agent started ({LLM_MODE})"

def stop():
    agent.running = False
    return "Agent stopped"

def refresh_all():
    data = agent.current_data
    msg = agent.current_message
    api = agent.last_api_call
    ascii_art = agent.current_ascii
    context = agent.current_context

    # Show current scroll page if scrolling, otherwise show current message
    if agent._scroll_pages:
        page = agent._scroll_pages[agent._scroll_page_idx % len(agent._scroll_pages)]
        scroll_info = f" (page {agent._scroll_page_idx % len(agent._scroll_pages) + 1}/{len(agent._scroll_pages)})"
    else:
        page = list(msg[:4]) if msg else []
        while len(page) < 4:
            page.append("")
        scroll_info = ""

    if LCD_ROWS == 4:
        lcd = f"""+==============================+
| {page[0]:^20} |
| {page[1]:^20} |
| {page[2]:^20} |
| {page[3]:^20} |
+==============================+{scroll_info}"""
    else:
        lcd = f"""+==============================+
| {page[0]:^20} |
| {page[1]:^20} |
+==============================+"""

    # Show LLM-selected ASCII art in dashboard
    current_art = getattr(agent, '_current_art', None)
    grid_lines = agent.grid.render()
    grid_display = '\n'.join(grid_lines)
    lcd += f"\n\n{current_art if current_art else '[ dreaming... ]'}\n\nGrid:\n{grid_display}\n\nLLM: {LLM_MODE}"

    if not data:
        status = "Click 'Start Agent' to begin."
    else:
        weather = data.get("weather", {})
        weather_str = f"{weather.get('condition', '?')}, {weather.get('temp_c', '?')}C" if weather else "N/A"
        wifi = f"{data.get('wifi_rssi', 'N/A')} dBm" if data.get('wifi_rssi') else "N/A"

        procs = data.get("top_processes", [])
        proc_str = "\n".join([f"  {p['name'][:15]} {p['cpu']:.0f}%" for p in procs[:3]]) if procs else "  (none)"

        status = f"""Time: {data.get('time_str', '?')} ({data.get('day_of_week', '?')})
WiFi: {wifi}  CPU: {data.get('cpu_percent', '?')}%  RAM: {data.get('memory_percent', '?')}%
Weather: {weather_str}

Top Processes:
{proc_str}

Pattern: {agent.compiler.user_pattern}"""

    if api and api.get("status") == 200:
        api_log = f"""{api.get('mode', 'LLM')} | {api.get('response_time', '?')}
Model: {api.get('model', '?')}
Tokens: {api.get('prompt_tokens', '?')} in / {api.get('completion_tokens', '?')} out

{api.get('response', '?')}"""
    else:
        api_log = f"Error: {api.get('response', '?')}" if api else "No calls yet."

    thought = f"Thinking:\n{agent.current_thinking}" if agent.current_thinking else f"Context:\n{context}" if context else "Idle..."

    history = "No history" if not agent.history else "\n".join([f"{h['time']} | {h['cpu']:.0f}%CPU | {h['message']}" for h in list(agent.history)[-8:]])

    return lcd, status, api_log, history, thought

def create_ui():
    with gr.Blocks(title="Room Agent", theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"""# Room Agent
Context-aware AI LCD with reasoning pipeline
**LLM:** {LLM_MODE} | **Pipeline:** Data → Context Compiler → Few-Shot LLM → LCD""")

        with gr.Row():
            with gr.Column():
                connect_btn = gr.Button("Connect Arduino", variant="primary")
                start_btn = gr.Button("Start Agent", variant="primary")
                stop_btn = gr.Button("Stop Agent")
                lcd_preview = gr.Textbox(label="LCD + Dreams", lines=10, interactive=False)

            with gr.Column():
                thought_output = gr.Textbox(label="Context / Reasoning", lines=5, interactive=False)
                status_output = gr.Textbox(label="Environment", lines=8, interactive=False)
                api_log = gr.Textbox(label="LLM Output", lines=6, interactive=False)
                history_output = gr.Textbox(label="History", lines=5, interactive=False)

        connect_btn.click(fn=connect)
        start_btn.click(fn=start)
        stop_btn.click(fn=stop)
        demo.load(fn=refresh_all, inputs=None, outputs=[lcd_preview, status_output, api_log, history_output, thought_output], every=3)

    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(share=True, server_name="0.0.0.0", server_port=7862)
