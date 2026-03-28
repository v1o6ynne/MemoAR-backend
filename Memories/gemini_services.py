import os
from pathlib import Path
from google import genai
from google.genai import types

from supabase import create_client, Client

from rembg import remove, new_session  # 1. 加上 new_session
from PIL import Image


# 获取环境变量
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

# 初始化
supabase: Client = create_client(url, key)
_rembg_session = new_session("u2netp")


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

                    bg_removed_path = self._remove_white_background(
                        out_path,
                        threshold=238,
                        softness=18
                    )

                    remote_url = self._upload_to_supabase(
                        path=bg_removed_path,
                        content_type="image/png",
                    )
                    return remote_url
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
    
    # @staticmethod
    # def _remove_background(path: Path) -> Path:
    #     input_bytes = path.read_bytes()
    #     output_bytes = remove(input_bytes, )

    #     out_png = path.with_suffix(".png")
    #     out_png.write_bytes(output_bytes)
    #     return out_png

    @staticmethod
    def _remove_white_background(
        path: Path,
        threshold: int = 238,
        softness: int = 18
    ) -> Path:
        image = Image.open(path).convert("RGBA")
        pixels = image.load()
        width, height = image.size

        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]

                # 越接近 255 越白
                min_rgb = min(r, g, b)

                if min_rgb >= threshold:
                    # 很白，直接透明
                    pixels[x, y] = (r, g, b, 0)
                elif min_rgb >= threshold - softness:
                    # 边缘过渡区，做一点半透明减少白边
                    alpha = int(255 * (threshold - min_rgb) / max(softness, 1))
                    alpha = max(0, min(255, alpha))
                    pixels[x, y] = (r, g, b, alpha)
                else:
                    pixels[x, y] = (r, g, b, a)

        out_png = path.with_suffix(".png")
        image.save(out_png)
        return out_png
    

    
    @staticmethod   
    def _upload_to_supabase(path: Path, content_type: str) -> str:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")

        from supabase import create_client
        supabase_client = create_client(url, key)

        with open(path, "rb") as f:
            supabase_client.storage.from_("storage").upload(
                path=str(path),
                file=f,
                file_options={"content-type": content_type, "upsert": "true"}
            )

        public_url = supabase_client.storage.from_("storage").get_public_url(str(path))
        print(public_url)
        return public_url