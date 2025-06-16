# Polly Transcribe Project

This project uploads an MP3 to S3, transcribes it with Amazon Transcribe, translates it using Amazon Translate, and converts it back to speech with Amazon Polly.

### Run Instructions
- Place MP3 files in `/audio_inputs/`
- Run: `python process_audio.py`
