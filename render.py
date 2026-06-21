import os
import random
import subprocess
import threading
import time
from pathlib import Path
import gdown

TMP            = Path("/tmp/catvids")
CATS_FOLDER    = "1suKDbdX6DQcC76T3Xc0n6mJeZ9i_t7CH"
PURRING_FOLDER = "1hc7-oO4PeICXWPe6b07CFsDHOe8P4qz6"
SUB_FILE_ID    = "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw"
DURATION       = random.randint(2400, 3600)
MAX_SIZE_BYTES = int(1.8 * 1024 * 1024 * 1024)
CRF            = random.randint(21, 26)

SUB_POSITION = random.choice(["bottom_left", "bottom_right", "bottom_center"])
if SUB_POSITION == "bottom_left":
    overlay_x = "30"
elif SUB_POSITION == "bottom_center":
    overlay_x = "(W-w)/2"
else:
    overlay_x = "W-w-30"

VIDEO_INDEX = int(os.environ.get("VIDEO_INDEX", "0"))

TMP.mkdir(exist_ok=True)
(TMP / "cats").mkdir(exist_ok=True)
(TMP / "purring").mkdir(exist_ok=True)
(TMP / "sub").mkdir(exist_ok=True)

def download_with_timeout(fn, timeout_sec=1800, label="download"):
    result = [None]
    error  = [None]
    def worker():
        try:
            result[0] = fn()
        except Exception as e:
            error[0] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        raise TimeoutError(f"{label} timed out after {timeout_sec}s")
    if error[0]:
        raise error[0]
    return result[0]

stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free space: {free_gb:.1f} GB")
if free_gb < 4.0:
    raise SystemExit(f"[DISK] Not enough free space ({free_gb:.1f} GB). Need at least 4 GB.")

cats_dir    = TMP / "cats"
purring_dir = TMP / "purring"
sub_path    = TMP / "sub" / "sub.mp4"

print("Downloading cat videos...")
for attempt in range(3):
    try:
        download_with_timeout(
            lambda: gdown.download_folder(id=CATS_FOLDER, output=str(cats_dir), quiet=False, use_cookies=False),
            timeout_sec=900, label="cats folder"
        )
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")
        if attempt == 2:
            raise SystemExit(f"Failed to download cats folder after 3 attempts: {e}")
        time.sleep(30)

print("Downloading purring audio...")
for attempt in range(3):
    try:
        download_with_timeout(
            lambda: gdown.download_folder(id=PURRING_FOLDER, output=str(purring_dir), quiet=False, use_cookies=False),
            timeout_sec=900, label="purring folder"
        )
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")
        if attempt == 2:
            raise SystemExit(f"Failed to download purring folder after 3 attempts: {e}")
        time.sleep(30)

if not sub_path.exists():
    print("Downloading subscribe button...")
    try:
        download_with_timeout(
            lambda: gdown.download(id=SUB_FILE_ID, output=str(sub_path), quiet=False),
            timeout_sec=300, label="sub.mp4"
        )
    except Exception as e:
        raise SystemExit(f"Failed to download sub.mp4: {e}")
else:
    print("Skipping sub.mp4 (already downloaded)")

stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free after downloads: {free_gb:.1f} GB")
if free_gb < 2.0:
    raise SystemExit(f"[DISK] Not enough space to render ({free_gb:.1f} GB free).")

videos = sorted(
    list(cats_dir.glob("*.mp4")) +
    list(cats_dir.glob("*.mov")) +
    list(cats_dir.glob("*.avi")) +
    list(cats_dir.glob("*.mkv"))
)
if not videos:
    raise SystemExit("No videos found in cats folder.")
if VIDEO_INDEX >= len(videos):
    raise SystemExit(f"VIDEO_INDEX {VIDEO_INDEX} out of range — only {len(videos)} videos found.")

video_path = videos[VIDEO_INDEX]
print(f"\n>>> VIDEO USED   : {video_path.name} (index {VIDEO_INDEX})")
print(f">>> DURATION     : {DURATION}s ({DURATION//60}m {DURATION%60}s) — stops at 1.8 GB")
print(f">>> CRF          : {CRF}")
print(f">>> SUB POSITION : {SUB_POSITION}\n")

(TMP / f"video_name_{VIDEO_INDEX}.txt").write_text(video_path.name)

songs = (
    list(purring_dir.glob("*.mp3")) +
    list(purring_dir.glob("*.wav")) +
    list(purring_dir.glob("*.m4a")) +
    list(purring_dir.glob("*.ogg"))
)
if not songs:
    raise SystemExit("No audio found in purring folder.")
random.shuffle(songs)
print("Audio order:")
for i, s in enumerate(songs):
    print(f"  {i+1}. {s.name}")

concat_audio = TMP / f"concat_audio_{VIDEO_INDEX}.txt"
estimated_len = 200
repeats = max(1, (DURATION // (len(songs) * estimated_len)) + 2)
with open(concat_audio, "w") as f:
    for _ in range(repeats):
        for s in songs:
            f.write(f"file '{s}'\n")

intervals = []
t = 30
while t < DURATION - 10:
    intervals.append(t)
    t += 828
enable_parts = "+".join([f"between(t,{s},{s+4})" for s in intervals])

output_path = TMP / f"OUT_{VIDEO_INDEX}_{video_path.stem}.mp4"

filter_complex = (
    f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p[bg];"
    f"[1:v]scale=220:-1,"
    f"chromakey=0x00ff00:0.3:0.1[sub];"
    f"[bg][sub]overlay={overlay_x}:H-h-30:enable='{enable_parts}'[outv]"
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
    "-crf", str(CRF),
    "-c:a", "aac",
    "-b:a", "128k",
    "-ar", "44100",
    "-movflags", "+faststart",
    str(output_path),
]

print("\nRunning FFmpeg...")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

stopped_by_watcher = False

def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(15)
        if output_path.exists():
            size = output_path.stat().st_size
            mb   = size / (1024 * 1024)
            gb   = size / (1024 * 1024 * 1024)
            print(f"[SIZE] {output_path.name} → {mb:.1f} MB ({gb:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] ⚠️  Hit 1.8 GB cap — stopping FFmpeg cleanly.", flush=True)
                stopped_by_watcher = True
                proc.terminate()
                break

watcher = threading.Thread(target=size_watcher, daemon=True)
watcher.start()

for line in proc.stdout:
    print(line, end="", flush=True)

proc.wait()
watcher.join()

if not stopped_by_watcher and proc.returncode != 0:
    raise SystemExit(f"FFmpeg failed with exit code {proc.returncode}")

if not output_path.exists() or output_path.stat().st_size == 0:
    raise SystemExit("FFmpeg produced no output file.")

final_size    = output_path.stat().st_size
final_size_mb = final_size / (1024 * 1024)
final_size_gb = final_size / (1024 * 1024 * 1024)
stop_reason   = "capped at 1.8 GB by size watcher" if stopped_by_watcher else "duration reached"

print(f"\nDONE — {output_path}")
print(f"Stop reason  : {stop_reason}")
print(f"CRF used     : {CRF}")
print(f"Sub position : {SUB_POSITION}")
print(f"Size         : {final_size_mb:.1f} MB ({final_size_gb:.3f} GB)")
print(f"Video        : {video_path.name}")

github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"video_name={video_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"crf={CRF}\n")
        f.write(f"sub_position={SUB_POSITION}\n")
