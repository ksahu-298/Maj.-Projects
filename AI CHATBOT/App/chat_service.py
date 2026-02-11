"""Chat service with AI and fallback responses for mental health support."""
import random
import re
from app.config import OPENAI_API_KEY, GROQ_API_KEY

# System prompt for any AI provider
SAGE_SYSTEM_PROMPT = (
    "You are Sage, a compassionate AI assistant that helps users cope with "
    "depression, anxiety, stress, and other mental health challenges. "
    "You are empathetic, supportive, and non-judgmental. You listen actively "
    "and offer gentle encouragement. Keep responses concise (2-4 short paragraphs). "
    "You never diagnose or prescribe. You encourage professional help when appropriate. "
    "If someone mentions suicide or self-harm, acknowledge their pain and "
    "encourage them to contact a crisis helpline immediately."
)

# Empathetic fallback responses (used when no API key is set)
EMPATHETIC_RESPONSES = {
    "depression": [
        "I hear you, and what you're feeling is valid. Depression can make everything feel heavy. "
        "Remember, you don't have to face this alone. Have you considered reaching out to a trusted friend or professional?",
        "That sounds really difficult. It takes courage to open up about what you're going through. "
        "Small steps matter—even getting through today is an achievement. Be gentle with yourself.",
        "Thank you for sharing. Depression can feel isolating, but many people understand what you're experiencing. "
        "Consider talking to a counselor or therapist who can provide professional support.",
        "What you're describing is hard to carry. You matter, and your feelings are real. "
        "Sometimes the bravest thing is to ask for help. Would you feel able to reach out to someone today?",
        "I'm glad you're here. It's okay to not be okay. "
        "Many people find that small routines—getting outside, a short walk, or a phone call—can help a little. What feels possible for you right now?",
    ],
    "anxiety": [
        "I understand how overwhelming anxiety can feel. Your feelings are valid. "
        "Have you tried grounding techniques like the 5-4-3-2-1 method? Notice 5 things you see, 4 you hear, 3 you touch, 2 you smell, 1 you taste.",
        "Anxiety can make everything feel urgent. Remember to breathe—slow, deep breaths can help calm your nervous system. "
        "You're not alone in this. Many find relief through therapy, mindfulness, or talking to someone they trust.",
        "What you're experiencing is real and challenging. It's okay to take things one moment at a time. "
        "Would it help to focus on something simple right now, like your breathing?",
        "I hear you. When anxiety spikes, it can feel like too much. "
        "Try naming what you see around you or feeling your feet on the ground. You're safe in this moment.",
    ],
    "stress": [
        "Stress can feel overwhelming when it builds up. It's important to take breaks when you can. "
        "Going for a short walk, listening to music, or doing something you enjoy can help reset your mind.",
        "You're carrying a lot right now. Remember that it's okay to ask for help or say no to things that feel like too much. "
        "Prioritizing your wellbeing isn't selfish—it's necessary.",
        "Stress takes a real toll. What's one small thing you could do today to give yourself a moment of rest? "
        "Even 5 minutes of quiet can make a difference.",
        "It sounds like a lot is on your plate. You don't have to do everything at once. "
        "What's one thing you could set aside or delegate, even just for today?",
    ],
    "loneliness": [
        "Feeling lonely is difficult, and it's more common than many people realize. "
        "Even small connections—a text, a call, or joining an online community—can help.",
        "Loneliness can make us feel invisible. But you matter. "
        "Consider reaching out to someone today, even if it feels hard. They might be glad you did.",
        "You're not alone in feeling alone. Many people struggle with this. "
        "Support groups, hobby clubs, or volunteering can be ways to build meaningful connections.",
        "Connection doesn't have to be big. A short message, a wave to a neighbour, or a walk in a park can remind us we're part of the world. "
        "Is there one person or place you could reach out to this week?",
    ],
    "sleep": [
        "Sleep and mood are closely linked. Struggling to sleep can make everything feel harder. "
        "A consistent bedtime, limiting screens before bed, and a calm routine can help. If it persists, a doctor can help rule out sleep issues.",
        "Not sleeping well is exhausting and can affect how you feel during the day. "
        "Try to keep a regular schedule and avoid caffeine late in the day. You're not alone in this.",
    ],
    "anger": [
        "Anger can be a way our mind and body respond to stress or hurt. It's valid to feel it. "
        "Taking a pause, stepping away, or writing it out can sometimes help before we respond.",
        "Feeling angry doesn't make you a bad person. It often means something matters to you or something feels unfair. "
        "If you can, give yourself a moment before reacting. You deserve that space.",
    ],
    "general": [
        "I'm here to listen. Whatever you're going through, your feelings matter. "
        "Would you like to tell me more about what's on your mind?",
        "Thank you for reaching out. It takes strength to acknowledge when you're struggling. "
        "Remember, seeking support is a sign of courage, not weakness.",
        "I hear you. Mental health challenges are real and valid. "
        "If things feel overwhelming, please consider speaking with a mental health professional—they're trained to help.",
        "You're not alone. Many people have walked similar paths and found their way through. "
        "What would feel helpful to talk about right now?",
        "Whatever you're feeling, it's okay to feel it. "
        "Take your time. I'm here when you want to share more.",
    ],
}

# Crisis keywords - always include helpline info
CRISIS_KEYWORDS = ["suicide", "suicidal", "kill myself", "end my life", "want to die", "self-harm", "hurt myself"]

# India mental health helplines (24/7, toll-free)
CRISIS_MESSAGE = (
    "I'm concerned about what you've shared. If you're in crisis, please reach out immediately. "
    "India helplines (24/7, toll-free): "
    "Tele-MANAS: 14416 or 1800-89-14416 | "
    "Hello! Lifeline: 1800-121-3667 | "
    "KIRAN: 1800-599-0019 | "
    "Vandrevala Foundation: 1860-2662-345 / 1800-2333-330"
)

# Reflection prefixes to make fallback feel more personal
REFLECTION_PREFIXES = [
    "You shared that {} — ",
    "It sounds like {} — ",
    "Hearing that {} — ",
]


def _detect_topic(message: str) -> str:
    """Detect the primary topic from user message."""
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in ["depress", "sad", "hopeless", "empty", "worthless", "down", "low"]):
        return "depression"
    if any(kw in msg_lower for kw in ["anxious", "anxiety", "panic", "worry", "worried", "nervous", "scared"]):
        return "anxiety"
    if any(kw in msg_lower for kw in ["stress", "stressed", "overwhelm", "pressure", "busy", "tired"]):
        return "stress"
    if any(kw in msg_lower for kw in ["lonely", "alone", "isolat", "disconnect", "no one", "friend"]):
        return "loneliness"
    if any(kw in msg_lower for kw in ["sleep", "insomnia", "tired", "exhausted", "can't sleep"]):
        return "sleep"
    if any(kw in msg_lower for kw in ["angry", "anger", "frustrat", "irritat", "mad"]):
        return "anger"
    return "general"


def _short_reflection(message: str, max_words: int = 8) -> str | None:
    """Extract a short phrase from the message for reflection (e.g. 'you've been feeling low')."""
    message = message.strip()
    if len(message) < 10:
        return None
    # Take first sentence or first max_words words
    first = re.split(r"[.!?]", message)[0].strip()
    words = first.split()[:max_words]
    if len(words) < 2:
        return None
    return " ".join(words).lower()


def _is_crisis(message: str) -> bool:
    """Check if message contains crisis-related content."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in CRISIS_KEYWORDS)


async def _openai_response(message: str) -> str | None:
    """Get response from OpenAI if API key is configured."""
    if not OPENAI_API_KEY:
        return None
    try:
        import httpx  # type: ignore[import-untyped]
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": SAGE_SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


async def _groq_response(message: str) -> str | None:
    """Get response from Groq (free tier) if API key is configured."""
    if not GROQ_API_KEY:
        return None
    try:
        import httpx  # type: ignore[import-untyped]
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": SAGE_SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


async def get_ai_response(message: str) -> str | None:
    """Try OpenAI first, then Groq. Returns None if no key or on error."""
    result = await _openai_response(message)
    if result:
        return result
    return await _groq_response(message)


def _fallback_response(message: str) -> tuple[str, list[str]]:
    """Build a rich fallback response when no API key is available."""
    topic = _detect_topic(message)
    responses = EMPATHETIC_RESPONSES.get(topic, EMPATHETIC_RESPONSES["general"])
    base = random.choice(responses)
    reflection = _short_reflection(message)
    if reflection and random.random() < 0.5:
        prefix = random.choice(REFLECTION_PREFIXES).format(reflection)
        response = prefix + base
    else:
        response = base

    suggestions_map = {
        "depression": ["Talk about what helps", "I want to try therapy", "Coping strategies"],
        "anxiety": ["Breathing exercises", "Grounding techniques", "When to see a professional"],
        "stress": ["Stress management tips", "Setting boundaries", "Self-care ideas"],
        "loneliness": ["Building connections", "Online communities", "Volunteering"],
        "sleep": ["Sleep routine tips", "When to see a doctor", "Relaxation before bed"],
        "anger": ["Managing anger", "Safe ways to express", "When to get support"],
        "general": ["Tell me more", "I need resources", "Crisis support"],
    }
    suggestions = suggestions_map.get(topic, suggestions_map["general"])
    return response, suggestions


async def get_chat_response(message: str) -> tuple[str, list[str]]:
    """Get response for user message. Returns (response_text, suggestions)."""
    if _is_crisis(message):
        return CRISIS_MESSAGE, ["Call Tele-MANAS 14416", "Call KIRAN 1800-599-0019", "Reach out to someone you trust"]

    ai_response = await get_ai_response(message)
    if ai_response:
        suggestions = ["Tell me more", "What coping strategies help?", "I need professional help"]
        return ai_response, suggestions

    return _fallback_response(message)
