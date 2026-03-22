import os
from pathlib import Path
from google import genai
from google.genai import types


class GeminiService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.1-pro-preview",
        image_model: str = "gemini-3.1-flash-image-preview",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.image_model = image_model

    def complete(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        return response.text

    def complete_with_image_bytes(self, prompt: str, image_bytes: bytes, mime_type: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        return response.text

    def stylize_with_reference(
        self,
        prompt: str,
        user_image_bytes: bytes,
        user_mime_type: str,
        output_path: str,
        reference_image_path: str,
    ) -> str:
        ref_path = Path(reference_image_path)
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference image not found: {reference_image_path}")

        if not user_image_bytes:
            raise ValueError("Uploaded user image is empty.")

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        ref_bytes = ref_path.read_bytes()
        ref_mime = self._guess_mime_type(ref_path.suffix)

        response = self.client.models.generate_content(
            model=self.image_model,
            contents=[
                prompt,
                types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime),
                types.Part.from_bytes(data=user_image_bytes, mime_type=user_mime_type),
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",
                    image_size="2K",
                ),
            ),
        )

        print("===== GEMINI RESPONSE =====")
        print("response =", response)
        print("response.text =", getattr(response, "text", None))
        print("response.parts =", getattr(response, "parts", None))
        print("response.candidates =", getattr(response, "candidates", None))

        candidates = getattr(response, "candidates", None)
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {response}")

        first_candidate = candidates[0]
        content = getattr(first_candidate, "content", None)
        if content is None:
            raise ValueError(f"Gemini first candidate has no content: {response}")

        parts = getattr(content, "parts", None)
        if not parts:
            raise ValueError(f"Gemini first candidate has no parts: {response}")

        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None:
                try:
                    image = part.as_image()
                    image.save(out_path)
                    return str(out_path)
                except Exception as e:
                    print("part.as_image() failed:", e)

        raise ValueError(f"Model did not return an image part. Full response: {response}")

    @staticmethod
    def _guess_mime_type(suffix: str) -> str:
        suffix = suffix.lower()
        if suffix in [".jpg", ".jpeg"]:
            return "image/jpeg"
        if suffix == ".png":
            return "image/png"
        if suffix == ".webp":
            return "image/webp"
        return "image/jpeg"
       