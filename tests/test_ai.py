"""
AI Assistant Service Tests

Verifies AI content generation templates, hashtag optimization helpers,
sentiment classifiers, policy scanners, and mock API client fallbacks.
"""

import pytest
from services.ai_assistant import AIAssistant


def test_ai_mock_generation():
    # Force mock mode by passing no API keys
    ai = AIAssistant(api_key=None)
    assert ai.is_mock is True
    
    # Test post generation
    tw_post = ai.generate_post("AI development", "witty", "twitter")
    assert len(tw_post) > 0
    assert "AI development" in tw_post
    
    li_post = ai.generate_post("Leadership advice", "professional", "linkedin")
    assert "Leadership" in li_post
    assert "Strategy" in li_post
    
    # Test post optimization
    optimized_ig = ai.optimize_post("Check out our tool", "instagram")
    assert "#InstaStyle" in optimized_ig
    assert "✨" in optimized_ig


def test_ai_analysis():
    ai = AIAssistant(api_key=None)
    
    # Test regular safe analysis
    analysis_safe = ai.analyze_post("This is a great day to build beautiful software systems!")
    assert analysis_safe["sentiment"] == "Positive"
    assert analysis_safe["spam_risk"] < 0.2
    assert analysis_safe["policy_violation"] is False
    
    # Test warning trigger (caps look and exclamation marks)
    analysis_spam = ai.analyze_post("WIN MILLIONS OF DOLLARS RIGHT NOW!!! CLICK HERE!!!")
    assert analysis_spam["spam_risk"] > 0.4
    
    # Test policy violation trigger
    analysis_violation = ai.analyze_post("Double your income by buying our program today, buy now!")
    assert analysis_violation["policy_violation"] is True
    assert "Flagged for promotional spam" in analysis_violation["reason"]


def test_ai_client_mode(mock_genai_client):
    # Pass a valid token to bypass mock check
    ai = AIAssistant(api_key="valid_gemini_key_123")
    assert ai.is_mock is False
    assert ai.client is not None
    
    # Run mock client assertions
    generated = ai.generate_post("Project release", "professional", "twitter")
    assert generated == "Gemini generated content"
    
    # Check that client was called
    ai.client.models.generate_content.assert_called()
