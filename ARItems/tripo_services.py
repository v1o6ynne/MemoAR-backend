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

# 获取环境变量
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

# 初始化
supabase: Client = create_client(url, key)


TRIPO_TASK_URL = "https://api.tripo3d.ai/v2/openapi/task"


# ===== Image Path -> USDZ =====

async def generate_model_from_image(
    image_path: str,
    output_usdz_path: str = "", 
    orientation: str = "align_image",
    user_id: str = "default_user",
    file_name: str = "model.usdz"
):
    """
    generate 3D model and upload to Supabase
    """
    
    input_path = Path(image_path)
    
    if not str(image_path).startswith("http") and not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    
    working_dir = Path("/tmp/tripo_work")
    working_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = working_dir / f"task_{user_id}_{os.getpid()}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    async with TripoClient() as client:
        
        task_id = await client.image_to_model(
            image=str(image_path),
            orientation=orientation,
        )

        task = await client.wait_for_task(task_id, verbose=True)
        if task.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"Image-to-model task failed: {task.status}")

        
        convert_task_id = _submit_convert_task(task_id)
        convert_task = await client.wait_for_task(convert_task_id, verbose=True)
        if convert_task.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"Convert-to-USDZ task failed: {convert_task.status}")

        
        files = await client.download_task_models(convert_task, str(tmp_dir))

    usdz_file = _find_usdz_file(files, tmp_dir)
    if usdz_file is None:
        raise RuntimeError(f"No USDZ file found in output: {files}")

    print(f"Uploading to Supabase: {file_name} for user {user_id}")
    remote_url = _upload_to_supabase(
        local_path=usdz_file, 
        content_type="model/vnd.usdz+zip",
        user_id=user_id,
        file_name=file_name
    )

    shutil.rmtree(tmp_dir, ignore_errors=True)

    # this is Supabase public URL for frontend to download
    return remote_url


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
    
def _upload_to_supabase(local_path: Path, content_type: str, user_id: str, file_name: str) -> str:
    """
    upload to Supabase Storage under user_id folder
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")

    from supabase import create_client
    supabase_client = create_client(url, key)

    # using user_id and file_name for the path
    # path: models/user_id/file_name.usdz
    storage_path = f"{local_path}" 

    with open(local_path, "rb") as f:
        supabase_client.storage.from_("models").upload(
            path=storage_path,
            file=f,
            file_options={"content-type": content_type, "upsert": "true"}
        )

    public_url = supabase_client.storage.from_("models").get_public_url(storage_path)
    print(public_url)
    return public_url
