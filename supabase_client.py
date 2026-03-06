import os
from dotenv import load_dotenv

try:
    from supabase import create_client, Client

    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_supabase_client() -> Client:
    if not HAS_SUPABASE:
        print("Supabase library is not installed. Run: pip install supabase")
        return None

    if not SUPABASE_URL or not SUPABASE_KEY:
        print(
            "Supabase configuration missing in .env file (SUPABASE_URL and SUPABASE_KEY)"
        )
        return None

    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to create Supabase client: {e}")
        return None


def save_vocabulary_improvement(original_text: str, improved_text: str):
    """
    Saves the original and improved text to Supabase.
    Table: vocabulary_improvements
    Columns: original_text, improved_text
    """
    client = get_supabase_client()
    if not client:
        return False

    try:
        data = {"original_text": original_text, "improved_text": improved_text}
        response = client.table("vocabulary_improvements").insert(data).execute()
        return response != None
    except Exception as e:
        print(f"Failed to save to Supabase: {e}")
        return False
