"""Voting logic service."""
import random
from typing import List, Dict, Tuple, Optional


def determine_winner(vote_counts: Dict[int, int]) -> Tuple[Optional[List[int]], bool]:
    """Determine winner(s) from vote counts.
    
    Args:
        vote_counts: Dictionary mapping movie_id to vote count
        
    Returns:
        Tuple of (winner_ids, is_tie):
        - winner_ids: List of movie IDs with max votes, or None if no candidates
        - is_tie: True if there's a meaningful tie (multiple winners with >0 votes)
        
    When nobody voted (all counts are zero), a random candidate is picked
    instead of declaring a tie — this prevents a deadlock when not all
    members participate in the vote.

    Examples:
        {1: 5, 2: 3, 3: 2} -> ([1], False)   # movie 1 wins
        {1: 5, 2: 5, 3: 2} -> ([1, 2], True)  # tie between 1 and 2
        {1: 0, 2: 0}       -> ([<random>], False)  # no votes — random pick
        {}                  -> (None, False)    # no candidates
    """
    if not vote_counts:
        return None, False

    max_votes = max(vote_counts.values())

    # Nobody voted — pick a random candidate instead of declaring a tie
    if max_votes == 0:
        random_winner = random.choice(list(vote_counts.keys()))
        return [random_winner], False

    winners = [movie_id for movie_id, votes in vote_counts.items() if votes == max_votes]

    is_tie = len(winners) > 1

    return winners, is_tie


def format_vote_results(
    movie_data: List[Dict],
    vote_counts: Dict[int, int]
) -> str:
    """Format voting results for display.
    
    Args:
        movie_data: List of dictionaries with movie info (id, title, year, proposer)
        vote_counts: Dictionary mapping movie_id to vote count
        
    Returns:
        Formatted string with results
    """
    if not movie_data:
        return "Нет фильмов для голосования"
    
    # Sort movies by votes (descending)
    sorted_movies = sorted(
        movie_data,
        key=lambda x: vote_counts.get(x['id'], 0),
        reverse=True
    )
    
    lines = []
    for movie in sorted_movies:
        movie_id = movie['id']
        votes = vote_counts.get(movie_id, 0)
        title = movie.get('title', 'Без названия')
        year = movie.get('year', '')
        proposer = movie.get('proposer', '')
        
        year_str = f" ({year})" if year else ""
        vote_word = "голос" if votes % 10 == 1 and votes % 100 != 11 else \
                    "голоса" if votes % 10 in [2, 3, 4] and votes % 100 not in [12, 13, 14] else \
                    "голосов"
        
        line = f"🎬 {title}{year_str} — {votes} {vote_word}"
        if proposer:
            line += f"\nПредложил: {proposer}"
        lines.append(line)
    
    return "\n\n".join(lines)


def calculate_average_rating(ratings: List[int]) -> float:
    """Calculate average rating rounded to 2 decimal places.
    
    Args:
        ratings: List of integer ratings (1-10)
        
    Returns:
        Average rating rounded to 2 decimal places
        
    Examples:
        [8, 9, 7] -> 8.00
        [8, 9, 7, 10] -> 8.50
    """
    if not ratings:
        return 0.0
    
    return round(sum(ratings) / len(ratings), 2)
