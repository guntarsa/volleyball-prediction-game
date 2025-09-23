"""
YouTube API integration for volleyball highlights fetching
"""
import os
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False
    logging.warning("Google API client not installed. YouTube features will be disabled.")


class YouTubeService:
    """Handle YouTube API interactions for volleyball highlights"""

    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        self.service = None

        if not self.api_key:
            logging.warning("YOUTUBE_API_KEY environment variable not set")
        elif YOUTUBE_API_AVAILABLE:
            try:
                self.service = build('youtube', 'v3', developerKey=self.api_key)
                logging.info("YouTube API service initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize YouTube API service: {e}")
        else:
            logging.warning("YouTube API client not available")

    def is_available(self) -> bool:
        """Check if YouTube API is available and configured"""
        return YOUTUBE_API_AVAILABLE and self.api_key is not None and self.service is not None

    def search_volleyball_highlights(self, team1: str, team2: str, game_date: datetime,
                                   max_results: int = 10) -> List[Dict]:
        """
        Search for volleyball highlights for a specific game

        Args:
            team1: First team name
            team2: Second team name
            game_date: Date of the game
            max_results: Maximum number of results to return

        Returns:
            List of video dictionaries with metadata
        """
        if not self.is_available():
            logging.error("YouTube API not available")
            return []

        try:
            # Generate search queries
            search_queries = self._generate_search_queries(team1, team2, game_date)

            all_videos = []

            for query in search_queries[:3]:  # Limit to first 3 queries to save quota
                try:
                    videos = self._search_videos(query, max_results=5)
                    all_videos.extend(videos)

                    if len(all_videos) >= max_results:
                        break

                except Exception as e:
                    logging.error(f"Error searching with query '{query}': {e}")
                    continue

            # Remove duplicates and filter relevant videos
            unique_videos = self._deduplicate_videos(all_videos)
            relevant_videos = self._filter_relevant_videos(unique_videos, team1, team2)

            # Sort by relevance (view count, upload date, title match)
            sorted_videos = self._sort_by_relevance(relevant_videos, team1, team2)

            return sorted_videos[:max_results]

        except Exception as e:
            logging.error(f"Error searching for volleyball highlights: {e}")
            return []

    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get detailed information about a specific video"""
        if not self.is_available():
            return None

        try:
            request = self.service.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            )
            response = request.execute()

            if response['items']:
                video = response['items'][0]
                return self._format_video_data(video)

        except HttpError as e:
            logging.error(f"HTTP error getting video details for {video_id}: {e}")
        except Exception as e:
            logging.error(f"Error getting video details for {video_id}: {e}")

        return None

    def _generate_search_queries(self, team1: str, team2: str, game_date: datetime) -> List[str]:
        """Generate multiple search query variations for volleyball highlights"""
        date_str = game_date.strftime('%Y')

        queries = [
            # Specific match queries
            f'"{team1}" vs "{team2}" volleyball highlights {date_str}',
            f'{team1} {team2} volleyball World Championship 2025',
            f'{team1} vs {team2} FIVB Men volleyball highlights',

            # General tournament queries
            f'FIVB Men World Championship 2025 {team1} highlights',
            f'FIVB Men World Championship 2025 {team2} highlights',
            f'volleyball World Championship Philippines 2025 {team1}',

            # Channel-specific searches
            f'{team1} vs {team2} Volleyball World',
            f'{team1} {team2} volleyball highlights FIVB',

            # Fallback queries
            f'{team1} volleyball highlights 2025',
            f'{team2} volleyball highlights 2025'
        ]

        return queries

    def _search_videos(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search for videos with a specific query"""
        try:
            # Calculate date range (1 week before to 2 days after game)
            search_date = datetime.now() - timedelta(days=30)  # Search last 30 days
            published_after = search_date.strftime('%Y-%m-%dT%H:%M:%SZ')

            request = self.service.search().list(
                part='snippet',
                q=query,
                type='video',
                order='relevance',
                maxResults=max_results,
                publishedAfter=published_after,
                regionCode='US',
                relevanceLanguage='en',
                videoDuration='medium',  # 4-20 minutes, good for highlights
                videoDefinition='any'
            )

            response = request.execute()

            videos = []
            for item in response.get('items', []):
                video_data = self._format_search_result(item)
                if video_data:
                    videos.append(video_data)

            return videos

        except HttpError as e:
            logging.error(f"HTTP error searching videos: {e}")
            return []
        except Exception as e:
            logging.error(f"Error searching videos: {e}")
            return []

    def _format_search_result(self, item: Dict) -> Optional[Dict]:
        """Format a search result item into our standard format"""
        try:
            video_id = item['id']['videoId']
            snippet = item['snippet']

            return {
                'video_id': video_id,
                'title': snippet['title'],
                'description': snippet['description'],
                'channel_name': snippet['channelTitle'],
                'upload_date': datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                'thumbnail_url': snippet['thumbnails'].get('medium', {}).get('url', ''),
                'youtube_url': f'https://www.youtube.com/watch?v={video_id}',
                'view_count': 0,  # Will be filled by get_video_details if needed
                'duration': None,  # Will be filled by get_video_details if needed
                'relevance_score': 0
            }
        except Exception as e:
            logging.error(f"Error formatting search result: {e}")
            return None

    def _format_video_data(self, video: Dict) -> Dict:
        """Format video data from videos().list() response"""
        snippet = video['snippet']
        statistics = video.get('statistics', {})
        content_details = video.get('contentDetails', {})

        return {
            'video_id': video['id'],
            'title': snippet['title'],
            'description': snippet['description'],
            'channel_name': snippet['channelTitle'],
            'upload_date': datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
            'thumbnail_url': snippet['thumbnails'].get('medium', {}).get('url', ''),
            'youtube_url': f'https://www.youtube.com/watch?v={video["id"]}',
            'view_count': int(statistics.get('viewCount', 0)),
            'duration': content_details.get('duration', ''),
            'like_count': int(statistics.get('likeCount', 0)),
            'comment_count': int(statistics.get('commentCount', 0))
        }

    def _deduplicate_videos(self, videos: List[Dict]) -> List[Dict]:
        """Remove duplicate videos based on video ID"""
        seen_ids = set()
        unique_videos = []

        for video in videos:
            if video['video_id'] not in seen_ids:
                seen_ids.add(video['video_id'])
                unique_videos.append(video)

        return unique_videos

    def _filter_relevant_videos(self, videos: List[Dict], team1: str, team2: str) -> List[Dict]:
        """Filter videos to only include volleyball-related content"""
        relevant_videos = []

        for video in videos:
            title_lower = video['title'].lower()
            description_lower = video['description'].lower()
            channel_lower = video['channel_name'].lower()

            # Check for volleyball keywords
            volleyball_keywords = ['volleyball', 'fivb', 'world championship', 'highlights']
            has_volleyball = any(keyword in title_lower or keyword in description_lower
                               for keyword in volleyball_keywords)

            # Check for team names
            team1_lower = team1.lower()
            team2_lower = team2.lower()
            has_teams = (team1_lower in title_lower or team1_lower in description_lower or
                        team2_lower in title_lower or team2_lower in description_lower)

            # Check for trusted channels
            trusted_channels = ['volleyball world', 'fivb', 'olympics', 'world championship']
            is_trusted_channel = any(channel in channel_lower for channel in trusted_channels)

            # Calculate relevance score
            relevance_score = 0
            if has_volleyball:
                relevance_score += 2
            if has_teams:
                relevance_score += 3
            if is_trusted_channel:
                relevance_score += 2
            if 'highlights' in title_lower:
                relevance_score += 1
            if 'vs' in title_lower and has_teams:
                relevance_score += 1

            video['relevance_score'] = relevance_score

            # Only include videos with some relevance
            if relevance_score >= 2:
                relevant_videos.append(video)

        return relevant_videos

    def _sort_by_relevance(self, videos: List[Dict], team1: str, team2: str) -> List[Dict]:
        """Sort videos by relevance score, view count, and upload date"""
        def sort_key(video):
            return (
                video['relevance_score'],  # Primary: relevance score
                video['view_count'],       # Secondary: view count
                video['upload_date']       # Tertiary: upload date (recent first)
            )

        return sorted(videos, key=sort_key, reverse=True)

    def get_channel_videos(self, channel_name: str, max_results: int = 10) -> List[Dict]:
        """Get recent videos from a specific channel"""
        if not self.is_available():
            return []

        try:
            # First, search for the channel
            search_request = self.service.search().list(
                part='snippet',
                q=channel_name,
                type='channel',
                maxResults=1
            )
            search_response = search_request.execute()

            if not search_response['items']:
                return []

            channel_id = search_response['items'][0]['id']['channelId']

            # Get videos from the channel
            videos_request = self.service.search().list(
                part='snippet',
                channelId=channel_id,
                type='video',
                order='date',
                maxResults=max_results
            )
            videos_response = videos_request.execute()

            videos = []
            for item in videos_response.get('items', []):
                video_data = self._format_search_result(item)
                if video_data:
                    videos.append(video_data)

            return videos

        except Exception as e:
            logging.error(f"Error getting channel videos for {channel_name}: {e}")
            return []


# Global instance
youtube_service = YouTubeService()


def search_game_highlights(game_id: int) -> List[Dict]:
    """
    Main function to search for highlights for a specific game
    Returns list of video dictionaries
    """
    try:
        # Import here to avoid circular imports
        from app import Game

        game = Game.query.get(game_id)
        if not game:
            logging.error(f"Game {game_id} not found")
            return []

        logging.info(f"Searching highlights for {game.team1} vs {game.team2}")
        return youtube_service.search_volleyball_highlights(
            game.team1, game.team2, game.game_date, max_results=5
        )

    except Exception as e:
        logging.error(f"Error searching highlights for game {game_id}: {e}")
        return []


def get_featured_channels_latest() -> List[Dict]:
    """Get latest videos from featured volleyball channels"""
    featured_channels = [
        'Volleyball World',
        'FIVB Volleyball',
        'Olympics'
    ]

    all_videos = []
    for channel in featured_channels:
        videos = youtube_service.get_channel_videos(channel, max_results=3)
        all_videos.extend(videos)

    # Sort by upload date and return recent videos
    all_videos.sort(key=lambda v: v['upload_date'], reverse=True)
    return all_videos[:10]