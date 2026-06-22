import os, random, subprocess, threading, time
from pathlib import Path
import gdown

TMP            = Path("/tmp/catvids")
CATS_FOLDER    = "1suKDbdX6DQcC76T3Xc0n6mJeZ9i_t7CH"
PURRING_FOLDER = "1hc7-oO4PeICXWPe6b07CFsDHOe8P4qz6"
SUB_FILE_ID    = "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw"
DURATION       = random.randint(18000, 28800)
MIN_SIZE_BYTES = int(1.0 * 1024 * 1024 * 1024)
MAX_SIZE_BYTES = int(1.95 * 1024 * 1024 * 1024)
CRF            = random.randint(21, 26)
VIDEO_INDEX    = int(os.environ.get("VIDEO_INDEX", "0"))

TMP.mkdir(exist_ok=True)
(TMP / "cats").mkdir(exist_ok=True)
(TMP / "purring").mkdir(exist_ok=True)
(TMP / "sub").mkdir(exist_ok=True)

cats_dir    = TMP / "cats"
purring_dir = TMP / "purring"
sub_path    = TMP / "sub" / "sub.mp4"

def download_with_timeout(fn, timeout_sec=1800, label="download"):
    result = [None]; error = [None]
    def worker():
        try: result[0] = fn()
        except Exception as e: error[0] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start(); t.join(timeout_sec)
    if t.is_alive(): raise TimeoutError(f"{label} timed out after {timeout_sec}s")
    if error[0]: raise error[0]
    return result[0]

stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free space: {free_gb:.1f} GB")
if free_gb < 4.0:
    raise SystemExit(f"[DISK] Not enough free space ({free_gb:.1f} GB).")

print("Downloading cat videos...")
for attempt in range(3):
    try:
        download_with_timeout(
            lambda: gdown.download_folder(id=CATS_FOLDER, output=str(cats_dir), quiet=False, use_cookies=False),
            timeout_sec=900, label="cats"
        )
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")
        if attempt == 2:
            raise SystemExit(f"cats download failed: {e}")
        time.sleep(30)

print("Downloading purring audio...")
for attempt in range(3):
    try:
        download_with_timeout(
            lambda: gdown.download_folder(id=PURRING_FOLDER, output=str(purring_dir), quiet=False, use_cookies=False),
            timeout_sec=900, label="purring"
        )
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")
        if attempt == 2:
            raise SystemExit(f"purring download failed: {e}")
        time.sleep(30)

if not sub_path.exists():
    print("Downloading sub overlay...")
    try:
        download_with_timeout(
            lambda: gdown.download(id=SUB_FILE_ID, output=str(sub_path), quiet=False),
            timeout_sec=300, label="sub"
        )
    except Exception as e:
        raise SystemExit(f"sub download failed: {e}")
else:
    print("sub already present, skipping.")

stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free after downloads: {free_gb:.1f} GB")
if free_gb < 2.0:
    raise SystemExit(f"[DISK] Not enough space ({free_gb:.1f} GB).")

videos = sorted(
    list(cats_dir.glob("*.mp4")) +
    list(cats_dir.glob("*.mov")) +
    list(cats_dir.glob("*.avi")) +
    list(cats_dir.glob("*.mkv"))
)
if not videos:
    raise SystemExit("No videos found.")
if VIDEO_INDEX >= len(videos):
    raise SystemExit(f"VIDEO_INDEX {VIDEO_INDEX} out of range ({len(videos)} videos).")

video_path = videos[VIDEO_INDEX]
print(f"\n>>> VIDEO    : {video_path.name} (index {VIDEO_INDEX})")
print(f">>> DURATION : {DURATION}s ({DURATION//60}m {DURATION%60}s)")
print(f">>> CRF      : {CRF}\n")

(TMP / f"video_name_{VIDEO_INDEX}.txt").write_text(video_path.name)

songs = (
    list(purring_dir.glob("*.mp3")) +
    list(purring_dir.glob("*.wav")) +
    list(purring_dir.glob("*.m4a")) +
    list(purring_dir.glob("*.ogg"))
)
if not songs:
    raise SystemExit("No audio found.")
random.shuffle(songs)
print("Audio order:")
for i, s in enumerate(songs):
    print(f"  {i+1}. {s.name}")

concat_audio = TMP / f"concat_audio_{VIDEO_INDEX}.txt"
estimated_len = 200
repeats = max(1, (DURATION // (len(songs) * estimated_len)) + 2)
with open(concat_audio, "w") as f:
    for _ in range(repeats):
        batch = songs[:]
        random.shuffle(batch)
        for s in batch:
            f.write(f"file '{s}'\n")

# Sub overlay: every 6-14 min randomized, 3-4 sec, random bottom-left or bottom-right
intervals_left  = []
intervals_right = []
t = random.randint(360, 840)
while t < DURATION - 10:
    show_dur = random.randint(3, 4)
    end_t = t + show_dur
    if random.random() < 0.5:
        intervals_left.append((t, end_t))
    else:
        intervals_right.append((t, end_t))
    t += random.randint(360, 840)

def make_enable(intervals):
    if not intervals: return "0"
    return "+".join([f"between(t,{s},{e})" for s, e in intervals])

enable_left  = make_enable(intervals_left)
enable_right = make_enable(intervals_right)
print(f"Sub overlay: {len(intervals_left)} left, {len(intervals_right)} right appearances")

output_path = TMP / f"OUT_{VIDEO_INDEX}_{video_path.stem}.mp4"

filter_complex = (
    f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p[bg];"
    f"[1:v]scale=220:-1,chromakey=0x00ff00:0.3:0.1[sub_clean];"
    f"[sub_clean]split[sl][sr];"
    f"[bg][sl]overlay=30:H-h-30:enable='{enable_left}'[mid];"
    f"[mid][sr]overlay=W-w-30:H-h-30:enable='{enable_right}'[outv]"
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
under_minimum = False

def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(15)
        if output_path.exists():
            size = output_path.stat().st_size
            mb = size / (1024 * 1024)
            gb = size / (1024 * 1024 * 1024)
            print(f"[SIZE] {mb:.1f} MB ({gb:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] Cap reached — stopping.", flush=True)
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
    raise SystemExit(f"FFmpeg failed: {proc.returncode}")
if not output_path.exists() or output_path.stat().st_size == 0:
    raise SystemExit("No output produced.")

final_size    = output_path.stat().st_size
final_size_mb = final_size / (1024 * 1024)
final_size_gb = final_size / (1024 * 1024 * 1024)

if final_size < MIN_SIZE_BYTES:
    print(f"[SIZE] ⚠️ Under 1 GB ({final_size_gb:.3f} GB).")
    under_minimum = True

stop_reason = "cap reached" if stopped_by_watcher else "duration reached"
print(f"\nDONE — {output_path}")
print(f"Stop   : {stop_reason}")
print(f"Size   : {final_size_mb:.1f} MB ({final_size_gb:.3f} GB)")
print(f"1-2 GB : {'✅' if MIN_SIZE_BYTES <= final_size <= MAX_SIZE_BYTES else '❌'}")

github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"video_name={video_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"under_minimum={str(under_minimum).lower()}\n")
