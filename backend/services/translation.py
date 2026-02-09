"""Auto-translation service using OpenAI GPT."""
import logging
from typing import Dict, Optional
import aiohttp
import json
from config import settings

logger = logging.getLogger(__name__)


class TranslationService:
    """Automatic translation service."""
    
    # Supported languages
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'es': 'Spanish',
        'pt': 'Portuguese',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
    }
    
    # In-memory cache (in production, use Redis)
    _cache: Dict[str, str] = {}
    
    @classmethod
    async def translate(cls, text: str, target_language: str, source_language: str = 'en') -> str:
        """Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code (en, es, pt, etc.)
            source_language: Source language code (default: en)
            
        Returns:
            Translated text
        """
        # If same language, return as-is
        if source_language == target_language:
            return text
        
        # Check if target language is supported
        if target_language not in cls.SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {target_language}, returning original text")
            return text
        
        # Check cache
        cache_key = f"{source_language}:{target_language}:{text}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        try:
            # Call OpenAI API for translation
            translated = await cls._call_openai_api(text, target_language, source_language)
            
            # Cache result
            cls._cache[cache_key] = translated
            
            return translated
        except Exception as e:
            logger.error(f"Translation failed: {e}", exc_info=True)
            return text  # Fallback to original text
    
    @classmethod
    async def _call_openai_api(cls, text: str, target_language: str, source_language: str) -> str:
        """Call OpenAI API for translation using Emergent LLM key."""
        target_lang_name = cls.SUPPORTED_LANGUAGES[target_language]
        source_lang_name = cls.SUPPORTED_LANGUAGES[source_language]
        
        prompt = f"Translate the following text from {source_lang_name} to {target_lang_name}. Return ONLY the translated text, no explanations:\n\n{text}"
        
        headers = {
            'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': f'You are a professional translator. Translate text to {target_lang_name}. Return only the translation, no explanations.'},
                {'role': 'user', 'content': text}
            ],
            'temperature': 0.3,
            'max_tokens': 500,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error: {response.status} - {error_text}")
                    raise Exception(f"OpenAI API error: {response.status}")
                
                data = await response.json()
                translated = data['choices'][0]['message']['content'].strip()
                return translated
    
    @classmethod
    def clear_cache(cls):
        """Clear translation cache."""
        cls._cache.clear()
