import os, json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from nemoguardrails import LLMRails, RailsConfig
import string
_rails = None

def get_guardrails():
    global _rails
    if _rails is None:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        config_path = settings.GUARDRAILS_CONFIG_DIR
        print(f"🔄 Loading config from: {config_path}")
        
        config = RailsConfig.from_path(config_path)
        if hasattr(config, 'prompts'):
            print("📝 Loaded Prompts:")
            for prompt in config.prompts:
                print(f"  - Task: {prompt.task}")
                print(f"    Content: {prompt.content[:100]}...")
        else:
            print("❌ No prompts found in config!")
        
        _rails = LLMRails(config)
        
    return _rails
    
@csrf_exempt
def check_content(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            direction = data.get('direction', 'input')
            
            rails = get_guardrails()
            
            if direction == 'input':
                result = rails.generate(messages=[{"role": "user", "content": text, "user_input": text}])
            else:
                result = rails.generate(messages=[
                    {"role": "user", "content": "Validation prompt"},
                    {"role": "assistant", "content": text, "bot_response": text}
                ])
            
            # Strict validation of response
            validation_response = result.get("content", "").strip().lower()
            clean_response = validation_response.translate(str.maketrans('', '', string.punctuation)).strip()
            should_block = any(word in clean_response.split() for word in ["yes", "yeah", "yep"])
            
            # Debug logging
            print(f"Validation request - Direction: {direction}")
            print(f"Content: {text[:50]}...")
            print(f"Raw validation response: {repr(validation_response)}")
            print(f"Should block: {should_block}")
            
            return JsonResponse({
                "allowed": not should_block,
                "message": "Content blocked by policy" if should_block else "Content approved",
                "validation_response": validation_response
            })
            
        except Exception as e:
            print(f"Guardrails error: {str(e)}")
            return JsonResponse({
                "allowed": False,  # Fail closed for safety
                "error": str(e),
                "message": "Content blocked due to validation error"
            }, status=500)
    
    return JsonResponse({"error": "Only POST allowed"}, status=405) 