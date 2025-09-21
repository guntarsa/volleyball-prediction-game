"""
SerpApi integration for automatic volleyball result fetching
"""
import os
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

try:
    import serpapi
    SERPAPI_AVAILABLE = True
except ImportError:
    SERPAPI_AVAILABLE = False
    logging.warning("SerpApi package not installed. Result fetching will be disabled.")

# Will be imported from app.py when used
# from app import db, Game, SerpApiUsage, get_riga_time

class VolleyballResultFetcher:
    """Handle volleyball result fetching via SerpApi"""

    def __init__(self):
        self.api_key = os.getenv('SERPAPI_API_KEY')
        if not self.api_key:
            logging.warning("SERPAPI_API_KEY environment variable not set")
        self.client = None
        if SERPAPI_AVAILABLE and self.api_key:
            self.client = serpapi.Client(api_key=self.api_key)

    def is_available(self) -> bool:
        """Check if SerpApi is available and configured"""
        return SERPAPI_AVAILABLE and self.api_key is not None and self.client is not None

    def check_monthly_limit(self) -> bool:
        """Check if we're under monthly search limit"""
        if not self.is_available():
            return False

        # Import here to avoid circular imports
        from app import SerpApiUsage

        usage = SerpApiUsage.get_current_month_usage()
        return usage.can_make_search()

    def search_volleyball_result(self, team1: str, team2: str, game_date: datetime) -> Optional[Dict]:
        """Search for volleyball match result using multiple query strategies"""
        if not self.is_available():
            logging.error("SerpApi not available")
            return None

        if not self.check_monthly_limit():
            logging.warning("Monthly SerpApi search limit reached")
            return None

        # Try different query formats
        queries = self._generate_search_queries(team1, team2, game_date)

        for query in queries:
            try:
                logging.info(f"Searching with query: {query}")

                # Make SerpApi search
                response = self.client.search({
                    'engine': 'google',
                    'q': query,
                    'location': 'Philippines',  # Tournament location
                    'hl': 'en',
                    'gl': 'us'
                })

                # Update usage tracking
                self._update_usage_tracking()

                # Try to extract result from response
                result = self._parse_response(response, team1, team2)
                if result:
                    logging.info(f"Found result: {result}")
                    return result

            except Exception as e:
                logging.error(f"SerpApi search failed for query '{query}': {e}")
                continue

        logging.warning(f"No volleyball result found for {team1} vs {team2}")
        return None

    def _generate_search_queries(self, team1: str, team2: str, game_date: datetime) -> list:
        """Generate multiple search query variations"""
        date_str = game_date.strftime('%Y-%m-%d')
        date_readable = game_date.strftime('%B %d, %Y')

        queries = [
            # Specific tournament format
            f'"FIVB Men\'s World Championship 2025" {team1} {team2} result',
            f'"Men\'s World Championship 2025" {team1} vs {team2} volleyball',

            # Date-specific searches
            f'{team1} vs {team2} volleyball {date_str} result',
            f'{team1} {team2} volleyball score {date_readable}',

            # Location-specific
            f'{team1} {team2} volleyball Philippines 2025 result',
            f'{team1} vs {team2} volleyball world championship Philippines',

            # General volleyball result search
            f'{team1} vs {team2} volleyball result September 2025',
            f'volleyball {team1} {team2} final score'
        ]

        return queries

    def _parse_response(self, response: Dict, team1: str, team2: str) -> Optional[Dict]:
        """Parse SerpApi response to extract volleyball score"""

        # Method 1: Check for structured sports results
        if 'sports_results' in response:
            result = self._parse_sports_results(response['sports_results'], team1, team2)
            if result:
                return result

        # Method 2: Parse organic search results
        if 'organic_results' in response:
            result = self._parse_organic_results(response['organic_results'], team1, team2)
            if result:
                return result

        # Method 3: Check answer box
        if 'answer_box' in response:
            result = self._parse_answer_box(response['answer_box'], team1, team2)
            if result:
                return result

        return None

    def _parse_sports_results(self, sports_data: Dict, team1: str, team2: str) -> Optional[Dict]:
        """Parse structured sports results from SerpApi"""
        try:
            # Look for game spotlight with team scores
            if 'game_spotlight' in sports_data:
                spotlight = sports_data['game_spotlight']
                if 'teams' in spotlight:
                    return self._extract_team_scores(spotlight['teams'], team1, team2)

            # Look for other structured score data
            if 'games' in sports_data:
                for game in sports_data['games']:
                    if 'teams' in game:
                        result = self._extract_team_scores(game['teams'], team1, team2)
                        if result:
                            return result

        except Exception as e:
            logging.error(f"Error parsing sports results: {e}")

        return None

    def _parse_organic_results(self, organic_results: list, team1: str, team2: str) -> Optional[Dict]:
        """Parse organic search results for volleyball scores"""
        for result in organic_results:
            # Check title and snippet for volleyball scores
            text_to_check = f"{result.get('title', '')} {result.get('snippet', '')}"
            score = self._extract_score_from_text(text_to_check, team1, team2)
            if score:
                return score

        return None

    def _parse_answer_box(self, answer_box: Dict, team1: str, team2: str) -> Optional[Dict]:
        """Parse answer box for quick volleyball score results"""
        text_to_check = f"{answer_box.get('title', '')} {answer_box.get('snippet', '')}"
        return self._extract_score_from_text(text_to_check, team1, team2)

    def _extract_team_scores(self, teams_data: list, team1: str, team2: str) -> Optional[Dict]:
        """Extract scores from structured team data"""
        if len(teams_data) != 2:
            return None

        try:
            team_scores = {}
            for team_info in teams_data:
                team_name = team_info.get('name', '')
                score = team_info.get('score', {}).get('total', 0)

                # Try to match team names
                if self._is_team_match(team_name, team1):
                    team_scores[team1] = int(score)
                elif self._is_team_match(team_name, team2):
                    team_scores[team2] = int(score)

            if len(team_scores) == 2:
                if self._is_valid_volleyball_score(team_scores[team1], team_scores[team2]):
                    return {
                        'team1_score': team_scores[team1],
                        'team2_score': team_scores[team2],
                        'source': 'serpapi_structured'
                    }

        except (ValueError, KeyError) as e:
            logging.error(f"Error extracting team scores: {e}")

        return None

    def _extract_score_from_text(self, text: str, team1: str, team2: str) -> Optional[Dict]:
        """Extract volleyball score from text using regex patterns"""

        # Volleyball score patterns (3-0, 3-1, 3-2)
        volleyball_patterns = [
            r'(\d)[:\s-]+(\d)',  # Basic score pattern
            r'(\d)\s*[-–]\s*(\d)',  # Score with dashes
            r'(\d)\s*:\s*(\d)',  # Score with colon
        ]

        for pattern in volleyball_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                score1, score2 = int(match.group(1)), int(match.group(2))

                # Check if it's a valid volleyball score
                if self._is_valid_volleyball_score(score1, score2):
                    # Try to determine which team has which score based on context
                    team1_score, team2_score = self._determine_team_scores(
                        text, team1, team2, score1, score2, match.start()
                    )

                    if team1_score is not None and team2_score is not None:
                        return {
                            'team1_score': team1_score,
                            'team2_score': team2_score,
                            'source': 'serpapi_text'
                        }

        return None

    def _is_valid_volleyball_score(self, score1: int, score2: int) -> bool:
        """Check if score represents a valid volleyball match result"""
        # Winner must have 3 sets, loser must have 0-2 sets
        return ((score1 == 3 and score2 in [0, 1, 2]) or
                (score2 == 3 and score1 in [0, 1, 2]))

    def _is_team_match(self, found_name: str, target_name: str) -> bool:
        """Check if found team name matches target team name"""
        if not found_name or not target_name:
            return False

        # Simple fuzzy matching
        found_clean = found_name.lower().strip()
        target_clean = target_name.lower().strip()

        # Exact match
        if found_clean == target_clean:
            return True

        # Contains match
        if target_clean in found_clean or found_clean in target_clean:
            return True

        # Check for common abbreviations/variations
        # This could be expanded with more sophisticated matching
        return False

    def _determine_team_scores(self, text: str, team1: str, team2: str,
                              score1: int, score2: int, match_pos: int) -> Tuple[Optional[int], Optional[int]]:
        """Determine which score belongs to which team based on context"""

        # Look for team names around the score
        context_before = text[max(0, match_pos - 100):match_pos].lower()
        context_after = text[match_pos:match_pos + 100].lower()
        full_context = context_before + context_after

        team1_lower = team1.lower()
        team2_lower = team2.lower()

        # Strategy 1: Look for explicit patterns like "TeamA 3-1 TeamB" or "TeamA beats TeamB 3-1"
        # First try direct team-score pattern matching in wider context
        full_text_lower = text.lower()

        # Try to match pattern: team_name number - team_name number in the full text
        team_score_pattern = rf"({team1_lower}|{team2_lower})\s*(\d+)\s*[-–]\s*({team1_lower}|{team2_lower})\s*(\d+)"
        team_score_match = re.search(team_score_pattern, full_text_lower, re.IGNORECASE)

        if team_score_match:
            first_team = team_score_match.group(1).lower()
            first_score = int(team_score_match.group(2))
            second_team = team_score_match.group(3).lower()
            second_score = int(team_score_match.group(4))

            # Map the scores correctly: return (team1_score, team2_score)
            if first_team == team1_lower and second_team == team2_lower:
                # Pattern: "Team1 X - Team2 Y" -> return (X, Y)
                return first_score, second_score
            elif first_team == team2_lower and second_team == team1_lower:
                # Pattern: "Team2 X - Team1 Y" -> return (Y, X)
                return second_score, first_score

        # Extract the actual score pattern with surrounding text
        score_pattern = f"({score1})[:\\s-]+({score2})"
        score_match = re.search(score_pattern, text[max(0, match_pos - 50):match_pos + 50])

        if score_match:
            # Look for team names immediately before and after the score
            before_score = text[max(0, match_pos - 50):match_pos].lower()
            after_score = text[match_pos:match_pos + 50].lower()

            # Check if team1 appears right before score and team2 after (or vice versa)
            team1_before_distance = before_score.rfind(team1_lower)
            team2_before_distance = before_score.rfind(team2_lower)
            team1_after_distance = after_score.find(team1_lower)
            team2_after_distance = after_score.find(team2_lower)

            # Pattern: "TeamA score1 - TeamB score2" means TeamA gets score1, TeamB gets score2
            if (team1_before_distance >= 0 and team2_after_distance >= 0 and
                (team2_before_distance < 0 or team1_before_distance > team2_before_distance)):
                return score1, score2

            # Pattern: "TeamB score1 - TeamA score2" means TeamB gets score1, TeamA gets score2
            if (team2_before_distance >= 0 and team1_after_distance >= 0 and
                (team1_before_distance < 0 or team2_before_distance > team1_before_distance)):
                return score2, score1


        # Strategy 2: Look for winner indicators combined with scores
        # Check if team1 is mentioned as winner
        team1_winner_patterns = [
            rf"{team1_lower}.*(?:beat|defeat|won|win)",
            rf"(?:beat|defeat|won|win).*{team1_lower}",
            rf"{team1_lower}.*(?:victorious|victory|champion)"
        ]

        # Check if team2 is mentioned as winner
        team2_winner_patterns = [
            rf"{team2_lower}.*(?:beat|defeat|won|win)",
            rf"(?:beat|defeat|won|win).*{team2_lower}",
            rf"{team2_lower}.*(?:victorious|victory|champion)"
        ]

        # Check if team2 is mentioned as loser
        team2_loser_patterns = [
            rf"{team2_lower}.*(?:lost|lose|defeated)",
            rf"(?:lost|lose|defeated).*{team2_lower}"
        ]

        # Check if team1 is mentioned as loser
        team1_loser_patterns = [
            rf"{team1_lower}.*(?:lost|lose|defeated)",
            rf"(?:lost|lose|defeated).*{team1_lower}"
        ]

        team1_is_winner = any(re.search(pattern, full_context, re.IGNORECASE) for pattern in team1_winner_patterns)
        team2_is_winner = any(re.search(pattern, full_context, re.IGNORECASE) for pattern in team2_winner_patterns)
        team1_is_loser = any(re.search(pattern, full_context, re.IGNORECASE) for pattern in team1_loser_patterns)
        team2_is_loser = any(re.search(pattern, full_context, re.IGNORECASE) for pattern in team2_loser_patterns)

        if team1_is_winner or team2_is_loser:
            # team1 won, so they should have the higher score
            return (max(score1, score2), min(score1, score2))
        elif team2_is_winner or team1_is_loser:
            # team2 won, so they should have the higher score
            return (min(score1, score2), max(score1, score2))

        # Strategy 3: Original position-based logic (improved)
        team1_pos = full_context.find(team1_lower)
        team2_pos = full_context.find(team2_lower)

        if team1_pos >= 0 and team2_pos >= 0:
            # Calculate distances from score position (centered in context)
            score_center = len(context_before)
            team1_distance = abs(team1_pos - score_center)
            team2_distance = abs(team2_pos - score_center)

            # The team mentioned closer to the score gets the first score
            if team1_distance < team2_distance:
                return score1, score2
            elif team2_distance < team1_distance:
                return score2, score1
            # If equal distance, use position order
            elif team1_pos < team2_pos:
                return score1, score2
            else:
                return score2, score1

        # Fallback: try to detect which team is the likely winner based on context
        if score1 != score2:  # If scores are different
            higher_score = max(score1, score2)
            lower_score = min(score1, score2)

            # Look for winner context
            if re.search(rf"{team1_lower}.*(win|beat|defeat|victorious)", full_context, re.IGNORECASE):
                return (higher_score, lower_score) if score1 > score2 else (lower_score, higher_score)
            elif re.search(rf"{team2_lower}.*(win|beat|defeat|victorious)", full_context, re.IGNORECASE):
                return (lower_score, higher_score) if score1 > score2 else (higher_score, lower_score)

        # Final fallback - maintain original order but log the uncertainty
        logging.warning(f"Could not determine team score assignment for {team1} vs {team2}, using fallback")
        return score1, score2

    def _update_usage_tracking(self):
        """Update SerpApi usage tracking"""
        try:
            from app import SerpApiUsage
            usage = SerpApiUsage.get_current_month_usage()
            usage.increment_usage()
            logging.info(f"SerpApi usage updated: {usage.searches_used}/{usage.monthly_limit}")
        except Exception as e:
            logging.error(f"Failed to update SerpApi usage tracking: {e}")

# Global instance
result_fetcher = VolleyballResultFetcher()


def search_game_result(game_id: int) -> Optional[Dict]:
    """
    Main function to search for a game result
    Returns dict with team1_score, team2_score, source if found
    """
    try:
        from app import Game

        game = Game.query.get(game_id)
        if not game:
            logging.error(f"Game {game_id} not found")
            return None

        logging.info(f"Searching result for {game.team1} vs {game.team2}")
        return result_fetcher.search_volleyball_result(game.team1, game.team2, game.game_date)

    except Exception as e:
        logging.error(f"Error searching for game {game_id} result: {e}")
        return None


def update_game_with_result(game_id: int, force: bool = False) -> bool:
    """
    Update a game with automatically fetched result
    Returns True if successful, False otherwise
    """
    try:
        from app import db, Game

        game = Game.query.get(game_id)
        if not game:
            logging.error(f"Game {game_id} not found")
            return False

        # Check if already finished (unless forced)
        if game.is_finished and not force:
            logging.info(f"Game {game_id} already finished")
            return True

        # Check if we've already attempted auto-update (unless forced)
        if game.auto_update_attempted and not force:
            logging.info(f"Auto-update already attempted for game {game_id}")
            return False

        # Search for result
        result = search_game_result(game_id)
        if not result:
            # Mark as attempted even if no result found
            game.auto_update_attempted = True
            game.auto_update_timestamp = datetime.utcnow()
            db.session.commit()
            return False

        # Update game with result
        game.team1_score = result['team1_score']
        game.team2_score = result['team2_score']
        game.is_finished = True
        game.result_source = result['source']
        game.serpapi_search_used = True
        game.auto_update_attempted = True
        game.auto_update_timestamp = datetime.utcnow()

        db.session.commit()

        # Recalculate points for all predictions
        from app import Prediction, calculate_points
        predictions = Prediction.query.filter_by(game_id=game_id).all()
        for prediction in predictions:
            prediction.points = calculate_points(prediction, game)

        db.session.commit()

        logging.info(f"Game {game_id} updated with result: {result['team1_score']}-{result['team2_score']}")
        return True

    except Exception as e:
        logging.error(f"Error updating game {game_id} with result: {e}")
        return False


def get_monthly_usage_info() -> Dict:
    """Get current month's SerpApi usage information"""
    try:
        from app import SerpApiUsage
        usage = SerpApiUsage.get_current_month_usage()
        return {
            'month_year': usage.month_year,
            'searches_used': usage.searches_used,
            'monthly_limit': usage.monthly_limit,
            'remaining': usage.monthly_limit - usage.searches_used,
            'last_search': usage.last_search_date,
            'can_search': usage.can_make_search()
        }
    except Exception as e:
        logging.error(f"Error getting usage info: {e}")
        return {
            'month_year': datetime.now().strftime('%Y-%m'),
            'searches_used': 0,
            'monthly_limit': 250,
            'remaining': 250,
            'last_search': None,
            'can_search': False
        }


def test_score_assignment():
    """Test function to verify score assignment logic works correctly"""
    fetcher = VolleyballResultFetcher()

    test_cases = [
        {
            'text': 'Brazil beat Poland 3-1 in volleyball',
            'team1': 'Brazil',
            'team2': 'Poland',
            'score1': 3,
            'score2': 1,
            'expected': (3, 1),
            'description': 'Team1 wins, team1 mentioned first with win context'
        },
        {
            'text': 'Poland lost to Brazil 1-3 in the championship',
            'team1': 'Brazil',
            'team2': 'Poland',
            'score1': 1,
            'score2': 3,
            'expected': (3, 1),
            'description': 'Team1 wins but score order is reversed'
        },
        {
            'text': 'Final score: Poland 1 - Brazil 3',
            'team1': 'Brazil',
            'team2': 'Poland',
            'score1': 1,
            'score2': 3,
            'expected': (3, 1),
            'description': 'Team names around score in opposite order'
        }
    ]

    print("Testing score assignment logic:")
    print("=" * 50)

    for i, case in enumerate(test_cases, 1):
        result = fetcher._determine_team_scores(
            case['text'],
            case['team1'],
            case['team2'],
            case['score1'],
            case['score2'],
            case['text'].find(str(case['score1']))
        )

        status = "✓ PASS" if result == case['expected'] else "✗ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Description: {case['description']}")
        print(f"  Text: '{case['text']}'")
        print(f"  Teams: {case['team1']} vs {case['team2']}")
        print(f"  Input scores: {case['score1']}, {case['score2']}")
        print(f"  Expected: {case['expected']}")
        print(f"  Got: {result}")
        print()

    return True