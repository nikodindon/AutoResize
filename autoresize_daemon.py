#!/usr/bin/env python3
import yaml, os, json, time, subprocess, logging, sys
from pathlib import Path

CONFIG = yaml.safe_load(open("config.yaml"))
logging.basicConfig(
    filename=CONFIG.get("log_file", "autoresize.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("autoresize")

def target_size(duration):
    return (CONFIG["reference_max_size_gb"] * 1024**3) / (CONFIG["reference_duration_hours"]*3600) * duration

def load_cache():
    p = CONFIG.get("state_file", "state.json")
    return json.load(open(p)) if os.path.exists(p) else {}

def save_cache(cache):
    open(CONFIG.get("state_file", "state.json"), "w").write(json.dumps(cache))

def should_reencode(path):
    size = path.stat().st_size
    cache = load_cache()
    key = str(path)
    if key in cache and cache[key].get("reencoded"):
        return False, size, float(cache[key].get("duration", 0))
    if key in cache and cache[key].get("size") == size:
        duration = float(cache[key]["duration"])
    else:
        duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True).stdout.strip() or 0)
        cache[key] = {"size": size, "duration": duration}
        save_cache(cache)
    return size > target_size(duration) * CONFIG["oversize_factor"], size, duration

def reencode(src):
    out = str(src) + CONFIG["reencoded_suffix"] + src.suffix
    # Calcul du bitrate de référence pour cette vidéo
    cache = load_cache()
    duration = float(cache.get(str(src), {}).get("duration", 0) or float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(src)], capture_output=True, text=True).stdout.strip() or 0))
    target = (CONFIG["reference_max_size_gb"] * 1024**3) / (CONFIG["reference_duration_hours"] * 3600) * duration
    bitrate_kbps = int((target * 8) / (duration * 1024)) if duration > 0 else 2000
    codecs = [CONFIG["codec_video"], CONFIG.get("fallback_video", "libx265")]
    result = None
    for c in codecs:
        cmd = ["ffmpeg", "-y", "-i", str(src), "-c:v", c, "-preset", CONFIG.get("preset_video", "medium"), "-b:v", f"{bitrate_kbps}k", "-c:a", CONFIG["codec_audio"], out]
        logger.info(f"Reencoding {src} -> {out} (codec={c})")
        with open("autoresize_ffmpeg.log", "a") as ffmpeg_log:
            result = subprocess.run(cmd, stdout=ffmpeg_log, stderr=subprocess.STDOUT)
        logger.info(f"FFmpeg output saved to autoresize_ffmpeg.log (codec={c}, returncode={result.returncode})")
        if result.returncode == 0:
            break
        else:
            logger.warning(f"Codec {c} failed (returncode={result.returncode}), trying fallback.")
    if result and result.returncode != 0:
        logger.error(f"Reencoding failed for {src} with all codecs.")
        return
    if CONFIG.get("delete_original", False):
        src.unlink()
        logger.info(f"Deleted original {src}")
    else:
        logger.info(f"Kept original {src} (delete_original=false)")
    cache = load_cache()
    cache[str(src)] = {**(cache.get(str(src), {})), "reencoded": True, "reencoded_file": out}
    save_cache(cache)
    logger.info(f"Marked {src} as reencoded in state.json")

def ffmpeg_running():
    try:
        out = subprocess.run(["pgrep", "-c", "ffmpeg"], capture_output=True, text=True)
        return int(out.stdout.strip() or 0) > 0
    except:
        return False

def clean():
    cache = load_cache()
    for k, v in cache.items():
        if v.get("reencoded") and v.get("reencoded_file"):
            original = Path(k)
            new_file = Path(v["reencoded_file"])
            if new_file.exists():
                new_file.rename(original)
                logger.info(f"Clean: renamed {new_file} -> {original}")
            else:
                logger.info(f"Clean: reencoded file missing {new_file}")
    logger.info("Clean finished.")

def main():
    if "--clean" in sys.argv:
        clean()
        return
    logger.info("Daemon started.")
    for d in CONFIG["watch_dirs"]:
        for ext in CONFIG["video_extensions"]:
            for f in Path(d).rglob(f"*{ext}"):
                if CONFIG.get("reencoded_suffix") in f.name: continue
                cache = load_cache()
                key = str(f)
                size = f.stat().st_size
                # Skip rapide : même taille, déjà analysé, pas réencodé
                if key in cache and cache[key].get("size") == size and not cache[key].get("reencoded"):
                    continue
                ok, s, dur = should_reencode(f)
                logger.info(f"Check {f}: size={s}, duration={dur}s, oversize={ok}")
                if ok:
                    if ffmpeg_running():
                        logger.info(f"Queue: ffmpeg already running, skip {f}")
                    else:
                        reencode(f)

if __name__ == "__main__":
    main()
