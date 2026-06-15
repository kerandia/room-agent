---
title: Joe
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.17.3
python_version: "3.12"
app_file: app.py
pinned: true
license: mit
short_description: A dramatic AI personality living on a 20x4 LCD screen
tags:
- gradio
- build-small-hackathon
- track:wood
- achievement:offgrid
- badge-tiny-titan
- arduino
- lcd
- local-llm
- minicpm
- cohere
- whisper
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
- **Track**: Thousand Token Wood (whimsical / entertainment) — `track:wood`
- **Achievements claimed**: Off-Grid (`achievement:offgrid`, runs a fully local LLM, no cloud API) · Tiny Titan (`badge-tiny-titan`, 1.08B model)
- **Primary LLM**: MiniCPM5-1B (1.08B params, Apache-2.0)
- **Fallback LLM**: zephyr-7b-beta (7B params, MIT)
- **Speech-to-text**: Cohere Transcribe 03 (~2B params, runs in a persistent daemon) with Whisper-tiny fallback

All models run individually well under the 32B cap.

### Submission links
- **Demo video**: https://youtu.be/eBcLilTYz9Y
- **Social post**: https://x.com/ssaacar/status/2066630310410829835
