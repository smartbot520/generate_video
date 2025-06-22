import os
import json
import requests
import shutil
from moviepy.editor import *
from moviepy.audio.fx.all import volumex
import azure.cognitiveservices.speech as speechsdk
import moviepy.config as mpy_config

# Optional: Set ImageMagick path manually (only for local Windows use)
# mpy_config.change_settings({"IMAGEMAGICK_BINARY": "C:\\Program Files\\ImageMagick-7.1.1-Q16-HDRI\\magick.exe"})

# === CONFIGURATION from ENV ===
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
REGION = os.getenv("AZURE_REGION")

SCENES_DIR = 'scenes'
OUT_DIR = 'output'
BG_MUSIC = 'bg_music.mp3'
MUTED_OVERLAY = 'Muted_Video.mp4'
IMAGE_COUNT_PER_SCENE = 2

# === Ensure output folder exists ===
os.makedirs(OUT_DIR, exist_ok=True)

# === Download images from Pexels ===
def download_images(query, scene_index, image_dir):
    scene_dir = os.path.join(image_dir, f"scene{scene_index+1}")
    os.makedirs(scene_dir, exist_ok=True)

    url = f"https://api.pexels.com/v1/search?query={query}&per_page={IMAGE_COUNT_PER_SCENE}&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    photos = data.get('photos', [])

    if not photos:
        print(f"❌ No images found for: {query}")
        return

    for i, photo in enumerate(photos[:IMAGE_COUNT_PER_SCENE]):
        image_url = photo['src'].get('portrait') or photo['src'].get('original')
        img_data = requests.get(image_url).content
        with open(os.path.join(scene_dir, f'img{i+1}.jpg'), 'wb') as f:
            f.write(img_data)

    print(f"✅ Downloaded {len(photos)} images for '{query}' → {scene_dir}")

# === Generate Telugu TTS using Azure ===
def generate_tts(text, out_path):
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=REGION)
    audio_config = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    ssml = f"""
    <speak version='1.0' xml:lang='te-IN'>
        <voice name='te-IN-ShrutiNeural'>
            <prosody rate='+15.00%' pitch='+5%'>{text}</prosody>
        </voice>
    </speak>
    """
    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise Exception(f"TTS failed: {result.reason}")

# === Process all scene files ===
SCENES_FILES = [f for f in os.listdir(SCENES_DIR) if f.endswith('.json')]

for scene_file in SCENES_FILES:
    base_name = os.path.splitext(scene_file)[0]
    print(f"\n🚀 Processing {scene_file}...")

    # Dynamic folders
    SCENES_FILE = os.path.join(SCENES_DIR, scene_file)
    IMAGE_DIR = f'images_{base_name}'
    AUDIO_DIR = f'audio_{base_name}'
    OUTPUT_SUBDIR = os.path.join(OUT_DIR, base_name)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(OUTPUT_SUBDIR, exist_ok=True)
    FULL_AUDIO = os.path.join(AUDIO_DIR, 'full_audio.mp3')
    OUT_VIDEO = os.path.join(OUTPUT_SUBDIR, 'final_video.mp4')

    # Load scenes
    with open(SCENES_FILE, 'r', encoding='utf-8') as f:
        scenes = json.load(f)

    scene_texts = [scene['text'] for scene in scenes]
    full_script = ' '.join(scene_texts)

    # Step 1: Download images
    print("🖼️ Downloading images from Pexels...")
    for idx, scene in enumerate(scenes):
        download_images(scene['image_keyword'], idx, IMAGE_DIR)

    # Step 2: Generate TTS
    print("🔊 Generating TTS from Telugu text...")
    generate_tts(full_script, FULL_AUDIO)
    tts_audio = AudioFileClip(FULL_AUDIO)
    total_audio_duration = tts_audio.duration

    # Step 3: Split duration per scene
    scene_word_counts = [len(text.split()) for text in scene_texts]
    total_words = sum(scene_word_counts)
    scene_durations = [(count / total_words) * total_audio_duration for count in scene_word_counts]

    # Step 4: Create video scenes
    print("🎞️ Creating video scenes with subtitles...")
    scene_clips = []
    for idx, (scene, duration) in enumerate(zip(scenes, scene_durations)):
        scene_path = os.path.join(IMAGE_DIR, f"scene{idx+1}")
        images = sorted([
            os.path.join(scene_path, f)
            for f in os.listdir(scene_path)
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ])

        if not images:
            raise Exception(f"No images found for scene {idx+1}")

        per_img_duration = max(duration / len(images), 2.5)

        img_clips = [
            ImageClip(img)
                .resize(height=1920)
                .crop(width=1080, height=1920, x_center=540, y_center=960)
                .set_opacity(0.85)
                .set_duration(per_img_duration)
                .set_fps(24)
            for img in images
        ]

        scene_video = concatenate_videoclips(img_clips).set_duration(duration)

        subtitle = TextClip(
            scene['subtitle'],
            fontsize=60,
            font='DejaVu-Sans',  # Use a safe system font
            color='white',
            size=(1080, None),
            method='caption'     # Avoid ImageMagick
         ).set_duration(duration).set_position(("center", "bottom")).margin(bottom=50, opacity=0).fadein(1).fadeout(1)

        scene_with_text = CompositeVideoClip([scene_video, subtitle]).fadein(1).fadeout(1)
        scene_clips.append(scene_with_text)

    # Step 5: Combine scenes
    print("📹 Combining scenes into final video...")
    video_without_audio = concatenate_videoclips(scene_clips, method="compose").set_duration(tts_audio.duration)

    # Step 6: Add muted background
    print("🎬 Adding background video...")
    overlay_video = VideoFileClip(MUTED_OVERLAY, audio=False)
    overlay_video = overlay_video.resize(height=1920).crop(width=1080, height=1920, x_center=540, y_center=960)
    overlay_video = overlay_video.loop(duration=tts_audio.duration).set_duration(tts_audio.duration)

    final_visual = CompositeVideoClip([overlay_video, video_without_audio.set_position("center")])

    # Step 7: Add audio
    print("🎵 Merging background music and TTS audio...")
    bg_music = AudioFileClip(BG_MUSIC).volumex(0.5).audio_loop(duration=tts_audio.duration)
    final_audio = CompositeAudioClip([bg_music, tts_audio])
    final_video = final_visual.set_audio(final_audio)

    # Step 8: Export final video
    print(f"💾 Exporting video to: {OUT_VIDEO}")
    final_video.write_videofile(OUT_VIDEO, codec="libx264", audio_codec="aac", fps=24)
    print(f"✅ Saved video: {OUT_VIDEO}")

    # Step 9: Cleanup
    shutil.rmtree(IMAGE_DIR)
    shutil.rmtree(AUDIO_DIR)
