# AutoResize

Daemon Python qui surveille une bibliothèque vidéo et réencode automatiquement les fichiers disproportionnellement volumineux par rapport à leur durée. Utilise FFmpeg avec NVENC et un mode qualité constante (`-cq`).

## Config (`config.yaml`)
- `watch_dirs` : répertoires surveillés
- `check_interval_minutes` : fréquence
- `reference_max_size_gb` / `reference_duration_hours` : budget de taille proportionnel à la durée (ex. 1 Go pour 2h)
- `oversize_factor` : seuil de dépassement pour déclencher le réencodage (ex. 1.3 = 30% au-dessus du budget)
- `codec_video` / `preset_video` / `cq` : encodage NVENC avec qualité constante (`-cq`). Le bitrate devient variable selon la complexité de la scène.
- `preset_fallback` / `fallback_video` : fallback CPU (`libx265`) avec preset séparé (`medium`).
- `delete_original` : false par défaut (garde l'original)
- `codec_video` : `hevc_nvenc` (GPU), `h264_nvenc` (GPU), `libx265` (CPU, taille minimale), `libx264` (CPU, rapide)
- `preset_video` : `ultrafast`, `fast`, `medium`, `slow`, `veryslow` (ou `p1`..`p7` pour NVENC)
- `preset_fallback` : preset pour le codec de repli (ex. `fast` pour `libx264`)
- `cq` : qualité constante (`-cq`) pour NVENC uniquement (ex. `28`) ; remplace `-b:v` sur `hevc_nvenc`/`h264_nvenc`
- Cache (`state.json`) : conserve `codec_version` (`codec`, `preset`, `cq`) pour permettre le retraitement si le profil change.

## Lancement
```bash
python3 autoresize_daemon.py
```
## Service systemd
```bash
cp autoresize.service ~/.config/systemd/user/
# ou /etc/systemd/system/ pour système
systemctl --user daemon-reload
systemctl --user enable --now autoresize.service
systemctl --user status autoresize.service
journalctl --user -u autoresize.service -f
```
Le service démarre automatiquement au reboot si `enable` est fait.

## Nettoyage manuel (`--clean`)
Après avoir testé manuellement les vidéos réencodées (`.reencoded.mkv`), lancer :
```bash
python3 autoresize_daemon.py --clean
```
Cela supprime les originaux trop gros et renomme les `.reencoded.mkv` en noms originaux. Ensuite, passer `delete_original: true` dans `config.yaml` pour automatiser le nettoyage directement lors du réencodage.

## Roadmap / améliorations suggérées

- Séparer `preset_video` (NVENC `p1..p7`) et `preset_fallback` (CPU `fast`/`medium`) : fait.
- Ajouter `cq` pour NVENC (`-cq`) au lieu de `-b:v` : fait (`cq: 28` dans config).
- Explication `-cq` : mode qualité constante (inverse du % qualité) ; plus le chiffre est bas, meilleure est la qualité et plus le fichier est gros (`-cq 28` ≈ correct, `-cq 22` ≈ très bon, `-cq 18` ≈ excellent). NVENC respecte mieux `-cq` que `-b:v`.
- Validation du fichier produit après encodage (`ffprobe` sur output) avant suppression de l'original.
- Cache `state.json` : ajouter version du codec (`hevc_nvenc` / `p5` / `cq 28`) pour permettre le retraitement si le profil change.
- Remplacer le fallback `libx264` par `libx265` pour rester cohérent avec la stratégie HEVC.
- Sécurité : remplacer suppression immédiate par un renommage atomique (`.original.mkv`) + suppression différée (`--clean`).
- Kodi : adapter le nettoyage (`movies` vs `tvshows`) selon les `watch_dirs`.
- Limiter à un seul `ffmpeg` à la fois (`pgrep` déjà en place) — conserver pour éviter la saturation GPU sur 1650 SUPER.
