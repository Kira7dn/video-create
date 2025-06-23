from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import shutil
import os
import uuid
import subprocess
import json

app = FastAPI()

def remove_tmp_dir(tmp_dir):
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)

@app.post("/api/concat-videos")
async def concat_videos_api(
    videos: list[UploadFile] = File(...),
    transition: str = Form(None),
    transition_duration: float = Form(1.0),
    sequence: str = Form(None),
    background_tasks: BackgroundTasks = None,
):
    tmp_dir = f"tmp_concat_{uuid.uuid4().hex}"
    os.makedirs(tmp_dir, exist_ok=True)
    video_paths = []
    try:
        for vid in videos:
            path = os.path.join(tmp_dir, vid.filename)
            with open(path, "wb") as f:
                shutil.copyfileobj(vid.file, f)
            video_paths.append(path)
        output_path = os.path.join(tmp_dir, "output_concat.mp4")
        cmd = [
            "python",
            "concat_videos.py",
            "--input-dir",
            tmp_dir,
            "--output",
            output_path,
        ]
        if transition:
            cmd += ["--transition", transition]
        if transition_duration:
            cmd += ["--transition-duration", str(transition_duration)]
        if sequence:
            cmd += ["--sequence", sequence]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not os.path.exists(output_path):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return JSONResponse(status_code=400, content={"error": result.stderr})
        if background_tasks:
            background_tasks.add_task(remove_tmp_dir, tmp_dir)
        return FileResponse(output_path, media_type="video/mp4")
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/create-video")
async def create_video_api(input_json: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    tmp_dir = f"tmp_create_{uuid.uuid4().hex}"
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        json_path = os.path.join(tmp_dir, input_json.filename)
        with open(json_path, "wb") as f:
            shutil.copyfileobj(input_json.file, f)
        output_path = os.path.join(tmp_dir, "output_create.mp4")
        cmd = ["python", "create_video.py", "--input", json_path, "--output", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not os.path.exists(output_path):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return JSONResponse(status_code=400, content={"error": result.stderr})
        if background_tasks:
            background_tasks.add_task(remove_tmp_dir, tmp_dir)
        return FileResponse(output_path, media_type="video/mp4")
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
