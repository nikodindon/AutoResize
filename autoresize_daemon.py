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
    result = size > target_size(duration) * CONFIG["oversize_factor"]
    if not result:
        cache[key]["checked_not_oversize"] = True
        save_cache(cache)
    return result, size, duration

def reencode(src):
    out = str(src) + CONFIG["reencoded_suffix"] + src.suffix
    # Calcul du bitrate de référence pour cette vidéo
    cache = load_cache()
    duration = float(cache.get(str(src), {}).get("duration", 0) or float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(src)], capture_output=True, text=True).stdout.strip() or 0))
    target = (CONFIG["reference_max_size_gb"] * 1024**3) / (CONFIG["reference_duration_hours"] * 3600) * duration
    bitrate_kbps = int((target * 8) / (duration * 1024)) if duration > 0 else 2000
    codecs = [CONFIG["codec_video"], CONFIG.get("fallback_video", "libx265")]
    result = None
    for i, c in enumerate(codecs):
        preset = CONFIG.get("preset_video", "medium") if i == 0 else CONFIG.get("preset_fallback", CONFIG.get("preset_video", "medium"))
        cmd = ["ffmpeg", "-y", "-i", str(src), "-c:v", c, "-preset", preset]
        if "nvenc" in c and CONFIG.get("cq") is not None:
            cmd += ["-cq", str(CONFIG.get("cq"))]
        else:
            cmd += ["-b:v", f"{bitrate_kbps}k"]
        cmd += ["-c:a", CONFIG["codec_audio"], out]
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
        # Renommer le .reencoded en nom original (sans suffixe)
        out_renamed = str(src)
        if Path(out).exists():
            Path(out).rename(out_renamed)
            logger.info(f"Renamed reencoded {out} -> {out_renamed}")
            out = out_renamed  # mettre à jour pour le cache
            # Appel Kodi clean library
            try:
                import urllib.request, base64, json
                kodi_cfg = CONFIG.get("kodi", {})
                if kodi_cfg.get("host"):
                    auth = base64.b64encode(f"{kodi_cfg.get('user','')}:{kodi_cfg.get('pass','')}".encode()).decode()
                    req = urllib.request.Request(
                        f"http://{kodi_cfg['host']}:{kodi_cfg.get('port',8082)}/jsonrpc",
                        data=json.dumps({"jsonrpc":"2.0","method":"VideoLibrary.Clean","params":{"showdialogs":False,"content":"movies"},"id":1}).encode(),
                        headers={"Content-Type":"application/json","Authorization":"Basic "+auth}
                    )
                    urllib.request.urlopen(req, timeout=5)
                    logger.info("Kodi clean library called.")
            except Exception as e:
                logger.warning(f"Kodi clean library failed: {e}")
    else:
        logger.info(f"Kept original {src} (delete_original=false)")
    # Mettre à jour la taille du fichier final (renommé ou non) dans le cache
    final_path = Path(str(src)) if CONFIG.get("delete_original", False) and Path(out).exists() else (Path(out_renamed) if CONFIG.get("delete_original", False) else Path(out))
    # En fait, utilisons directement le chemin final (out après renommage si applicable)
    final_path = Path(out_renamed) if (CONFIG.get("delete_original", False) and Path(out_renamed).exists()) else (Path(str(src)) if CONFIG.get("delete_original", False) and Path(str(src)).exists() else Path(out))
    if final_path.exists():
        final_size = final_path.stat().st_size
        cache = load_cache()
        cache[str(src)] = {**(cache.get(str(src), {})), "reencoded": True, "reencoded_file": str(final_path) if final_path != Path(str(src)) else str(final_path), "size": final_size}
        save_cache(cache)
        logger.info(f"Updated cache size={final_size} for {final_path}")
    else:
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
    logger.info("Daemon started (loop mode, interval=%s min).", CONFIG.get("check_interval_minutes", 30))
    while True:
        for d in CONFIG["watch_dirs"]:
            for ext in CONFIG["video_extensions"]:
                for f in Path(d).rglob(f"*{ext}"):
                    if CONFIG.get("reencoded_suffix") in f.name: continue
                    cache = load_cache()
                    key = str(f)
                    size = f.stat().st_size
                    # Skip rapide : déjà réencodé (même taille) ou non oversize confirmé
                    if key in cache and cache[key].get("reencoded"):
                        if cache[key].get("size") == size:
                            continue
                        else:
                            # Taille du fichier renommé a changé, mettre à jour le cache
                            cache = load_cache()
                            cache[key]["size"] = size
                            # Mettre à jour reencoded_file si nécessaire (le même chemin)
                            cache[key]["reencoded_file"] = str(f)
                            save_cache(cache)
                            continue
                    if key in cache and cache[key].get("checked_not_oversize") and cache[key].get("size") == size:
                        continue
                    ok, s, dur = should_reencode(f)
                    logger.info(f"Check {f}: size={s}, duration={dur}s, oversize={ok}")
                    if ok:
                        if ffmpeg_running():
                            logger.info(f"Queue: ffmpeg already running, skip {f}")
                        else:
                            reencode(f)
        time.sleep(CONFIG.get("check_interval_minutes", 30) * 60)

if __name__ == "__main__":
    main()
