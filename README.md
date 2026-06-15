---
title: Joe
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
license: mit
---

# Joe

A self-aware AI personality living on a 20x4 LCD screen. Joe monitors your computer's CPU, RAM, WiFi, clipboard, active apps, ambient audio, and weather — then reasons about how it feels using a local LLM (MiniCPM5-1B via Ollama) and displays context-aware messages on a physical LCD.

## Features
- **Real-time monitoring**: CPU, RAM, WiFi signal, clipboard, active apps, ambient audio
- **Context Compiler**: pattern detection, state tracking, event detection
- **Local LLM**: MiniCPM5-1B via Ollama (primary) or HF Inference API (fallback)
- **ASCII Art Dreams**: 100+ LCD-optimized patterns with IDs 0-99
- **Grid System**: movable `@` character on 20x4 grid with mood faces
- **Gradio Dashboard**: real-time monitoring, API logs, history

## Hardware (optional)
- Arduino Uno + 20x4 I2C LCD (2004A)
- Works without hardware in demo mode

## Setup (local)
```bash
pip install -r requirements.txt
# Install Ollama and pull MiniCPM5-1B
ollama pull openbmb/minicpm5:latest
python app.py
```

## HF Spaces (live demo)
This Space runs **MiniCPM5-1B** directly via HuggingFace transformers — same model as local.
- **First load**: ~30-60s (downloads ~1GB model weights)
- **Inference**: ~2-5s per response on CPU
- **No Ollama needed**: model loads into memory on startup
- **Fallback**: if transformers fails, falls back to HF Inference API (zephyr-7b)

## HF Build Small Hackathon
This project was built for the [HF Build Small Hackathon](https://huggingface.co/build/small). All models used are ≤32B parameters.
- **Primary model**: MiniCPM5-1B (1.08B params, Apache-2.0)
- **Fallback model**: zephyr-7b-beta (7B params, MIT)
