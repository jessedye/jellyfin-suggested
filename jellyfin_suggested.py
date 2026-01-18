#!/usr/bin/env python3
"""
Jellyfin Suggested - Creates personalized "Suggested For You" playlists for each Jellyfin user
based on their watch history and TMDB similar content recommendations.
"""

import asyncio
import aiohttp
import os
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('JellyfinSuggested')


@dataclass
class Config:
    """Configuration loaded from environment variables."""
    jellyfin_url: str
    jellyfin_api_key: str
    tmdb_api_key: str
    playlist_name: str = "Suggested For You"
    max_watched_items: int = 20
    max_similar_per_item: int = 5
    max_playlist_items: int = 50
    min_tmdb_rating: float = 6.0
    min_tmdb_votes: int = 50
    request_timeout: int = 30

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        jellyfin_url = os.getenv('JELLYFIN_URL', '').rstrip('/')
        jellyfin_api_key = os.getenv('JELLYFIN_API_KEY', '')
        tmdb_api_key = os.getenv('TMDB_API_KEY', '')

        if not all([jellyfin_url, jellyfin_api_key, tmdb_api_key]):
            raise ValueError(
                "Missing required environment variables. "
                "Please set JELLYFIN_URL, JELLYFIN_API_KEY, and TMDB_API_KEY"
            )

        return cls(
            jellyfin_url=jellyfin_url,
            jellyfin_api_key=jellyfin_api_key,
            tmdb_api_key=tmdb_api_key,
            playlist_name=os.getenv('PLAYLIST_NAME', 'Suggested For You'),
            max_watched_items=int(os.getenv('MAX_WATCHED_ITEMS', '20')),
            max_similar_per_item=int(os.getenv('MAX_SIMILAR_PER_ITEM', '5')),
            max_playlist_items=int(os.getenv('MAX_PLAYLIST_ITEMS', '50')),
            min_tmdb_rating=float(os.getenv('MIN_TMDB_RATING', '6.0')),
            min_tmdb_votes=int(os.getenv('MIN_TMDB_VOTES', '50')),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '30')),
        )


class JellyfinClient:
    """Client for interacting with Jellyfin API."""

    def __init__(self, config: Config, session: aiohttp.ClientSession):
        self.config = config
        self.session = session
        self.headers = {'X-Emby-Token': config.jellyfin_api_key}

    async def get_users(self) -> list[dict]:
        """Get all Jellyfin users."""
        url = f"{self.config.jellyfin_url}/Users"
        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                return await resp.json()
            logger.error(f"Failed to get users: {resp.status}")
            return []

    async def get_watched_items(self, user_id: str, media_type: str) -> list[dict]:
        """Get recently watched items for a user."""
        url = f"{self.config.jellyfin_url}/Items"
        params = {
            'userId': user_id,
            'isPlayed': 'true',
            'sortBy': 'DatePlayed',
            'sortOrder': 'Descending',
            'recursive': 'true',
            'includeItemTypes': media_type,
            'limit': self.config.max_watched_items,
            'fields': 'ProviderIds'
        }
        async with self.session.get(url, headers=self.headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('Items', [])
            logger.error(f"Failed to get watched items: {resp.status}")
            return []

    async def get_library_items(self, media_type: str) -> dict[int, dict]:
        """Get all items in library indexed by TMDB ID."""
        url = f"{self.config.jellyfin_url}/Items"
        params = {
            'recursive': 'true',
            'includeItemTypes': media_type,
            'fields': 'ProviderIds'
        }
        async with self.session.get(url, headers=self.headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                items = {}
                for item in data.get('Items', []):
                    tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
                    if tmdb_id:
                        items[int(tmdb_id)] = item
                return items
            logger.error(f"Failed to get library items: {resp.status}")
            return {}

    async def get_user_playlists(self, user_id: str) -> list[dict]:
        """Get playlists for a user."""
        url = f"{self.config.jellyfin_url}/Items"
        params = {
            'userId': user_id,
            'includeItemTypes': 'Playlist',
            'recursive': 'true'
        }
        async with self.session.get(url, headers=self.headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('Items', [])
            return []

    async def create_playlist(self, user_id: str, name: str, item_ids: list[str]) -> Optional[str]:
        """Create a new playlist."""
        url = f"{self.config.jellyfin_url}/Playlists"
        params = {
            'userId': user_id,
            'name': name,
            'ids': ','.join(item_ids),
            'mediaType': 'Mixed'
        }
        async with self.session.post(url, headers=self.headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('Id')
            logger.error(f"Failed to create playlist: {resp.status}")
            return None

    async def get_playlist_items(self, playlist_id: str, user_id: str) -> list[dict]:
        """Get items in a playlist."""
        url = f"{self.config.jellyfin_url}/Playlists/{playlist_id}/Items"
        params = {'userId': user_id}
        async with self.session.get(url, headers=self.headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('Items', [])
            return []

    async def clear_playlist(self, playlist_id: str, item_ids: list[str]) -> bool:
        """Remove items from a playlist."""
        if not item_ids:
            return True
        url = f"{self.config.jellyfin_url}/Playlists/{playlist_id}/Items"
        params = {'entryIds': ','.join(item_ids)}
        async with self.session.delete(url, headers=self.headers, params=params) as resp:
            return resp.status == 204

    async def add_to_playlist(self, playlist_id: str, user_id: str, item_ids: list[str]) -> bool:
        """Add items to a playlist."""
        if not item_ids:
            return True
        url = f"{self.config.jellyfin_url}/Playlists/{playlist_id}/Items"
        params = {'userId': user_id, 'ids': ','.join(item_ids)}
        async with self.session.post(url, headers=self.headers, params=params) as resp:
            return resp.status == 204


class TMDbClient:
    """Client for interacting with TMDB API."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, config: Config, session: aiohttp.ClientSession):
        self.config = config
        self.session = session

    async def get_similar(self, tmdb_id: int, media_type: str) -> list[dict]:
        """Get similar movies/shows from TMDB."""
        endpoint = 'movie' if media_type == 'Movie' else 'tv'
        url = f"{self.BASE_URL}/{endpoint}/{tmdb_id}/similar"
        params = {'api_key': self.config.tmdb_api_key}

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for item in data.get('results', [])[:self.config.max_similar_per_item]:
                        vote_avg = item.get('vote_average', 0)
                        vote_count = item.get('vote_count', 0)
                        if vote_avg >= self.config.min_tmdb_rating and vote_count >= self.config.min_tmdb_votes:
                            results.append({
                                'id': item['id'],
                                'title': item.get('title') or item.get('name'),
                                'vote_average': vote_avg
                            })
                    return results
                return []
        except Exception as e:
            logger.error(f"Error getting similar for {tmdb_id}: {e}")
            return []


class PlaylistGenerator:
    """Generates personalized playlists for Jellyfin users."""

    def __init__(self, config: Config):
        self.config = config
        self.jellyfin: Optional[JellyfinClient] = None
        self.tmdb: Optional[TMDbClient] = None

    async def run(self):
        """Main entry point to generate playlists for all users."""
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.jellyfin = JellyfinClient(self.config, session)
            self.tmdb = TMDbClient(self.config, session)

            # Get library content indexed by TMDB ID
            logger.info("Fetching library content...")
            movie_library = await self.jellyfin.get_library_items('Movie')
            series_library = await self.jellyfin.get_library_items('Series')
            logger.info(f"Found {len(movie_library)} movies and {len(series_library)} series in library")

            # Process each user
            users = await self.jellyfin.get_users()
            logger.info(f"Processing {len(users)} users...")

            for user in users:
                await self.process_user(user, movie_library, series_library)

    async def process_user(self, user: dict, movie_library: dict, series_library: dict):
        """Generate playlist for a single user."""
        user_id = user['Id']
        user_name = user['Name']
        logger.info(f"Processing user: {user_name}")

        # Get watched items
        watched_movies = await self.jellyfin.get_watched_items(user_id, 'Movie')
        watched_series = await self.jellyfin.get_watched_items(user_id, 'Episode')

        # Extract unique series from episodes
        seen_series = set()
        unique_series = []
        for episode in watched_series:
            series_id = episode.get('SeriesId')
            if series_id and series_id not in seen_series:
                seen_series.add(series_id)
                # Get series info for TMDB ID
                series_info = await self.get_series_info(user_id, series_id)
                if series_info:
                    unique_series.append(series_info)

        logger.info(f"  Found {len(watched_movies)} watched movies, {len(unique_series)} watched series")

        # Find similar content
        suggested_items = []
        watched_tmdb_ids = set()

        # Collect watched TMDB IDs to exclude
        for movie in watched_movies:
            tmdb_id = movie.get('ProviderIds', {}).get('Tmdb')
            if tmdb_id:
                watched_tmdb_ids.add(int(tmdb_id))

        for series in unique_series:
            tmdb_id = series.get('ProviderIds', {}).get('Tmdb')
            if tmdb_id:
                watched_tmdb_ids.add(int(tmdb_id))

        # Get similar movies
        for movie in watched_movies[:self.config.max_watched_items]:
            tmdb_id = movie.get('ProviderIds', {}).get('Tmdb')
            if tmdb_id:
                similar = await self.tmdb.get_similar(int(tmdb_id), 'Movie')
                for s in similar:
                    if s['id'] in movie_library and s['id'] not in watched_tmdb_ids:
                        jellyfin_item = movie_library[s['id']]
                        if jellyfin_item['Id'] not in [i['Id'] for i in suggested_items]:
                            suggested_items.append({
                                'Id': jellyfin_item['Id'],
                                'Name': jellyfin_item['Name'],
                                'Type': 'Movie',
                                'Score': s['vote_average']
                            })

        # Get similar series
        for series in unique_series[:self.config.max_watched_items]:
            tmdb_id = series.get('ProviderIds', {}).get('Tmdb')
            if tmdb_id:
                similar = await self.tmdb.get_similar(int(tmdb_id), 'Series')
                for s in similar:
                    if s['id'] in series_library and s['id'] not in watched_tmdb_ids:
                        jellyfin_item = series_library[s['id']]
                        if jellyfin_item['Id'] not in [i['Id'] for i in suggested_items]:
                            suggested_items.append({
                                'Id': jellyfin_item['Id'],
                                'Name': jellyfin_item['Name'],
                                'Type': 'Series',
                                'Score': s['vote_average']
                            })

        # Sort by TMDB score and limit
        suggested_items.sort(key=lambda x: x['Score'], reverse=True)
        suggested_items = suggested_items[:self.config.max_playlist_items]

        logger.info(f"  Found {len(suggested_items)} suggestions")

        if suggested_items:
            await self.update_playlist(user_id, user_name, suggested_items)

    async def get_series_info(self, user_id: str, series_id: str) -> Optional[dict]:
        """Get series info including provider IDs."""
        url = f"{self.config.jellyfin_url}/Items/{series_id}"
        params = {'userId': user_id, 'fields': 'ProviderIds'}
        async with self.jellyfin.session.get(url, headers=self.jellyfin.headers, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

    async def update_playlist(self, user_id: str, user_name: str, items: list[dict]):
        """Create or update the suggestions playlist for a user."""
        playlist_name = self.config.playlist_name
        playlists = await self.jellyfin.get_user_playlists(user_id)

        # Find existing playlist
        existing_playlist = None
        for p in playlists:
            if p['Name'] == playlist_name:
                existing_playlist = p
                break

        item_ids = [item['Id'] for item in items]

        if existing_playlist:
            playlist_id = existing_playlist['Id']
            logger.info(f"  Updating existing playlist for {user_name}")

            # Get current items and clear them
            current_items = await self.jellyfin.get_playlist_items(playlist_id, user_id)
            if current_items:
                entry_ids = [item['PlaylistItemId'] for item in current_items]
                await self.jellyfin.clear_playlist(playlist_id, entry_ids)

            # Add new items
            await self.jellyfin.add_to_playlist(playlist_id, user_id, item_ids)
        else:
            logger.info(f"  Creating new playlist for {user_name}")
            await self.jellyfin.create_playlist(user_id, playlist_name, item_ids)

        logger.info(f"  Playlist updated with {len(items)} items")
        for item in items[:5]:
            logger.info(f"    - {item['Name']} ({item['Type']}, score: {item['Score']:.1f})")
        if len(items) > 5:
            logger.info(f"    ... and {len(items) - 5} more")


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Jellyfin Suggested - Personalized Playlist Generator")
    logger.info(f"Started at {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        config = Config.from_env()
        generator = PlaylistGenerator(config)
        await generator.run()
        logger.info("Completed successfully!")
    except ValueError as e:
        logger.error(str(e))
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())
