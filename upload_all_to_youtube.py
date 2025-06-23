import os
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === Config ===
SCENES_DIR = "scenes"
FINAL_COMBINED_DIR = "final_combined"
CREDENTIALS_PICKLE_FILE = "youtube_token.pickle"
CLIENT_SECRETS_FILE = "client_secrets.json"
THUMBNAIL_FILE = "thumbnail.jpg"  # Optional

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    credentials = None
    if os.path.exists(CREDENTIALS_PICKLE_FILE):
        with open(CREDENTIALS_PICKLE_FILE, "rb") as token:
            credentials = pickle.load(token)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(CREDENTIALS_PICKLE_FILE, "wb") as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)

def upload_video(file_path, metadata):
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "27"  # Education
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(file_path, mimetype="video/*", resumable=True)

    print(f"📤 Uploading: {file_path}")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None

    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"⏳ Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"✅ Uploaded: https://www.youtube.com/watch?v={video_id}")

    # Optional: upload thumbnail
    if os.path.exists(THUMBNAIL_FILE):
        youtube.thumbnails().set(videoId=video_id, media_body=THUMBNAIL_FILE).execute()
        print("🖼️ Thumbnail uploaded.")

def main():
    json_files = [f for f in os.listdir(SCENES_DIR) if f.endswith('.json')]

    for json_file in json_files:
        base_name = os.path.splitext(json_file)[0]
        json_path = os.path.join(SCENES_DIR, json_file)
        video_path = os.path.join(FINAL_COMBINED_DIR, f"{base_name}_combined.mp4")

        if not os.path.exists(video_path):
            print(f"❌ Skipping {base_name}: Combined video not found.")
            continue

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata = data.get("metadata")
        if not metadata:
            print(f"⚠️ Skipping {base_name}: Metadata missing.")
            continue

        upload_video(video_path, metadata)

if __name__ == "__main__":
    main()
