from youtubesearchpython import VideosSearch
import re
from datetime import datetime
from difflib import SequenceMatcher

def parse_view_count(view_text):
    """
    Convert view count text to integer
    Examples: "1.2M views" -> 1200000, "10K views" -> 10000
    """
    if not view_text or view_text == 'N/A':
        return 0
    
    view_text = view_text.lower().replace('views', '').replace(',', '').strip()
    
    try:
        if 'k' in view_text:
            return int(float(view_text.replace('k', '')) * 1000)
        elif 'm' in view_text:
            return int(float(view_text.replace('m', '')) * 1000000)
        elif 'b' in view_text:
            return int(float(view_text.replace('b', '')) * 1000000000)
        else:
            return int(float(view_text))
    except:
        return 0

def parse_published_time(published_text):
    """
    Convert published time to recency score
    More recent = higher score
    """
    if not published_text or published_text == 'N/A':
        return 0
    
    published_lower = published_text.lower()
    
    try:
        if 'hour' in published_lower or 'minute' in published_lower:
            return 100  # Very recent
        elif 'day' in published_lower:
            days = int(re.findall(r'\d+', published_text)[0])
            return max(0, 90 - days)
        elif 'week' in published_lower:
            weeks = int(re.findall(r'\d+', published_text)[0])
            return max(0, 80 - (weeks * 2))
        elif 'month' in published_lower:
            months = int(re.findall(r'\d+', published_text)[0])
            return max(0, 60 - (months * 3))
        elif 'year' in published_lower:
            years = int(re.findall(r'\d+', published_text)[0])
            return max(0, 40 - (years * 10))
    except:
        pass
    
    return 20  # Default for old content

def calculate_text_similarity(text1, text2):
    """
    Calculate similarity between two text strings (0-1)
    """
    if not text1 or not text2:
        return 0
    
    text1 = text1.lower()
    text2 = text2.lower()
    
    # Direct substring match bonus
    if text2 in text1 or text1 in text2:
        return 1.0
    
    # Word overlap
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 or not words2:
        return 0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    # Jaccard similarity
    jaccard = len(intersection) / len(union) if union else 0
    
    # Sequence matching
    sequence = SequenceMatcher(None, text1, text2).ratio()
    
    # Combine both metrics
    return (jaccard * 0.6) + (sequence * 0.4)

def calculate_relevance_score(video, query):
    """
    Calculate relevance score based on multiple factors
    
    Factors:
    - Title similarity (50% weight)
    - Description similarity (20% weight)
    - View count popularity (20% weight)
    - Recency (10% weight)
    """
    # Title similarity (most important)
    title_similarity = calculate_text_similarity(video['title'], query)
    title_score = title_similarity * 50
    
    # Description similarity
    description_similarity = calculate_text_similarity(video['description'], query)
    description_score = description_similarity * 20
    
    # View count (normalized, logarithmic scale for fairness)
    view_count = video['views_count']
    if view_count > 0:
        # Normalize views on log scale (max around 100M views = score of 20)
        import math
        view_score = min(20, (math.log10(view_count) / 8) * 20)
    else:
        view_score = 0
    
    # Recency score
    recency_score = parse_published_time(video['published']) * 0.1
    
    # Total score
    total_score = title_score + description_score + view_score + recency_score
    
    return total_score

def fetch_most_relevant_youtube_video(query, search_limit=15):
    """
    Search YouTube and return the most RELEVANT video based on query
    
    Args:
        query: Search query string
        search_limit: Number of results to fetch before scoring (default 15)
    
    Returns:
        Dictionary containing the most relevant video info, or None if no results
    """
    try:
        # Search for videos
        videos_search = VideosSearch(query, limit=search_limit)
        results = videos_search.result()
        
        if not results.get('result'):
            return None
        
        # Extract and enrich video information
        videos = []
        for video in results['result']:
            view_text = video.get('viewCount', {}).get('text', 'N/A')
            
            # Extract description snippet
            description_snippets = video.get('descriptionSnippet', [])
            description = ' '.join([snippet.get('text', '') for snippet in description_snippets]) if description_snippets else ''
            
            video_info = {
                'title': video.get('title', 'N/A'),
                'url': video.get('link', 'N/A'),
                'video_id': video.get('id', 'N/A'),
                'duration': video.get('duration', 'N/A'),
                'views_text': view_text,
                'views_count': parse_view_count(view_text),
                'published': video.get('publishedTime', 'N/A'),
                'channel': video.get('channel', {}).get('name', 'N/A'),
                'thumbnail': video.get('thumbnails', [{}])[0].get('url', 'N/A'),
                'description': description
            }
            
            # Calculate relevance score
            video_info['relevance_score'] = calculate_relevance_score(video_info, query)
            
            videos.append(video_info)
        
        # Sort by relevance score (descending) and return top 1
        most_relevant = sorted(videos, key=lambda x: x['relevance_score'], reverse=True)[0]
        
        return most_relevant
    
    except Exception as e:
        print(f"Error fetching YouTube videos: {e}")
        return None

# Example usage
if __name__ == "__main__":
    query = input("Enter your search query: ")
    top_video = fetch_most_relevant_youtube_video(query, search_limit=15)
    
    if top_video:
        print(f"\n🎯 MOST RELEVANT VIDEO:\n")
        print(f"Title: {top_video['title']}")
        print(f"URL: {top_video['url']}")
        print(f"Channel: {top_video['channel']}")
        print(f"Views: {top_video['views_text']}")
        print(f"Duration: {top_video['duration']}")
        print(f"Published: {top_video['published']}")
        print(f"Relevance Score: {top_video['relevance_score']:.2f}/100")
        if top_video['description']:
            print(f"\nDescription: {top_video['description'][:200]}...")
    else:
        print("No videos found.")