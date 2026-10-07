# AutoResize

Daemon Python qui surveille des répertoires contenant films/épisodes et réencode ceux dont la taille dépasse le seuil de référence (2h = 1.5 Go, avec un facteur 1.5x).

## Config (`config.yaml`)
- `watch_dirs` : répertoires surveillés
- `check_interval_minutes` : fréquence
- `reference_max_size_gb` / `reference_duration_hours` : référence
- `oversize_factor` : seuil de dépassement pour déclencher le réencodage
- `delete_original` : false par défaut (garde l'original)
- `codec_video` : `hevc_nvenc` (GPU), `h264_nvenc` (GPU), `libx265` (CPU, taille minimale), `libx264` (CPU, rapide)
- `preset_video` : `ultrafast`, `fast`, `medium`, `slow`, `veryslow` (ou `p1`..`p7` pour NVENC)

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
