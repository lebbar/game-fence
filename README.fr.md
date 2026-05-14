# Game Fence

🌍 **Langues**

- 🇸🇦 [العربية](README.ar.md)
- 🇬🇧 [English](README.md)
- 🇫🇷 **Français** _(ce fichier)_

---

Application **Windows** pour **limiter ou bloquer le lancement de programmes** selon un **planning hebdomadaire** (par exécutable). Utile pour encadrer le temps d’écran ou des jeux ; l’outil se lance en arrière-plan et les processus ciblés peuvent être fermés automatiquement hors des plages autorisées.

## Fonctionnalités

- Règles par **exécutable** (ex. `steam.exe`) avec modes par jour : bloqué toute la journée, autorisé uniquement entre certaines heures, etc.
- Interface **Tkinter** : français, anglais, arabe (RTL).
- Heure de référence : **NTP** quand le réseau le permet, sinon repli sur l’horloge système ; fuseau **UTC±N** configurable.
- **Raccourci global** `Ctrl+Shift+G` pour afficher la fenêtre (nécessite le module `keyboard`).
- Fichier de configuration JSON persistant.

## Prérequis

- **Windows 10/11** (64 bits).
- **Python 3.10+** (pour l’exécution depuis les sources).

## Téléchargement (exécutable)

**Utilisateurs** (sans Python) :

- **Lien direct (dernier `GameFence.exe`) :**  
  [https://github.com/lebbar/game-fence/releases/latest/download/GameFence.exe](https://github.com/lebbar/game-fence/releases/latest/download/GameFence.exe)

- **Releases :** [https://github.com/lebbar/game-fence/releases](https://github.com/lebbar/game-fence/releases)

### Publier une release (mainteneur)

**Option A — CI (recommandé)**  
Pousse un tag de version ; GitHub Actions (`.github/workflows/release.yml`) compile sous Windows et attache **`GameFence.exe`** à la release correspondante :

```powershell
git tag v1.0.0
git push origin v1.0.0
```

**Option B — manuel**  
Build avec `.\build.ps1` → `dist\GameFence.exe`, puis sur GitHub : **Releases** → **Draft a new release** → tag (ex. `v1.0.0`) → joindre **`GameFence.exe`** → **Publish release**.

## Installation (développement)

```powershell
git clone <votre-url-git>
cd game-fence
python -m pip install -r requirements.txt
```

Pour le raccourci clavier global :

```text
pip install keyboard
```

(déjà listé dans `requirements.txt`.)

## Lancement

```powershell
python main.py
```

Au premier lancement, l’application peut rester masquée : utiliser **`Ctrl+Shift+G`** pour ouvrir la fenêtre.

## Configuration

Fichier : `%LOCALAPPDATA%\GameFence\config.json`

- Règles, intervalle de surveillance, langue d’interface, décalage fuseau (UTC±N), etc.

## Build — exécutable autonome

Avec **PyInstaller** (voir `requirements-build.txt`) :

```powershell
.\build.ps1
```

Sortie : `dist\GameFence.exe` (sans console).

### Installateur Windows (optionnel)

1. Compiler l’EXE avec `build.ps1`.
2. Ouvrir `installer.iss` dans **[Inno Setup](https://jrsoftware.org/isinfo.php)** et lancer **Compiler**.

Sortie : dossier `installer_output\`.

## Structure du dépôt

| Élément | Rôle |
|---------|------|
| `main.py` | Interface graphique |
| `core.py` | Planification, config, fermeture de processus |
| `clock_sync.py` | Synchronisation NTP / temps de référence |
| `i18n.py` | Chaînes et polices selon la locale |
| `locales/` | Traductions `fr.json`, `en.json`, `ar.json` |
| `GameFence.spec` | Définition PyInstaller |
| `build.ps1` | Installation des deps + build de l’EXE |

## Dépendances principales

- `keyboard` — hook clavier pour le raccourci global.
- `ntplib` — requête NTP.

## Sécurité & limites

- Le contrôle repose sur l’ordinateur où l’outil tourne ; un utilisateur avec des droits administrateur peut désactiver l’outil. 
- À combiner avec des comptes Windows adaptés pour un usage sérieux de type "contrôle parental".
- Cet outil ne remplace pas un encadrement physique ni la présence d’un adulte.
- Une personne avec un profil technique peut souvent trouver une faille ou un contournement ; ne considérez pas la protection comme absolue.

---

*Projet personnel — contributions et issues bienvenues.*
