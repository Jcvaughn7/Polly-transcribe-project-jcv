import boto3
import os
import time
import uuid
import json

# Read environment variable or default to beta
environment = os.getenv("ENVIRONMENT", "beta")  # <-- move this to top
bucket_name = "mytranscribebucketjcv"
region = "us-east-1"
target_language_code = "es"
audio_input_folder = "./audio_inputs"

# AWS clients
s3 = boto3.client("s3", region_name=region)
transcribe = boto3.client("transcribe", region_name=region)
translate = boto3.client("translate", region_name=region)
polly = boto3.client("polly", region_name=region)

# Ensure audio_inputs folder exists and has files
if not os.path.exists(audio_input_folder):
    os.makedirs(audio_input_folder)
    print(f"📂 Created folder: {audio_input_folder}")
    print("❗ Add .mp3 files and rerun.")
    exit(1)

files = [f for f in os.listdir(audio_input_folder) if f.endswith(".mp3")]
if not files:
    print("❌ No .mp3 files found.")
    exit(1)

filename = files[0]
base_filename = filename.rsplit(".", 1)[0]
input_path = os.path.join(audio_input_folder, filename)
job_name = f"transcribe-job-{uuid.uuid4()}"

# Upload audio file to S3
s3_input_key = f"{environment}/audio_inputs/{filename}"
print(f"Uploading {input_path} to s3://{bucket_name}/{s3_input_key}")
s3.upload_file(input_path, bucket_name, s3_input_key)
s3_uri = f"s3://{bucket_name}/{s3_input_key}"

# Start transcription
print("⏳ Starting transcription job...")
transcript_json_key = f"{environment}/transcripts/{base_filename}.json"
transcribe.start_transcription_job(
    TranscriptionJobName=job_name,
    Media={"MediaFileUri": s3_uri},
    MediaFormat="mp3",
    LanguageCode="en-US",
    OutputBucketName=bucket_name,
    OutputKey=transcript_json_key,
)

# Wait for transcription to complete
while True:
    status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
    job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
    if job_status in ["COMPLETED", "FAILED"]:
        break
    print("⏳ Waiting for transcription...")
    time.sleep(10)

if job_status == "FAILED":
    print("❌ Transcription failed.")
    exit(1)

print("✅ Transcription completed")

# Download transcript JSON
local_json = f"/tmp/{base_filename}.json"
s3.download_file(bucket_name, transcript_json_key, local_json)

with open(local_json, "r") as f:
    transcript_data = json.load(f)

transcribed_text = transcript_data["results"]["transcripts"][0]["transcript"]

# Save transcript text locally and upload to S3
transcript_txt_key = f"{environment}/transcripts/{base_filename}.txt"
local_txt = f"/tmp/{base_filename}.txt"
with open(local_txt, "w") as f:
    f.write(transcribed_text)
s3.upload_file(local_txt, bucket_name, transcript_txt_key)
print(f"✅ Transcript uploaded to s3://{bucket_name}/{transcript_txt_key}")

# Translate text
translated = translate.translate_text(
    Text=transcribed_text,
    SourceLanguageCode="en",
    TargetLanguageCode=target_language_code,
)
translated_text = translated["TranslatedText"]

# Save translated text locally and upload to S3
translation_key = f"{environment}/translations/{base_filename}_{target_language_code}.txt"
local_translation = f"/tmp/{base_filename}_{target_language_code}.txt"
with open(local_translation, "w") as f:
    f.write(translated_text)
s3.upload_file(local_translation, bucket_name, translation_key)
print(f"✅ Translation uploaded to s3://{bucket_name}/{translation_key}")

# Convert translated text to speech
response = polly.synthesize_speech(
    Text=translated_text,
    OutputFormat="mp3",
    VoiceId="Lucia" if target_language_code == "es" else "Joanna",
    Engine="neural",
)

# Save synthesized speech locally
output_audio_filename = f"{base_filename}_{target_language_code}.mp3"
local_audio_path = f"/tmp/{output_audio_filename}"

if "AudioStream" in response:
    with open(local_audio_path, "wb") as f:
        f.write(response["AudioStream"].read())
    print(f"✅ Synthesized audio saved: {local_audio_path}")
else:
    print("Polly synthesis failed.")
    exit(1)

# Upload synthesized audio to S3
audio_key = f"{environment}/audio_outputs/{output_audio_filename}"
s3.upload_file(local_audio_path, bucket_name, audio_key)
print(f"✅ Audio uploaded to s3://{bucket_name}/{audio_key}")
