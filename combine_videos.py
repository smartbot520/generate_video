import os
from moviepy.editor import *

INTRO_VIDEO = "Intro_Shorts.mp4"
OUTRO_VIDEO = "Outro_Shorts.mp4"
OUTPUT_DIR = "output"
FINAL_DIR = "final_combined"

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 24

os.makedirs(FINAL_DIR, exist_ok=True)

def prepare_clip(clip):
    clip = clip.resize(height=TARGET_HEIGHT)
    if clip.w != TARGET_WIDTH:
        clip = clip.crop(width=TARGET_WIDTH, x_center=clip.w / 2)
    return clip.set_fps(TARGET_FPS)

for folder in os.listdir(OUTPUT_DIR):
    final_path = os.path.join(OUTPUT_DIR, folder, "final_video.mp4")
    if not os.path.exists(final_path):
        continue

    print(f"🔗 Combining: {folder}")
    intro_clip = prepare_clip(VideoFileClip(INTRO_VIDEO))
    main_clip = prepare_clip(VideoFileClip(final_path))
    outro_clip = prepare_clip(VideoFileClip(OUTRO_VIDEO))

    combined = concatenate_videoclips([intro_clip, main_clip, outro_clip], method="compose")
    combined.write_videofile(os.path.join(FINAL_DIR, f"{folder}_combined.mp4"), codec="libx264", audio_codec="aac", fps=TARGET_FPS)
