import requests
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def list_llmlab_models():
    api_key = os.environ.get("LLMLAB_API_KEY")

    if not api_key:
        print("Error: LLMLAB_API_KEY not found in environment or .env file.")
        sys.exit(1)

    endpoint = "https://llmlab.plgrid.pl/api/v1/models-plgrid-format"
    headers = {"accept": "application/json", "Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        models = response.json()

        print(f"{'Model Name':<50} | {'Price (1M tokens)':<20} | {'Tags'}")
        print("-" * 85)

        for model in models:
            name = (
                model.get("model_name")
                or model.get("id")
                or model.get("name")
                or "Unknown"
            )

            price = model.get("credits_per_token_price")
            if price is None:
                in_p = model.get("credits_per_input_token_price")
                out_p = model.get("credits_per_output_token_price")
                price = f"In: {in_p} / Out: {out_p}" if in_p and out_p else "N/A"

            tags = []
            if model.get("is_active"):
                tags.append("Active")
            if not model.get("is_active"):
                tags.append("Inactive")
            if model.get("accessible"):
                tags.append("Accessible")
            if not model.get("accessible"):
                tags.append("Inaccessible")
            if model.get("is_non_commercial"):
                tags.append("Non-commercial")
            if model.get("supports_function_calling"):
                tags.append("FC")
            if model.get("is_embedding"):
                tags.append("EMB")
            if model.get("is_beta"):
                tags.append("Beta")

            tags_str = ", ".join(tags)
            print(f"{name:<50} | {str(price):<20} | {tags_str}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching models: {e}")
        sys.exit(1)


if __name__ == "__main__":
    list_llmlab_models()
