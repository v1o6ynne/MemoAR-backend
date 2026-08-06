from dotenv import load_dotenv
load_dotenv()

import shutil
import subprocess
from pathlib import Path

import os
import requests
from tripo3d import TripoClient
from tripo3d.models import TaskStatus

from supabase import create_client, Client
import asyncio
from tripo3d.exceptions import TripoRequestError

import tempfile
import uuid


# 获取环境变量
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

# 初始化
supabase: Client = create_client(url, key)





TRIPO_TASK_URL = "https://api.tripo3d.ai/v2/openapi/task"
async def _wait_for_task_with_retry(
    client: TripoClient,
    task_id: str,
    *,
    verbose: bool = True,
    retries: int = 5,
    base_delay: float = 1.5,
):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            task = await client.wait_for_task(task_id, verbose=verbose)
            return task
        except TripoRequestError as e:
            last_error = e
            msg = str(e)

            retryable = (
                "HTTP 502" in msg
                or "HTTP 503" in msg
                or "HTTP 504" in msg
                or "Bad Gateway" in msg
            )

            print(
                f"⚠️ [Tripo] wait_for_task failed "
                f"attempt={attempt}/{retries} task_id={task_id} "
                f"retryable={retryable} error={e}"
            )

            if not retryable or attempt == retries:
                raise

            await asyncio.sleep(base_delay * attempt)

        except Exception as e:
            last_error = e
            print(
                f"⚠️ [Tripo] unexpected wait_for_task failure "
                f"attempt={attempt}/{retries} task_id={task_id} error={e}"
            )

            if attempt == retries:
                raise

            await asyncio.sleep(base_delay * attempt)

    raise last_error if last_error else RuntimeError(f"Unknown wait_for_task failure: {task_id}")

# ===== Image Path -> USDZ =====

def _resolve_input_image_path(
    image_path: str,
) -> tuple[str, Path | None]:
    """
    Resolve an input image into a path usable by Tripo.

    Returns:
        resolved_path:
            HTTP URL or an actual local file path.

        temporary_file:
            A downloaded temporary file that should be removed later.
            None when no temporary file was created.
    """

    # Tripo can directly receive an HTTP URL.
    if image_path.startswith(("http://", "https://")):
        print(f"✅ [InputImage] using remote URL: {image_path}")
        return image_path, None

    local_path = Path(image_path)

    # Compatibility with an actual backend-local file.
    if local_path.is_file():
        print(f"✅ [InputImage] using local file: {local_path}")
        return str(local_path), None

    # Otherwise, treat it as a Supabase Storage object path.
    object_path = image_path.lstrip("/")

    print("🟡 [InputImage] downloading from Supabase")
    print("   bucket = storage")
    print("   object_path =", object_path)

    try:
        image_bytes = (
            supabase.storage
            .from_("storage")
            .download(object_path)
        )
    except Exception as exc:
        print("❌ [InputImage] Supabase download failed:", repr(exc))

        raise FileNotFoundError(
            f"Input image was not found locally or in Supabase: "
            f"{object_path}"
        ) from exc

    if not image_bytes:
        raise FileNotFoundError(
            f"Supabase returned an empty input image: {object_path}"
        )

    suffix = Path(object_path).suffix or ".png"

    with tempfile.NamedTemporaryFile(
        prefix="memoar-input-",
        suffix=suffix,
        delete=False,
    ) as temporary_file:
        temporary_file.write(image_bytes)
        temporary_path = Path(temporary_file.name)

    print("✅ [InputImage] downloaded to temporary file")
    print("   path =", temporary_path)
    print("   bytes =", len(image_bytes))

    return str(temporary_path), temporary_path

async def generate_model_from_image(
    image_path: str,
    output_usdz_path: str = "",
    orientation: str = "align_image",
    user_id: str = "default_user",
    file_name: str = "model.usdz",
):
    """
    Generate a 3D model from:
    - an HTTP image URL,
    - a backend-local image path, or
    - a Supabase Storage object path.

    Then convert it to USDZ and upload the USDZ to Supabase.
    """

    resolved_image_path: str | None = None
    temporary_input_file: Path | None = None
    tmp_dir: Path | None = None

    try:
        # The frontend sends a Supabase object path such as:
        # user-id/modelImages/memory-id.png
        resolved_image_path, temporary_input_file = (
            _resolve_input_image_path(image_path)
        )

        print("🟡 [Tripo] original image_path =", image_path)
        print("🟡 [Tripo] resolved image_path =", resolved_image_path)

        working_dir = Path("/tmp/tripo_work")
        working_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # uuid prevents concurrent requests from using the same directory.
        tmp_dir = (
            working_dir
            / f"task_{user_id}_{uuid.uuid4().hex}"
        )

        tmp_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        async with TripoClient() as client:
            task_id = await client.image_to_model(
                image=resolved_image_path,
                orientation=orientation,
            )

            print(
                f"🟡 [Tripo] image_to_model "
                f"task_id={task_id}"
            )

            task = await _wait_for_task_with_retry(
                client,
                task_id,
                verbose=True,
            )

            if task.status != TaskStatus.SUCCESS:
                raise RuntimeError(
                    f"Image-to-model task failed: "
                    f"{task.status}"
                )

            convert_task_id = _submit_convert_task(
                task_id
            )

            print(
                f"🟡 [Tripo] convert_model "
                f"task_id={convert_task_id}"
            )

            convert_task = await _wait_for_task_with_retry(
                client,
                convert_task_id,
                verbose=True,
            )

            if convert_task.status != TaskStatus.SUCCESS:
                raise RuntimeError(
                    f"Convert-to-USDZ task failed: "
                    f"{convert_task.status}"
                )

            files = await client.download_task_models(
                convert_task,
                str(tmp_dir),
            )

        usdz_file = _find_usdz_file(
            files,
            tmp_dir,
        )

        if usdz_file is None:
            raise RuntimeError(
                f"No USDZ file found in output: {files}"
            )

        print(
            f"🟡 Uploading USDZ to Supabase: "
            f"{output_usdz_path} for user {user_id}"
        )

        remote_url = _upload_to_supabase(
            local_path=usdz_file,
            content_type="model/vnd.usdz+zip",
            object_path=output_usdz_path,
        )

        print(
            "✅ [Tripo] USDZ uploaded:",
            remote_url,
        )

        return remote_url

    finally:
        # Remove downloaded input PNG.
        if (
            temporary_input_file is not None
            and temporary_input_file.exists()
        ):
            temporary_input_file.unlink(
                missing_ok=True
            )

            print(
                "🧹 Removed temporary input image:",
                temporary_input_file,
            )

        # Remove downloaded Tripo result directory.
        if tmp_dir is not None:
            shutil.rmtree(
                tmp_dir,
                ignore_errors=True,
            )

            print(
                "🧹 Removed Tripo working directory:",
                tmp_dir,
            )


def _submit_convert_task(original_model_task_id: str) -> str:
    """
    Submit Tripo convert_model task to export USDZ.
    Reuses the API key already loaded in environment.
    """
    api_key = os.getenv("TRIPO_API_KEY")
    if not api_key:
        raise ValueError("TRIPO_API_KEY is not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "type": "convert_model",
        "format": "USDZ",
        "original_model_task_id": original_model_task_id,
    }

    resp = requests.post(TRIPO_TASK_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    print("convert_model response =", data)

    if data.get("code") != 0:
        raise RuntimeError(f"Tripo convert_model failed: {data}")

    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Tripo convert_model returned no task_id: {data}")

    return task_id


def _find_usdz_file(files, search_dir: Path) -> Path | None:
    if isinstance(files, list):
        for f in files:
            p = Path(str(f))
            if p.suffix.lower() == ".usdz" and p.exists():
                return p

    if isinstance(files, dict):
        for _, value in files.items():
            if isinstance(value, str):
                p = Path(value)
                if p.suffix.lower() == ".usdz" and p.exists():
                    return p

    for p in search_dir.rglob("*.usdz"):
        return p

    return None


def _get_tools_dir() -> Path:
    """
    tripo_services.py is in ARItems/
    tools are in sibling Tools/
    """
    return Path(__file__).resolve().parent.parent / "Tools"


def _get_rotate_tool_path() -> Path:
    return _get_tools_dir() / "usdz_rotate_tool"


def _get_poster_tool_path() -> Path:
    return _get_tools_dir() / "usdz_poster_renderer"


def _rotate_usdz_overwrite(
    usdz_path: Path,
    deg1: float = -90,
    axis1: str = "x",
    deg2: float = -90,
    axis2: str = "y",
):
    """
    Rotate USDZ and overwrite the original file path.
    Final filename stays exactly the same.
    """
    tool_path = _get_rotate_tool_path()

    if not tool_path.exists():
        raise FileNotFoundError(f"USDZ rotate tool not found: {tool_path}")

    rotated_tmp = usdz_path.with_name(f".{usdz_path.stem}_rotating{usdz_path.suffix}")

    result = subprocess.run(
        [
            str(tool_path),
            str(usdz_path),
            str(rotated_tmp),
            str(deg1),
            axis1,
            str(deg2),
            axis2,
        ],
        capture_output=True,
        text=True,
    )

    print("USDZ rotate stdout:\n", result.stdout)
    print("USDZ rotate stderr:\n", result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"USDZ rotation failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    if not rotated_tmp.exists():
        raise RuntimeError(f"Rotated USDZ not produced: {rotated_tmp}")

    rotated_tmp.replace(usdz_path)


def _render_usdz_poster(usdz_path: Path, poster_path: Path):
    """
    Render a transparent PNG poster from the final USDZ.
    Output path uses the same basename as the USDZ, just with .png.
    """
    tool_path = _get_poster_tool_path()

    if not tool_path.exists():
        raise FileNotFoundError(f"USDZ poster renderer not found: {tool_path}")

    poster_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            str(tool_path),
            str(usdz_path),
            str(poster_path),
        ],
        capture_output=True,
        text=True,
    )

    print("USDZ poster stdout:\n", result.stdout)
    print("USDZ poster stderr:\n", result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"USDZ poster render failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    if not poster_path.exists():
        raise RuntimeError(f"Poster PNG not produced: {poster_path}")
    

 
def _upload_to_supabase(local_path: Path, content_type: str, object_path: str) -> str:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")

    from supabase import create_client
    supabase_client = create_client(url, key)

    with open(local_path, "rb") as f:
        supabase_client.storage.from_("storage").upload(
            path=object_path,
            file=f,
            file_options={"content-type": content_type, "upsert": "true"}
        )

    public_url = supabase_client.storage.from_("storage").get_public_url(object_path)
    print(public_url)
    return public_url
