import json
from google import genai
from google.genai import types

class GeminiService:
    def __init__(self, api_key=None, model="gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def set_api_key(self, api_key):
        self.api_key = api_key

    def test_connection(self):
        """
        Tests if the Gemini API key and connection are valid.
        Returns (success: bool, message: str)
        """
        if not self.api_key:
            return False, "Aucune clé API configurée."

        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents="Ping. Réponds uniquement par 'PONG'."
            )
            if response and response.text:
                return True, "Connexion à Google Gemini réussie !"
            return False, "Réponse vide de l'API."
        except Exception as e:
            return False, f"Erreur de connexion : {str(e)}"

    def select_packages(self, user_prompt, available_items):
        """
        Analyzes the user prompt and returns a list of package names matching the intent.
        """
        if not self.api_key:
            raise ValueError("Clé API Gemini non configurée. Veuillez l'ajouter dans les Paramètres.")

        if not available_items:
            return []

        client = genai.Client(api_key=self.api_key)
        system_instruction = (
            "You are an expert IT automation assistant for AutoForge AI. "
            "Given a user request and a list of local installer filenames/folders, "
            "return a pure JSON array containing ONLY the exact names of files or folders that strictly match the intent. "
            "Do not include commentary or markdown fences."
        )
        prompt = f"Available Packages: {json.dumps(available_items)}\nUser Request: {user_prompt}"

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json"
            )
        )
        
        try:
            cleaned_text = response.text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            selected = json.loads(cleaned_text.strip())
            if isinstance(selected, list):
                return selected
            return []
        except Exception as e:
            raise ValueError(f"Erreur de traitement de la réponse IA: {str(e)}")
