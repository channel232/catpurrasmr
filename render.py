import os
import random
import subprocess
import urllib.request
import re
from pathlib import Path
import gdown

# ── Config ────────────────────────────────────────────────────────────────────
TMP            = Path("/tmp/catvids")
CATS_FOLDER    = "1suKDbdX6DQcC76T3Xc0n6mJeZ9i_t7CH"
PURRING_FOLDER = "1hc7-oO4PeICXWPe6b07CFsDHOe8P4qz6"
SUB_FILE_ID    = "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw"

DURATION = random.randint(2400, 3600)  # 40–60 min

# ── Setup dirs ────────────────────────────────────────────────────────────────
TMP.mkdir(exist_ok=True)
(TMP / "cats").mkdir(exist_ok=True)
(TMP / "purring").mkdir(exist_ok=True)
(TMP / "sub").mkdir(exist_ok=True)

# ── Download assets ───────────────────────────────────────────────────────────
print("Downloading cat videos...")
gdown.download_folder(id=CATS_FOLDER, output=str(TMP / "cats"), quiet=False, use_cookies=False)

print("Downloading purring audio...")
gdown.download_folder(id=PURRING_FOLDER, output=str(TMP / "purring"), quiet=False, use_cookies=False)

print("Downloading subscribe button...")
gdown.download(id=SUB_FILE_ID, output=str(TMP / "sub" / "sub.mp4"), quiet=False)

# ── Pick one random video ─────────────────────────────────────────────────────
videos = (
    list((TMP / "cats").glob("*.mp4")) +
    list((TMP / "cats").glob("*.mov")) +
    list((TMP / "cats").glob("*.avi")) +
    list((TMP / "cats").glob("*.mkv"))
)
if not videos:
    raise SystemExit("No videos found in cats folder.")

video_path = random.choice(videos)
print(f"\n>>> VIDEO USED: {video_path.name}")
print(f">>> DURATION  : {DURATION}s ({DURATION//60}m {DURATION%60}s)\n")

# ── Save video name for summary ───────────────────────────────────────────────
(TMP / "video_name.txt").write_text(video_path.name)

# ── Try to get Drive file ID for video preview ────────────────────────────────
try:
    req = urllib.request.Request(
        f"https://drive.google.com/drive/folders/{CATS_FOLDER}",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    html = urllib.request.urlopen(req).read().decode("utf-8")
    name_id_matches = re.findall(r'"(1[a-zA-Z0-9_-]{25,})"[^}]*?"([^"]+\.(?:mp4|mov|avi|mkv))"', html, re.IGNORECASE)
    file_id = None
    for fid, fname in name_id_matches:
        if fname.lower() == video_path.name.lower():
            file_id = fid
            break
    if file_id:
        (TMP / "video_id.txt").write_text(file_id)
        print(f">>> Drive file ID: {file_id}")
    else:
        print(">>> Could not extract Drive file ID")
except Exception as e:
    print(f">>> Drive ID lookup failed: {e}")

# ── Shuffle purring audio ─────────────────────────────────────────────────────
songs = (
    list((TMP / "purring").glob("*.mp3")) +
    list((TMP / "purring").glob("*.wav")) +
    list((TMP / "purring").glob("*.m4a")) +
    list((TMP / "purring").glob("*.ogg"))
)
if not songs:
    raise SystemExit("No audio found in purring folder.")

random.shuffle(songs)

concat_audio = TMP / "concat_audio.txt"
estimated_len = 200
repeats = max(1, (DURATION // (len(songs) * estimated_len)) + 2)
with open(concat_audio, "w") as f:
    for _ in range(repeats):
        for s in songs:
            f.write(f"file '{s}'\n")

# ── Sub overlay timing (every 3 min, 4 sec) ───────────────────────────────────
sub_path = TMP / "sub" / "sub.mp4"
intervals = []
t = 30
while t < DURATION - 10:
    intervals.append(t)
    t += 180
enable_parts = "+".join([f"between(t,{s},{s+4})" for s in intervals])

# ── Output path ───────────────────────────────────────────────────────────────
output_path = TMP / f"OUT_{video_path.stem}.mp4"

# ── FFmpeg ────────────────────────────────────────────────────────────────────
filter_complex = (
    f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p[bg];"
    f"[1:v]scale=220:-1,"
    f"chromakey=0x00ff00:0.3:0.1[sub];"
    f"[bg][sub]overlay=30:H-h-30:enable='{enable_parts}'[outv]"
)

cmd = [
    "ffmpeg", "-y",
    "-stream_loop", "-1", "-i", str(video_path),
    "-stream_loop", "-1", "-i", str(sub_path),
    "-f", "concat", "-safe", "0", "-i", str(concat_audio),
    "-t", str(DURATION),
    "-filter_complex", filter_complex,
    "-map", "[outv]",
    "-map", "2:a",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "23",
    "-c:a", "aac",
    "-b:a", "128k",
    "-ar", "44100",
    "-movflags", "+faststart",
    "-shortest",
    str(output_path),
]

print("\nRunning FFmpeg...")
result = subprocess.run(cmd)

if result.returncode != 0:
    raise SystemExit("FFmpeg failed.")

size_mb = output_path.stat().st_size / (1024 * 1024)
print(f"\nDONE — {output_path}")
print(f"Size     : {size_mb:.1f} MB")
print(f"Duration : {DURATION//60}m {DURATION%60}s")
print(f"Video    : {video_path.name}")
