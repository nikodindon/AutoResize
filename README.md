# AutoResize

Automatise la compression de ta bibliothèque vidéo avec FFmpeg et NVENC.

AutoResize est un daemon Python qui surveille des répertoires contenant des films et des séries, détecte les vidéos disproportionnellement volumineuses par rapport à leur durée et les réencode automatiquement.

L'objectif est simple : réduire l'espace occupé par une bibliothèque vidéo sans devoir traiter chaque fichier manuellement.

AutoResize privilégie l'encodage matériel NVIDIA avec NVENC, tout en proposant un fallback logiciel sur CPU lorsque l'encodage matériel échoue.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Fonctionnement](#fonctionnement)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancement](#lancement)
- [Installation comme service systemd](#installation-comme-service-systemd)
- [Logs et diagnostic](#logs-et-diagnostic)
- [Nettoyage et bibliothèque Kodi](#nettoyage-et-bibliothèque-kodi)
- [Limites actuelles](#limites-actuelles)
- [Roadmap](#roadmap)
- [Contribuer](#contribuer)

---

## Fonctionnalités

### Surveillance automatique
- Surveillance récursive de plusieurs répertoires.
- Détection des fichiers vidéo dont la taille dépasse un seuil calculé à partir de leur durée.
- Prise en charge des extensions configurées, notamment MKV, MP4 et AVI.
- Cache persistant dans `state.json` pour éviter de recalculer inutilement les métadonnées.
- Vérification périodique des nouveaux fichiers et de ceux qui restent à traiter.

### Encodage vidéo
- Encodage matériel NVIDIA via `hevc_nvenc` ou `h264_nvenc`.
- Encodage logiciel de secours via `libx265` ou un autre codec configuré.
- Réglage de qualité constante (`-cq`) pour NVENC.
- Presets distincts pour l'encodage matériel et le fallback CPU.
- Conservation des pistes audio via `-c:a copy` lorsque cette option est configurée.
- Journalisation des commandes et résultats FFmpeg.

### Sécurité et récupération
- Vérification de la durée du fichier produit avec `ffprobe`.
- Conservation temporaire de l'original sous la forme `.original` lorsque la suppression automatique est activée.
- Vérification du fichier réencodé avant le remplacement final.
- Mode de nettoyage manuel avec `--clean`.
- Synchronisation de la bibliothèque Kodi après les renommages effectués par le nettoyage.

### Conçu pour fonctionner en arrière-plan
AutoResize peut être lancé manuellement ou exécuté en tant que service utilisateur `systemd`. Une fois démarré, il surveille les répertoires configurés sans intervention régulière.

---

## Fonctionnement

AutoResize repose sur un **budget de taille proportionnel à la durée** de chaque vidéo.

Par exemple, avec une référence de 1 Go pour 2 heures et un facteur de dépassement de 1.3, le programme considère qu'une vidéo de deux heures dépassant environ 1,3 Go mérite d'être examinée pour compression.

Le calcul est le suivant :

```
taille_de_référence = taille_maximale_de_référence × durée_vidéo ÷ durée_de_référence
seuil_de_traitement  = taille_de_référence × facteur_de_dépassement
```

Une vidéo n'est éligible que si sa taille dépasse ce seuil.

### Étapes du traitement
1. Parcourir les répertoires surveillés.
2. Identifier les fichiers vidéo qui n'ont pas déjà été traités.
3. Récupérer leur durée avec `ffprobe`.
4. Comparer leur taille au seuil configuré.
5. Lancer FFmpeg si le fichier est éligible et qu'aucun autre processus FFmpeg n'est détecté.
6. Utiliser le codec et le preset principaux, puis tenter le fallback en cas d'échec.
7. Vérifier la durée du fichier produit.
8. Finaliser le traitement selon la configuration, puis mettre à jour le cache.
9. Synchroniser Kodi après les renommages effectués par la procédure de nettoyage.

Le programme recommence ensuite son cycle après l'intervalle configuré.

> **Le seuil de taille n'est pas une taille de sortie garantie**
>
> Le budget de taille sert à décider quelles vidéos doivent être traitées. Il ne garantit pas la taille finale lorsque NVENC utilise le mode `-cq`.
>
> En qualité constante, le débit varie en fonction de la complexité de l'image. Deux films de même durée peuvent donc produire des fichiers de tailles très différentes.

---

## Prérequis

- Linux recommandé.
- Python 3.
- FFmpeg et `ffprobe`.
- PyYAML (`pip install pyyaml`).
- Un GPU NVIDIA et un pilote compatible pour utiliser NVENC.
- Kodi avec JSON-RPC activé, uniquement si tu souhaites l'intégration Kodi.

Vérifier les outils :

```bash
python3 --version
ffmpeg -version
ffprobe -version
nvidia-smi
```

Installer les dépendances Python (Linux Mint / Ubuntu) :

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg
```

Créer un environnement Python :

```bash
cd /chemin/vers/AutoResize
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml
```

Vérifier que l'installation FFmpeg prend en charge NVENC :

```bash
ffmpeg -encoders | grep nvenc
```

> La présence des encodeurs dans la liste ne garantit pas à elle seule que le pilote et le GPU permettent leur utilisation. Un test d'encodage réel reste nécessaire.

---

## Installation

Cloner le dépôt :

```bash
git clone https://github.com/nikodindon/AutoResize.git
cd AutoResize
```

Créer le fichier de configuration à partir de l'exemple :

```bash
cp config.yaml.example config.yaml
```

Modifier `config.yaml` selon tes répertoires, tes paramètres d'encodage et, si nécessaire, les informations de connexion à Kodi.

> **Important** : le daemon charge actuellement `config.yaml` depuis le répertoire de travail courant. Lance-le depuis le répertoire du projet ou configure explicitement le répertoire de travail dans ton service `systemd`.

---

## Configuration

Exemple de configuration :

```yaml
watch_dirs:
  - /path/to/movies
  - /path/to/series

check_interval_minutes: 3

reference_duration_hours: 2.0
reference_max_size_gb: 1.0
oversize_factor: 1.3

video_extensions:
  - .mkv
  - .mp4
  - .avi

codec_video: hevc_nvenc
fallback_video: libx265

preset_video: p5
preset_fallback: medium

cq: 27
codec_audio: copy

delete_original: false
reencoded_suffix: .reencoded

log_file: autoresize.log
state_file: state.json

kodi:
  host: ""
  port: 8082
  user: ""
  pass: ""
```

Adapte cet exemple à ton environnement. Les valeurs de référence et le `CQ` sont des exemples, pas des réglages universels.

### Paramètres de surveillance

| Paramètre | Description |
|--|--|
| `watch_dirs` | Liste des répertoires surveillés récursivement. |
| `check_interval_minutes` | Intervalle entre deux cycles de surveillance. |
| `video_extensions` | Extensions de fichiers prises en charge. |

### Paramètres de sélection

| Paramètre | Description |
|--|--|
| `reference_duration_hours` | Durée de référence pour le calcul du budget. |
| `reference_max_size_gb` | Taille de référence pour cette durée. |
| `oversize_factor` | Multiplicateur appliqué au budget avant déclenchement du réencodage. |

Exemple : avec `reference_max_size_gb: 1.0`, `reference_duration_hours: 2.0` et `oversize_factor: 1.3`, une vidéo de deux heures devient éligible au-dessus d'environ 1,3 Go.

> Ces paramètres déterminent l'**éligibilité** des fichiers, pas leur taille de sortie en mode `CQ`.

### Paramètres d'encodage

| Paramètre | Description |
|--|--|
| `codec_video` | Codec principal, par exemple `hevc_nvenc` ou `h264_nvenc`. |
| `fallback_video` | Codec de secours, par exemple `libx265`. |
| `preset_video` | Preset du codec principal ; les presets NVENC utilisent notamment `p1` à `p7`. |
| `preset_fallback` | Preset du codec de secours, par exemple `medium`. |
| `cq` | Valeur de qualité constante utilisée avec NVENC si elle est définie. |
| `codec_audio` | Codec audio ou `copy` pour conserver les flux audio sans les réencoder. |

#### Comprendre le paramètre `CQ`

Avec NVENC, `-cq` contrôle la qualité visuelle recherchée. En règle générale :

- `CQ` plus bas : meilleure qualité et fichiers généralement plus volumineux.
- `CQ` plus élevé : compression plus agressive et risque accru de dégradation visuelle.

Le résultat dépend du contenu, du codec et de ses options. Il est préférable de comparer plusieurs scènes représentatives avant de choisir une valeur pour toute une bibliothèque.

#### Comprendre les presets

Les presets définissent différents compromis entre vitesse d'encodage et efficacité de compression. Pour NVENC, `p1` à `p7` correspondent aux niveaux de preset disponibles dans les versions compatibles de FFmpeg et du pilote.

Un preset plus lent ne garantit pas à lui seul une meilleure qualité perçue : le `CQ`, le contenu et les options d'encodage comptent également.

### Cache et fichiers de sortie

| Paramètre | Description |
|--|--|
| `delete_original` | Active ou désactive le mécanisme de remplacement automatique de l'original. |
| `reencoded_suffix` | Suffixe utilisé pour nommer les fichiers intermédiaires réencodés. |
| `state_file` | Fichier JSON contenant les métadonnées et l'état des fichiers. |
| `log_file` | Fichier journal principal. |

Le cache évite de recalculer la durée des fichiers dont la taille n'a pas changé et mémorise les traitements terminés.

> **Attention** : tant que le mécanisme de remplacement et de nettoyage n'a pas été entièrement sécurisé pour tous les cas, teste les modifications sur des fichiers non critiques et conserve une sauvegarde indépendante. Ne considère pas `delete_original: false` comme une garantie de conservation sans avoir vérifié le comportement de la version utilisée.

### Intégration Kodi

Le bloc `kodi` est facultatif. Pour l'activer, configure l'adresse du serveur Kodi, son port JSON-RPC et les identifiants nécessaires.

> **Ne publie jamais tes identifiants réels dans le dépôt Git.** Garde-les dans ton fichier local `config.yaml`, qui doit rester ignoré par Git.

---

## Lancement

Depuis le répertoire du projet, avec l'environnement virtuel activé :

```bash
python3 autoresize_daemon.py
```

Le daemon commence à surveiller les répertoires définis dans `config.yaml`.

Pour arrêter le programme lancé au premier plan, utilise `Ctrl+C`.

### Comment fonctionne le traitement simultané ?

La version actuelle vérifie la présence d'un processus FFmpeg avant de lancer un nouvel encodage. Si FFmpeg est déjà actif, le fichier éligible est ignoré pour ce cycle et pourra être examiné de nouveau lors d'un cycle ultérieur.

Il ne s'agit pas encore d'une **file d'attente persistante** : les tâches en attente ne sont pas enregistrées explicitement comme des travaux à exécuter.

---

## Installation comme service systemd

Pour exécuter AutoResize en arrière-plan avec un service utilisateur :

```bash
mkdir -p ~/.config/systemd/user
cp autoresize.service ~/.config/systemd/user/
```

Vérifie le fichier `autoresize.service` et adapte notamment le chemin du projet, l'interpréteur Python et le répertoire de travail.

Puis :

```bash
systemctl --user daemon-reload
systemctl --user enable --now autoresize.service
```

Vérifier l'état :

```bash
systemctl --user status autoresize.service
```

Suivre les journaux :

```bash
journalctl --user -u autoresize.service -f
```

Pour redémarrer le service après une modification :

```bash
systemctl --user restart autoresize.service
```

Le service sera lancé automatiquement à la connexion de l'utilisateur si l'activation (`enable`) a été effectuée. Pour un fonctionnement utilisateur même sans session ouverte, le comportement dépend de la configuration `systemd` et du `linger`.

---

## Logs et diagnostic

AutoResize utilise un journal principal défini par `log_file` et écrit également les sorties FFmpeg dans `autoresize_ffmpeg.log`.

Consulter le journal principal :

```bash
tail -f autoresize.log
```

Consulter le journal FFmpeg :

```bash
tail -f autoresize_ffmpeg.log
```

Les journaux permettent notamment de retrouver :
- Les fichiers examinés et leur éligibilité.
- Les commandes d'encodage lancées.
- Les erreurs et tentatives de fallback.
- Les résultats des validations.
- Les opérations de renommage et les appels Kodi.

> Les chemins des journaux sont à adapter si le service `systemd` utilise un autre répertoire de travail.

---

## Nettoyage et bibliothèque Kodi

Le daemon dispose d'un mode de nettoyage manuel :

```bash
python3 autoresize_daemon.py --clean
```

Cette opération parcourt les entrées réencodées présentes dans le cache, vérifie la durée des fichiers de sortie et traite les renommages associés. Lorsqu'un répertoire est modifié, le programme peut demander à Kodi de scanner ce répertoire via JSON-RPC.

Le nettoyage peut supprimer le fichier de sauvegarde `.original` après validation et remplacement. Il faut donc considérer cette opération comme **destructive**.

Avant de lancer le nettoyage sur une bibliothèque importante :

1. Vérifie le contenu de `state.json`.
2. Contrôle que les fichiers de sortie existent et sont lisibles.
3. Conserve une sauvegarde indépendante des originaux importants.
4. Teste le processus sur un petit répertoire.

> L'option `--clean` n'est pas un mode de simulation et ne doit pas être utilisée comme tel.

---

## Limites actuelles

AutoResize est un outil en évolution. La version actuelle présente notamment les limites suivantes :

- **Pas encore de tableau de bord ni de statistiques globales consolidées.**
- **Pas de file d'attente persistante** avec priorités, reprises et historique des tâches.
- **Pas de sélection automatique du `CQ`** en fonction du contenu vidéo.
- **La validation de sortie** vérifie principalement la durée, pas l'intégralité de la qualité ou de la structure des flux.
- **La détection de FFmpeg** s'appuie sur les processus visibles par `pgrep` et ne constitue pas un système de verrouillage dédié.
- **Les paramètres de codec** ne sont pas encore optimisés automatiquement selon la résolution, le grain, le type de contenu ou le GPU.
- **Le cache JSON** est simple et ne constitue pas encore une base de données transactionnelle.

Ces limites constituent les principaux axes de développement de la roadmap.

---

## Roadmap

La priorité est de conserver un daemon léger, autonome et fiable, puis de lui ajouter progressivement de l'intelligence et une interface de supervision.

Les cases ci-dessous représentent des objectifs à réaliser, et **non des fonctionnalités déjà disponibles**.

### Phase 1 — Fiabilité et sécurité
**Objectif** : garantir que les originaux ne sont jamais perdus à cause d'un échec d'encodage ou d'un état incohérent.

- [ ] Définir un cycle de vie explicite des tâches : `pending`, `encoding`, `validating`, `completed`, `failed`.
- [ ] Sécuriser le remplacement des originaux, notamment lorsque `delete_original` est désactivé.
- [ ] Garantir qu'un fichier temporaire ne remplace jamais un original avant validation.
- [ ] Ajouter une validation des flux vidéo et audio, de la durée et de la lisibilité du fichier.
- [ ] Éviter les traitements concurrents avec un verrouillage dédié.
- [ ] Rendre les écritures du cache résistantes aux interruptions et aux arrêts brutaux.
- [ ] Ajouter un mode simulation sans modification des fichiers.
- [ ] Tester les scénarios d'erreur : disque plein, arrêt de FFmpeg, fichier incomplet, redémarrage du daemon.

**Critère de réussite** : aucun original n'est supprimé ou remplacé par une sortie non validée, y compris après un redémarrage.

---

### Phase 2 — File d'attente persistante
**Objectif** : transformer le cycle de surveillance actuel en un véritable gestionnaire de tâches.

- [ ] Enregistrer les tâches à traiter dans un état persistant.
- [ ] Conserver la file d'attente après un redémarrage.
- [ ] Reprendre les tâches interrompues ou les remettre proprement en attente.
- [ ] Distinguer les tâches en attente, actives, terminées et en erreur.
- [ ] Ajouter des tentatives de reprise limitées avec journalisation des erreurs.
- [ ] Éviter de retraiter un fichier en cours de téléchargement ou de copie.
- [ ] Ajouter une politique de priorité : plus gros fichiers, gain estimé, ordre d'arrivée ou priorité manuelle.
- [ ] Permettre de suspendre et de reprendre le traitement.

**Critère de réussite** : aucun fichier éligible n'est définitivement perdu parce qu'un encodage était déjà en cours.

---

### Phase 3 — Statistiques et rapports
**Objectif** : mesurer précisément l'efficacité d'AutoResize.

- [ ] Enregistrer la taille initiale et la taille finale de chaque vidéo.
- [ ] Calculer l'économie en octets et en pourcentage.
- [ ] Mesurer la durée d'encodage et la vitesse moyenne.
- [ ] Produire des statistiques globales par répertoire, codec et période.
- [ ] Afficher le nombre de fichiers terminés, en attente et en erreur.
- [ ] Calculer les économies cumulées et les gains récents.
- [ ] Générer un rapport lisible en JSON ou en HTML.

**Critère de réussite** : connaître à tout moment l'espace économisé, les performances et l'état de la bibliothèque.

---

### Phase 4 — Profils d'encodage intelligents
**Objectif** : adapter les paramètres au contenu plutôt que d'appliquer le même `CQ` à toutes les vidéos.

- [ ] Créer des profils distincts pour les films, les séries, l'animation et la 4K.
- [ ] Détecter la résolution, le codec source, le débit, la profondeur de couleur et la durée.
- [ ] Permettre des profils configurables selon le type de contenu.
- [ ] Ajouter un mode de test sur un échantillon de scènes représentatives.
- [ ] Comparer les résultats selon la taille, le temps d'encodage et des métriques de qualité disponibles.
- [ ] Proposer des réglages initiaux sans les appliquer automatiquement.
- [ ] Introduire ensuite une sélection automatique des paramètres, activable séparément.

**Critère de réussite** : obtenir un compromis qualité/taille mesuré et reproductible, sans dégradation excessive sur les contenus difficiles.

---

### Phase 5 — Tableau de bord Web local
**Objectif** : superviser AutoResize sans devoir consulter constamment les journaux.

- [ ] Créer une interface Web légère accessible sur le réseau local.
- [ ] Afficher les statistiques globales et l'espace économisé.
- [ ] Montrer les tâches en attente, en cours, terminées et en erreur.
- [ ] Afficher la progression et la vitesse de l'encodage actif.
- [ ] Consulter l'historique des traitements.
- [ ] Ajouter des commandes pour suspendre, reprendre ou relancer une tâche.
- [ ] Permettre de consulter les profils d'encodage et les paramètres actifs.
- [ ] Sécuriser l'accès et ne pas exposer l'interface publiquement par défaut.

**Critère de réussite** : piloter et diagnostiquer le daemon depuis un navigateur sans accéder directement à la machine.

---

### Phase 6 — Intégrations et optimisation
**Objectif** : améliorer l'intégration dans un serveur multimédia domestique.

- [ ] Fiabiliser les scans Kodi et éviter les appels redondants.
- [ ] Ajouter une reprise des synchronisations Kodi échouées.
- [ ] Distinguer les répertoires de films et de séries lorsque cela est nécessaire.
- [ ] Améliorer la gestion des pistes audio, sous-titres, chapitres et métadonnées.
- [ ] Ajouter des limites de charge et des plages horaires d'encodage.
- [ ] Permettre des profils différents selon les machines et les capacités matérielles.
- [ ] Documenter les procédures de sauvegarde, de migration et de mise à jour.

**Critère de réussite** : disposer d'un service autonome et configurable pour une bibliothèque multimédia importante.

---

## Contribuer

Les contributions, idées et rapports de bugs sont les bienvenus.

Avant de proposer une modification :

1. Vérifie le comportement actuel et les limites documentées.
2. Teste sur un petit ensemble de fichiers.
3. Ne modifie pas les originaux pendant les tests sans sauvegarde.
4. Ajoute des logs et des tests pour les nouveaux comportements.
5. Mets à jour le README lorsque les fonctionnalités ou la configuration changent.

Les améliorations privilégiées sont celles qui renforcent la **fiabilité**, réduisent les interventions manuelles et **mesurent objectivement** les résultats.

---

## Licence

La licence du projet doit être précisée dans le dépôt avant toute redistribution officielle. Consulte le fichier `LICENSE` s'il est ajouté au dépôt.

---

AutoResize — une bibliothèque vidéo plus légère, automatiquement.
