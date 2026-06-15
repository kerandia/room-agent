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

## Setup
```bash
pip install -r requirements.txt
# Install Ollama and pull MiniCPM5-1B
ollama pull openbmb/minicpm5:latest
python app.py
```

## HF Build Small Hackathon
This project was built for the [HF Build Small Hackathon](https://huggingface.co/build/small). All models used are ≤32B parameters.
