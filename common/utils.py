import requests
from django.conf import settings
from sentence_transformers import SentenceTransformer, util
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize SentenceTransformer model
grader_model = SentenceTransformer('all-MiniLM-L6-v2')

# reusable HTTP session with retries
def get_api_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session

# Cache API responses to reduce redundant calls
@lru_cache(maxsize=100)
def _call_gemini_api(prompt):
    """Helper function to make Gemini API requests."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    params = {"key": settings.GEMINI_API_KEY}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        session = get_api_session()
        response = session.post(url, params=params, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        logger.info(f"API call successful for prompt: {prompt[:50]}...")
        return content
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise Exception(f"API request failed: {str(e)}")

def generate_ai_question(topic, difficulty, number):
    """
    Generate an AI-generated exam question for a given topic and difficulty.
    
    Args:
        topic (str): The subject or topic of the question.
        difficulty (str): Difficulty level ('easy', 'medium', 'hard').
        number (int): Question number for formatting.
    
    Returns:
        str: Formatted question text.
    """
    prompt = f"Generate a {difficulty}-level exam question numbered {number} about {topic} in the format: Question {number}: [question text]"
    try:
        return _call_gemini_api(prompt)
    except Exception as e:
        raise Exception(f"Failed to generate question: {str(e)}")

def generate_ai_answer(topic, difficulty):
    """
    Generate a detailed, correct answer for a question on a given topic and difficulty.
    
    Args:
        topic (str): The subject or topic.
        difficulty (str): Difficulty level ('easy', 'medium', 'hard').
    
    Returns:
        str: Detailed correct answer.
    """
    prompt = f"Provide a detailed, correct answer for a {difficulty}-level exam question about {topic}."
    try:
        return _call_gemini_api(prompt)
    except Exception as e:
        raise Exception(f"Failed to generate answer: {str(e)}")

def generate_feedback(student_answer, correct_answer):
    """
    Generate constructive feedback comparing a student's answer to the correct answer.
    
    Args:
        student_answer (str): The student's response.
        correct_answer (str): The expected correct answer.
    
    Returns:
        str: Feedback text, or an error message if API fails.
    """
    prompt = f"Compare this student answer: '{student_answer}' with the correct answer: '{correct_answer}'. Provide concise, constructive feedback."
    try:
        return _call_gemini_api(prompt)
    except Exception as e:
        return f"Feedback unavailable due to API error: {str(e)}"


import logging
from sentence_transformers import SentenceTransformer, util

grader_model = SentenceTransformer('all-MiniLM-L6-v2')
logger = logging.getLogger(__name__)

def auto_grade_answer(student_answer, correct_answer, max_marks):
    """
    Automatically grade a student's answer with section-wise evaluation based on cosine similarity.
    
    Args:
        student_answer (str): The student's response.
        correct_answer (str): The expected correct answer.
        max_marks (int): Maximum possible score for the question.
    
    Returns:
        tuple: (score: int, feedback: str) with detailed scoring breakdown.
    
    Raises:
        Exception: If encoding or grading fails.
    """
    try:
        # Input validation
        if not student_answer or not isinstance(student_answer, str):
            return 0, "No answer provided."
        if not correct_answer or not isinstance(correct_answer, str):
            return 0, "Correct answer is missing or invalid."

        # Split answers into sections based on common markers (e.g., "a)", "b)", "c)")
        def split_into_sections(text):
            sections = []
            current_section = ""
            for line in text.split('\n'):
                if line.strip().startswith(('a)', 'b)', 'c)', '**a)', '**b)', '**c)')):
                    if current_section:
                        sections.append(current_section.strip())
                    current_section = line
                else:
                    current_section += "\n" + line
            if current_section:
                sections.append(current_section.strip())
            return sections

        student_sections = split_into_sections(student_answer)
        correct_sections = split_into_sections(correct_answer)
        num_sections = max(len(correct_sections), 1)  # Avoid division by zero

        # Allocate marks per section
        marks_per_section = max_marks / num_sections
        total_score = 0
        feedback_parts = []

        # Grade each section
        for i, correct_section in enumerate(correct_sections):
            student_section = student_sections[i] if i < len(student_sections) else ""
            if not student_section:
                feedback_parts.append(f"Part {chr(97+i)}: Missing (0/{marks_per_section:.1f}).")
                continue

            # Encode and compute similarity
            student_embedding = grader_model.encode(student_section, convert_to_tensor=True)
            correct_embedding = grader_model.encode(correct_section, convert_to_tensor=True)
            similarity = util.cos_sim(student_embedding, correct_embedding).item()
            normalized_similarity = max(0, min((similarity + 1) / 2, 1))  # 0 to 1

            # Lower threshold to 0.6 for partial credit, scale from 0.6 to 1.0
            threshold = 0.6
            if normalized_similarity >= threshold:
                score_range = 1.0 - threshold
                scaled_similarity = (normalized_similarity - threshold) / score_range
                section_score = min(marks_per_section * scaled_similarity, marks_per_section)
                total_score += section_score
                if scaled_similarity >= 0.9:
                    feedback_parts.append(f"Part {chr(97+i)}: Excellent ({section_score:.1f}/{marks_per_section:.1f}).")
                elif scaled_similarity >= 0.75:
                    feedback_parts.append(f"Part {chr(97+i)}: Good ({section_score:.1f}/{marks_per_section:.1f}).")
                else:
                    feedback_parts.append(f"Part {chr(97+i)}: Partial credit ({section_score:.1f}/{marks_per_section:.1f}).")
            else:
                feedback_parts.append(f"Part {chr(97+i)}: Incorrect ({0}/{marks_per_section:.1f}).")
            logger.info(f"Section {chr(97+i)} - Similarity: {normalized_similarity:.2f}, Score: {section_score:.1f}/{marks_per_section:.1f}")

        # Round total score to nearest integer
        total_score = int(round(total_score))
        feedback = " ".join(feedback_parts) if feedback_parts else "Answer evaluated but no specific feedback generated."

        logger.info(f"Final grade - Score: {total_score}/{max_marks}, Sections evaluated: {num_sections}")
        return total_score, feedback

    except Exception as e:
        logger.error(f"Auto-grading failed: {str(e)}")
        raise Exception(f"Auto-grading failed: {str(e)}")