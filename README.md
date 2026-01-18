# Jellyfin Suggested

Creates personalized "Suggested For You" playlists for each Jellyfin user based on their watch history and TMDB recommendations.

## How It Works

1. Fetches each user's recently watched movies and TV shows
2. Uses TMDB API to find similar content
3. Filters recommendations to content that **already exists in your Jellyfin library**
4. Creates/updates a "Suggested For You" playlist for each user
5. Sorts suggestions by TMDB rating

No new content is downloaded - this only surfaces existing library content that users might enjoy.

## Requirements

- Jellyfin server with API access
- TMDB API key (free at https://www.themoviedb.org/settings/api)
- Docker (recommended) or Python 3.11+

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/jessedye/jellyfin-suggested.git
   cd jellyfin-suggested
   ```

2. Create your environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your credentials:
   ```
   JELLYFIN_URL=http://your-jellyfin-server:8096
   JELLYFIN_API_KEY=your_jellyfin_api_key
   TMDB_API_KEY=your_tmdb_api_key
   ```

4. Run:
   ```bash
   docker compose run --rm jellyfin-suggested
   ```

### Using Docker directly

```bash
docker run --rm \
  -e JELLYFIN_URL=http://your-jellyfin-server:8096 \
  -e JELLYFIN_API_KEY=your_api_key \
  -e TMDB_API_KEY=your_tmdb_key \
  ghcr.io/jessedye/jellyfin-suggested:latest
```

### Using Python

```bash
pip install -r requirements.txt

export JELLYFIN_URL=http://your-jellyfin-server:8096
export JELLYFIN_API_KEY=your_api_key
export TMDB_API_KEY=your_tmdb_key

python jellyfin_suggested.py
```

## Getting API Keys

### Jellyfin API Key

1. Open Jellyfin web UI
2. Go to **Dashboard** > **API Keys**
3. Click **+** to create a new key
4. Name it "jellyfin-suggested" and copy the key

### TMDB API Key

1. Create account at https://www.themoviedb.org
2. Go to **Settings** > **API**
3. Request an API key (choose "Developer" option)
4. Copy the **API Key** (not the Read Access Token)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JELLYFIN_URL` | *required* | Jellyfin server URL |
| `JELLYFIN_API_KEY` | *required* | Jellyfin API key |
| `TMDB_API_KEY` | *required* | TMDB API key |
| `PLAYLIST_NAME` | `Suggested For You` | Name of the playlist to create |
| `MAX_WATCHED_ITEMS` | `20` | Number of recently watched items to analyze per user |
| `MAX_SIMILAR_PER_ITEM` | `5` | Max similar items to fetch per watched item |
| `MAX_PLAYLIST_ITEMS` | `50` | Max items in the suggestion playlist |
| `MIN_TMDB_RATING` | `6.0` | Minimum TMDB rating to include |
| `MIN_TMDB_VOTES` | `50` | Minimum TMDB vote count to include |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Scheduling

This script is designed to run periodically (e.g., daily) to keep playlists fresh.

### Using cron (Linux/macOS)

```bash
# Run daily at 3 AM
0 3 * * * cd /path/to/jellyfin-suggested && docker compose run --rm jellyfin-suggested
```

### Using systemd timer

Create `/etc/systemd/system/jellyfin-suggested.service`:
```ini
[Unit]
Description=Jellyfin Suggested Playlist Generator

[Service]
Type=oneshot
WorkingDirectory=/path/to/jellyfin-suggested
ExecStart=/usr/bin/docker compose run --rm jellyfin-suggested
```

Create `/etc/systemd/system/jellyfin-suggested.timer`:
```ini
[Unit]
Description=Run Jellyfin Suggested daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable --now jellyfin-suggested.timer
```

## Viewing Playlists in Jellyfin

After running, each user will have a "Suggested For You" playlist visible in:
- **Home** > **My Media** > **Playlists**
- Or via **Libraries** > **Playlists**

You can pin the playlist to the home screen for easy access.

## License

MIT
