"""
AI Assistant Service Module

Leverages the Google Gemini GenAI SDK to generate, optimize, and classify social media posts.
Implements a smart local mock mode when API credentials are absent.
"""

import os
import re
import random
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


class AIAssistant:
    """SMM AI assistant utilizing Google Gemini or a rules-based mock engine."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Read from environment variables if not provided
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        
        self.is_mock = False
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY":
            self.is_mock = True
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.is_mock = True
                self.client = None

    def generate_post(self, topic: str, tone: str, platform: str) -> str:
        """
        Generates a social post based on a topic, tone, and platform.
        """
        tone = tone.lower().strip()
        platform = platform.lower().strip()
        
        if self.is_mock:
            return self._mock_generate_post(topic, tone, platform)

        prompt = (
            f"Write a social media post for {platform} about the following topic: '{topic}'.\n"
            f"The tone of the post must be '{tone}'.\n"
            f"Follow these platform constraints:\n"
            f"- For twitter: limit output to less than 270 characters, write a short punchy tweet.\n"
            f"- For linkedin: write a professional post, use line breaks, structure, and professional tone.\n"
            f"- For instagram: write a highly engaging caption, include space for hashtags.\n"
            f"Provide ONLY the post content, no explanations or introductory phrases."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=500
                )
            )
            return response.text.strip()
        except Exception as e:
            # Fallback to mock on connection error
            return f"[API Error - Mock Fallback] {self._mock_generate_post(topic, tone, platform)}"

    def optimize_post(self, content: str, platform: str) -> str:
        """
        Optimizes a post for a platform (e.g. adds hashtags, formatting, truncates if too long).
        """
        platform = platform.lower().strip()
        
        if self.is_mock:
            return self._mock_optimize_post(content, platform)

        prompt = (
            f"Optimize the following social post for the {platform} platform:\n"
            f"'{content}'\n"
            f"For Twitter/X, shorten to fit the 280 character limit if it exceeds it. Add 1-2 hashtags.\n"
            f"For LinkedIn, add professional spacing and formatting. Add 3 relevant hashtags.\n"
            f"For Instagram, add emoji formatting and a block of 5-8 relevant hashtags.\n"
            f"Return ONLY the optimized content, no other text."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text.strip()
        except Exception:
            return self._mock_optimize_post(content, platform)

    def analyze_post(self, content: str) -> Dict[str, Any]:
        """
        Performs sentiment analysis, spam risk analysis, and safety scanning.
        """
        if self.is_mock:
            return self._mock_analyze_post(content)

        prompt = (
            f"Analyze the following social media post:\n"
            f"'{content}'\n"
            f"Determine:\n"
            f"1. Sentiment (Positive, Negative, Neutral)\n"
            f"2. Spam Risk Score (0.0 to 1.0, where 1.0 is high spam risk)\n"
            f"3. Policy Violation (Yes/No)\n"
            f"Provide the analysis in JSON format with keys: 'sentiment', 'spam_risk', 'policy_violation', 'reason'."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text.strip())
            return {
                "sentiment": data.get("sentiment", "Neutral"),
                "spam_risk": float(data.get("spam_risk", 0.1)),
                "policy_violation": data.get("policy_violation", "No") == "Yes",
                "reason": data.get("reason", "Analysis successful.")
            }
        except Exception:
            return self._mock_analyze_post(content)

    # =====================================================================
    # Mock AI Fallbacks
    # =====================================================================

    def _mock_generate_post(self, topic: str, tone: str, platform: str) -> str:
        # Templates based on platform and tone
        if platform == "twitter":
            if tone == "witty":
                templates = [
                    f"Just spent way too long thinking about {topic}. Honestly? 10/10, no notes. 😂🔥 #opinion #mindblown",
                    f"Hot take on {topic}: It's either the best thing ever or the most misunderstood. Let's debate. 👇",
                    f"Me: I don't care about {topic}.\nAlso me after 5 seconds: here is a 12-page research essay on it. 📈"
                ]
            elif tone == "professional":
                templates = [
                    f"Analyzing the key developments in {topic}. Understanding these trends is crucial for strategy. #Business #Analysis",
                    f"Recent insights suggest that {topic} is driving significant changes in our industry. What is your perspective? #Growth",
                    f"Efficiency and foresight are essential when navigating {topic}. Here is a quick summary of the path forward."
                ]
            else:  # Bold / Educational
                templates = [
                    f"Stop scrolling. If you are not paying attention to {topic}, you are already behind. Period. 🚀",
                    f"Quick lesson on {topic}: Focus on quality, measure progress, and iterate fast. Thank me later. 📚",
                    f"Here is why {topic} is going to dominate the next decade. Be ready for the shift. #Innovation"
                ]
            return random.choice(templates)
        
        elif platform == "linkedin":
            intro = f"I have been thinking a lot about **{topic}** recently."
            if tone == "professional":
                body = (
                    "In today's fast-paced corporate environment, success belongs to those who understand the core pillars of execution. "
                    "By aligning organizational capabilities with strategic intent, we unlock sustainable growth."
                )
                footer = "What strategies is your organization implementing to address this? #Leadership #BusinessGrowth #Strategy"
            elif tone == "witty":
                body = (
                    "If we are being honest, most of us are trying to figure this out as we go. "
                    "However, sometimes the best strategy is simply starting. Perfection is the enemy of progress, especially in marketing."
                )
                footer = "Agree? Let me know your thoughts in the comments. #CorporateLife #Innovation #Mindset"
            else:  # Bold / Educational
                body = (
                    "Here are three things you need to remember:\n"
                    "1. Quality always wins over volume.\n"
                    "2. Feedback loops are your secret superpower.\n"
                    "3. Continuous learning is non-negotiable."
                )
                footer = "Don't wait for the right moment—create it. #Execution #GrowthMindset #Success"
            return f"{intro}\n\n{body}\n\n{footer}"
        
        else: # Instagram
            emojis = ["✨", "📸", "💡", "🎯", "🙌"]
            selected_emoji = random.choice(emojis)
            if tone == "witty":
                caption = f"Current mood: obsessed with {topic}. {selected_emoji} Seriously, can we talk about this? It's a game changer."
            elif tone == "professional":
                caption = f"Delivering excellence in {topic}. {selected_emoji} A closer look at the workflow, discipline, and metrics that build results."
            else:
                caption = f"Building the future of {topic}, one day at a time. {selected_emoji} Trust the process, execute daily, and watch the results compound."
            
            hashtags = "\n\n.\n.\n#marketing #motivation #growth #workspace #instadaily #creativelife"
            return caption + hashtags

    def _mock_optimize_post(self, content: str, platform: str) -> str:
        # Strip existing hashtags for clean formatting
        cleaned = re.sub(r"#\w+", "", content).strip()
        
        if platform == "twitter":
            # Truncate to 260 to fit tags
            if len(cleaned) > 260:
                cleaned = cleaned[:257] + "..."
            return f"{cleaned} #marketing #info"
        elif platform == "linkedin":
            return f"{cleaned}\n\n#ProfessionalNetwork #BusinessInsights #Innovation"
        else: # Instagram
            return f"✨ {cleaned} ✨\n\n#InstaStyle #GrowthMindset #SMM #SaaS"

    def _mock_analyze_post(self, content: str) -> Dict[str, Any]:
        # Count words and characters
        word_count = len(content.split())
        char_count = len(content)
        
        # Determine mock sentiment based on keyword matches
        content_lower = content.lower()
        positive_words = {"great", "awesome", "excel", "success", "growth", "win", "happy", "love", "best", "😂", "🔥", "🚀"}
        negative_words = {"bad", "fail", "slow", "waste", "behind", "error", "risk", "hazard", "threat"}
        
        pos_hits = sum(1 for w in positive_words if w in content_lower)
        neg_hits = sum(1 for w in negative_words if w in content_lower)
        
        if pos_hits > neg_hits:
            sentiment = "Positive"
        elif neg_hits > pos_hits:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        # Determine spam risk
        spam_score = 0.05
        # Caps lock spam
        caps_words = sum(1 for w in content.split() if w.isupper() and len(w) > 1)
        if caps_words > 2:
            spam_score += 0.3
        # Excessive links or emojis
        if "http" in content_lower or "www" in content_lower:
            spam_score += 0.2
        if len(re.findall(r"[!🔥🚀💥🤑]", content)) > 2:
            spam_score += 0.25
        
        # Check policy violation
        violation = False
        reason = "Content is safe."
        banned_words = {"buy now!", "make money fast", "viagra", "double your income"}
        for word in banned_words:
            if word in content_lower:
                violation = True
                reason = f"Flagged for promotional spam content: '{word}'."
                spam_score = max(spam_score, 0.9)
                break
                
        return {
            "sentiment": sentiment,
            "spam_risk": round(spam_score, 2),
            "policy_violation": violation,
            "reason": reason
        }
