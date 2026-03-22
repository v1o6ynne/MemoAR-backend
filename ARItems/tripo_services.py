from dotenv import load_dotenv
load_dotenv()

import shutil
import subprocess
from pathlib import Path

import os
import requests
from tripo3d import TripoClient
from tripo3d.models import TaskStatus


TRIPO_TASK_URL = "https://api.tripo3d.ai/v2/openapi/task"


# ===== Image Path -> USDZ =====

async def generate_model_from_image(
    image_path: str,
    output_usdz_path: str,
    orientation: str = "align_image",
):
    """
    Read an image from image_path, generate 3D model with Tripo,
    convert it to USDZ, save it to output_usdz_path, rotate it,
    and also render a transparent PNG poster at the same basename.
    Final return value still stays the USDZ path.
    """

    input_path = Path(image_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    output_path = Path(output_usdz_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = output_path.parent / f"tmp_{output_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    async with TripoClient() as client:
        # Step 1: image -> base model
        task_id = await client.image_to_model(
            image=str(input_path),
            orientation=orientation,
        )

        task = await client.wait_for_task(task_id, verbose=True)

        if task.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"Image-to-model task failed: {task.status}")

        # Step 2: convert -> USDZ
        convert_task_id = _submit_convert_task(task_id)

        convert_task = await client.wait_for_task(convert_task_id, verbose=True)

        if convert_task.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"Convert-to-USDZ task failed: {convert_task.status}")

        # Step 3: download converted model
        files = await client.download_task_models(convert_task, str(tmp_dir))

    usdz_file = _find_usdz_file(files, tmp_dir)
    if usdz_file is None:
        raise RuntimeError(f"No USDZ file found in converted output: {files}")

    if output_path.exists():
        output_path.unlink()

    shutil.move(str(usdz_file), str(output_path))

    # Step 4: rotate and overwrite same final path
    _rotate_usdz_overwrite(
        output_path,
        deg1=-90,
        axis1="x",
        deg2=-90,
        axis2="y",
    )

    # Step 5: render transparent PNG poster with same basename
    poster_path = output_path.with_suffix(".png")
    _render_usdz_poster(output_path, poster_path)

    shutil.rmtree(tmp_dir, ignore_errors=True)

    return str(output_path)


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