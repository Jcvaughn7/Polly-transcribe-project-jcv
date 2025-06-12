import boto3
import os
import time
import uuid
import json
import sys

print(f"ENVIRONMENT argument received: {env}")
print(f"Using environment variable: {environment}")


# ✅ Correct environment setup
environment = sys.argv[1] if len(sys.argv) > 1 else "beta"
print(f"Running with environment: {environment}")
s3_output_prefix = f"{environment}/"

bucket_name = "mytranscribebucketjcv"
region = "us-east-1"
target_language_code = "es"
audio_input_folder = os.path.join(os.getcwd(), "audio_inputs")




#  Clients
s3 = boto3.client("s3", region_name=region)
transcribe = boto3.client("transcribe", region_name=region)
translate = boto3.client("translate", region_name=region)
polly = boto3.client("polly", region_name=region)

#  Verify audio_inputs/ exists
if not os.path.exists(audio_input_folder):
    os.makedirs(audio_input_folder)
    print(f"Created folder: {audio_input_folder}")
    print("Add .mp3 files and rerun.")
    exit(1)

# Load first MP3 file 
files = [f for f in os.listdir(audio_input_folder) if f.endswith(".mp3")]
if not files:
    print("No .mp3 files found.")
    exit(1)

filename = files[0]
base_filename = filename.replace(".mp3", "")
input_path = os.path.join(audio_input_folder, filename)
job_name = f"transcribe-job-{uuid.uuid4()}"

#  Upload input audio to S3 
s3_input_key = f"{environment}/audio_inputs/{filename}"
s3.upload_file(input_path, bucket_name, s3_input_key)
s3_uri = f"s3://{bucket_name}/{s3_input_key}"
print(f"Uploaded input: {s3_uri}")

# Start Transcription Job 
print("Starting transcription...")
transcript_json_key = f"{environment}/transcripts/{base_filename}.json"
transcribe.start_transcription_job(
    TranscriptionJobName=job_name,
    Media={"MediaFileUri": s3_uri},
    MediaFormat="mp3",
    LanguageCode="en-US",
    OutputBucketName=bucket_name,
    OutputKey=transcript_json_key
)

 # Transcribing
while True:
    status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
    job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
    if job_status in ["COMPLETED", "FAILED"]:
        break
    print("Please Wait")
    time.sleep(10)

if job_status == "FAILED":
    print(" Transcription failed.")
    exit(1)

print(" Transcription completed")

# Download and parse transcript JSON 
local_json = f"/tmp/{base_filename}.json"
s3.download_file(bucket_name, transcript_json_key, local_json)

with open(local_json, "r") as f:
    transcript_data = json.load(f)

transcribed_text = transcript_data["results"]["transcripts"][0]["transcript"]

# Save plain text transcript 
transcript_txt_key = f"{environment}/transcripts/{base_filename}.txt"
local_txt = f"/tmp/{base_filename}.txt"
with open(local_txt, "w") as f:
    f.write(transcribed_text)
s3.upload_file(local_txt, bucket_name, transcript_txt_key)
print(f" Transcript uploaded to: s3://{bucket_name}/{transcript_txt_key}")

# Translate 
translated = translate.translate_text(
    Text=transcribed_text,
    SourceLanguageCode="en",
    TargetLanguageCode=target_language_code
)
translated_text = translated["TranslatedText"]

# Save translated text 
translation_key = f"{environment}/translations/{base_filename}_{target_language_code}.txt"
local_translation = f"/tmp/{base_filename}_{target_language_code}.txt"
with open(local_translation, "w") as f:
    f.write(translated_text)
s3.upload_file(local_translation, bucket_name, translation_key)
print(f"Translation uploaded: s3://{bucket_name}/{translation_key}")

# Convert translated text to speech
response = polly.synthesize_speech(
    Text=translated_text,
    OutputFormat="mp3",
    VoiceId="Lucia" if target_language_code == "es" else "Joanna",
    Engine="neural"
)

# save synthesized audio
output_audio_filename = f"{base_filename}_{target_language_code}.mp3"
local_audio_path = f"/tmp/{output_audio_filename}"

if "AudioStream" in response:
    with open(local_audio_path, "wb") as f:
        f.write(response["AudioStream"].read())
    print(f"Synthesized audio saved: {local_audio_path}")
else:
    print("Polly synthesis failed.")
    exit(1)

# Upload final audio to S3 
audio_key = f"{environment}/audio_outputs/{output_audio_filename}"
s3.upload_file(local_audio_path, bucket_name, audio_key)
print(f"Audio uploaded: s3://{bucket_name}/{audio_key}")

environment = os.getenv("ENVIRONMENT", "beta")  # Default to beta if not set up

