import logging
import re
import requests
from django.conf import settings
from django.core.cache import cache
from sentence_transformers import SentenceTransformer, util
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from functools import lru_cache, wraps
import uuid
from typing import Optional, Tuple, List
from django.core.exceptions import ImproperlyConfigured

# Configure logging with Django integration
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Cache key prefix for Gemini API
CACHE_PREFIX = "gemini_api_"
CACHE_TIMEOUT = 3600  # 1 hour in seconds

# Singleton for SentenceTransformer with lazy loading
class GraderModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Initializing SentenceTransformer model 'all-MiniLM-L6-v2'...")
            try:
                cls._instance = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("SentenceTransformer model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer model: {str(e)}")
                raise ImproperlyConfigured(f"SentenceTransformer initialization failed: {str(e)}")
        return cls._instance

# Global instance (lazy-loaded)
grader_model = GraderModel()

# Reusable HTTP session with retries and timeout
def get_api_session(retries: int = 3, backoff_factor: float = 1.0, timeout: int = 10) -> requests.Session:
    """Create a reusable HTTP session with configurable retry logic and timeout."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"],
        raise_on_redirect=True,
        raise_on_status=True
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.timeout = timeout
    return session

# Decorator for caching API calls with Django cache
def cache_api_call(timeout=CACHE_TIMEOUT):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{CACHE_PREFIX}{str(uuid.uuid4())}"  # Unique key per call
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__} with args: {args[:2]}...")
                return cached_result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cache miss, stored result for {func.__name__} with args: {args[:2]}...")
            return result
        return wrapper
    return decorator

# Cached Gemini API call with Django cache
@cache_api_call()
def _call_gemini_api(prompt: str, api_key: str) -> str:
    """
    Helper function to make Gemini API requests with caching and error handling.
    
    Args:
        prompt (str): The input prompt for the API.
        api_key (str): The API key for authentication.
    
    Returns:
        str: The API response text.
    
    Raises:
        ValueError: If API key or prompt is invalid.
        requests.RequestException: If the API request fails.
        KeyError: If the API response is malformed.
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("Gemini API key is missing or invalid.")
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt must be a non-empty string.")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    params = {"key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    session = get_api_session()
    try:
        response = session.post(url, params=params, json=payload, headers=headers)
        response.raise_for_status()
        content = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        if not content:
            raise KeyError("No valid content in API response.")
        logger.info(f"API call successful for prompt: {prompt[:50]}...")
        return content
    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}, Status: {getattr(e.response, 'status_code', 'N/A')}")
        raise
    except KeyError as e:
        logger.error(f"Invalid API response format: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in API call: {str(e)}")
        raise

def generate_ai_question(topic: str, difficulty: str, number: int) -> str:
    """
    Generate an AI-generated exam question for a given topic and difficulty without numbering.
    
    Args:
        topic (str): The subject or topic of the question.
        difficulty (str): Difficulty level ('easy', 'medium', 'hard').
        number (int): Question number for internal tracking (not in text).
    
    Returns:
        str: Question text without numbering.
    
    Raises:
        ValueError: If input is invalid.
        Exception: If generation fails.
    """
    if not all([topic, difficulty]) or not isinstance(number, int):
        raise ValueError("Invalid input: topic, difficulty, and number must be provided.")
    if difficulty not in ['easy', 'medium', 'hard']:
        raise ValueError("Difficulty must be 'easy', 'medium', or 'hard'.")

    prompt = f"Generate a {difficulty}-level exam question about {topic} without numbering in the format: [question text]"
    try:
        response = _call_gemini_api(prompt, settings.GEMINI_API_KEY)
        return re.sub(r'^(Question\s+\d+:)\s*', '', response.strip())
    except Exception as e:
        logger.error(f"Failed to generate question for topic {topic}: {str(e)}")
        raise

def generate_ai_answer(topic: str, difficulty: str) -> str:
    """
    Generate a detailed, correct answer for a question on a given topic and difficulty.
    
    Args:
        topic (str): The subject or topic.
        difficulty (str): Difficulty level ('easy', 'medium', 'hard').
    
    Returns:
        str: Detailed correct answer.
    
    Raises:
        ValueError: If input is invalid.
        Exception: If generation fails.
    """
    if not all([topic, difficulty]):
        raise ValueError("Invalid input: topic and difficulty must be provided.")
    if difficulty not in ['easy', 'medium', 'hard']:
        raise ValueError("Difficulty must be 'easy', 'medium', or 'hard'.")

    prompt = f"Provide a detailed, correct answer for a {difficulty}-level exam question about {topic}."
    try:
        return _call_gemini_api(prompt, settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to generate answer for topic {topic}: {str(e)}")
        raise

def generate_feedback(student_answer: str, correct_answer: str) -> str:
    """
    Generate constructive feedback comparing a student's answer to the correct answer.
    
    Args:
        student_answer (str): The student's response.
        correct_answer (str): The expected correct answer.
    
    Returns:
        str: Feedback text, or an error message if generation fails.
    """
    if not student_answer or not correct_answer:
        return "Feedback unavailable: Missing student or correct answer."

    prompt = f"Compare this student answer: '{student_answer}' with the correct answer: '{correct_answer}'. Provide concise, constructive feedback."
    try:
        return _call_gemini_api(prompt, settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to generate feedback: {str(e)}")
        return f"Feedback unavailable due to error: {str(e)}"

def auto_grade_answer(student_answer: str, correct_answer: str, max_marks: int) -> Tuple[int, str]:
    """
    Automatically grade a student's answer with section-wise evaluation based on cosine similarity.
    
    Args:
        student_answer (str): The student's response.
        correct_answer (str): The expected correct answer.
        max_marks (int): Maximum possible score for the question.
    
    Returns:
        tuple: (score: int, feedback: str) with detailed scoring breakdown.
    
    Raises:
        ValueError: If input parameters are invalid.
        Exception: If grading process fails.
    """
    if not isinstance(student_answer, str) or not student_answer.strip():
        return 0, "No valid answer provided."
    if not isinstance(correct_answer, str) or not correct_answer.strip():
        return 0, "No valid correct answer provided."
    if not isinstance(max_marks, (int, float)) or max_marks <= 0:
        raise ValueError("max_marks must be a positive number.")

    try:
        # Split answers into sections
        def split_into_sections(text: str) -> List[str]:
            sections = []
            current_section = ""
            for line in text.split('\n'):
                stripped_line = line.strip()
                if stripped_line and any(stripped_line.startswith(marker) for marker in ['a)', 'b)', 'c)', '1.', '2.', '3.', '**a)', '**b)', '**c)']):
                    if current_section:
                        sections.append(current_section.strip())
                    current_section = stripped_line
                else:
                    current_section += "\n" + line
            if current_section.strip():
                sections.append(current_section.strip())
            return sections if sections else [text.strip()]

        student_sections = split_into_sections(student_answer)
        correct_sections = split_into_sections(correct_answer)
        num_sections = max(len(correct_sections), 1)

        # Allocate marks per section
        marks_per_section = max_marks / num_sections
        total_score = 0
        feedback_parts = []

        # Grade each section with enhanced logic
        for i, correct_section in enumerate(correct_sections, start=1):
            student_section = student_sections[i-1] if i-1 < len(student_sections) else ""
            if not student_section:
                feedback_parts.append(f"Section {i}: Missing (0/{marks_per_section:.1f} marks).")
                continue

            student_embedding = grader_model.encode(student_section, convert_to_tensor=True)
            correct_embedding = grader_model.encode(correct_section, convert_to_tensor=True)
            similarity = util.cos_sim(student_embedding, correct_embedding).item()
            normalized_similarity = max(0, min((similarity + 1) / 2, 1))  # Normalize to 0-1

            threshold = 0.6
            section_score = 0
            if normalized_similarity >= threshold:
                score_range = 1.0 - threshold
                scaled_similarity = (normalized_similarity - threshold) / score_range if score_range > 0 else 0
                section_score = min(marks_per_section * scaled_similarity, marks_per_section)
                feedback = "Excellent" if scaled_similarity >= 0.9 else "Good" if scaled_similarity >= 0.75 else "Needs improvement"
                feedback_parts.append(f"Section {i}: {feedback} ({section_score:.1f}/{marks_per_section:.1f} marks).")
            else:
                feedback_parts.append(f"Section {i}: Incorrect (0/{marks_per_section:.1f} marks).")
            total_score += section_score
            logger.debug(f"Section {i} - Similarity: {normalized_similarity:.2f}, Score: {section_score:.1f}/{marks_per_section:.1f}")

        # Handle extra student sections
        extra_sections = len(student_sections) - len(correct_sections)
        if extra_sections > 0:
            feedback_parts.append(f"Extra {extra_sections} section(s) provided; not graded.")

        total_score = int(round(total_score))
        feedback = "\n".join(feedback_parts) if feedback_parts else "Answer evaluated, but no specific feedback generated."
        logger.info(f"Auto-graded - Score: {total_score}/{max_marks}, Sections: {num_sections}")
        return total_score, feedback

    except Exception as e:
        logger.error(f"Auto-grading failed: {str(e)}")
        raise