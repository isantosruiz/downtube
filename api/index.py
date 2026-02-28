import os
import tempfile
from pathlib import Path

import certifi
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename
import yt_dlp

app = Flask(__name__, template_folder="../templates", static_folder="../static")


def _base_ydl_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "cookiefile": None,
        "nocheckcertificate": False,
        "ca_certs": certifi.where(),
    }


def _extract_video_info(url: str):
    options = _base_ydl_options()
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        fallback_options = {**options, "nocheckcertificate": True}
        with yt_dlp.YoutubeDL(fallback_options) as ydl:
            return ydl.extract_info(url, download=False)


def _download_video(url: str, ydl_opts: dict):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        fallback_options = {**ydl_opts, "nocheckcertificate": True}
        with yt_dlp.YoutubeDL(fallback_options) as ydl:
            ydl.download([url])


def _build_format_label(fmt: dict) -> str:
    resolution = fmt.get("resolution") or "N/A"
    ext = fmt.get("ext") or "unknown"
    fps = fmt.get("fps")
    vcodec = fmt.get("vcodec") or "none"
    acodec = fmt.get("acodec") or "none"
    has_audio = acodec != "none"
    tbr = fmt.get("tbr")
    size = fmt.get("filesize") or fmt.get("filesize_approx")

    parts = [f"{resolution}", ext.upper()]
    if fps:
        parts.append(f"{int(fps)}fps")
    if tbr:
        parts.append(f"{int(tbr)}kbps")
    parts.append("con audio" if has_audio else "sin audio")
    if size:
        parts.append(f"{round(size / (1024 * 1024), 1)} MB")
    parts.append(f"v:{vcodec} a:{acodec}")

    return " | ".join(parts)


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/formats")
def get_formats():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Debes indicar una URL de YouTube."}), 400

    try:
        info = _extract_video_info(url)
    except Exception as exc:
        return jsonify({"error": f"No se pudo leer el video: {exc}"}), 400

    raw_formats = info.get("formats") or []

    # Solo formatos de video para descarga del archivo audiovisual.
    video_formats = [
        fmt
        for fmt in raw_formats
        if fmt.get("vcodec") not in (None, "none") and fmt.get("format_id")
    ]

    if not video_formats:
        return jsonify({"error": "No hay formatos de video disponibles para esta URL."}), 404

    seen = set()
    formats = []
    for fmt in video_formats:
        key = fmt["format_id"]
        if key in seen:
            continue
        seen.add(key)
        has_audio = (fmt.get("acodec") or "none") != "none"
        format_selector = key if has_audio else f"{key}+bestaudio/best"
        merge_note = "" if has_audio else " | se añadirá mejor audio"
        formats.append(
            {
                "format_id": key,
                "format_selector": format_selector,
                "ext": fmt.get("ext") or "unknown",
                "height": fmt.get("height") or 0,
                "has_audio": has_audio,
                "label": f"{_build_format_label(fmt)}{merge_note}",
            }
        )

    formats.sort(key=lambda x: (x["has_audio"], x["height"]), reverse=True)

    return jsonify(
        {
            "title": info.get("title") or "video",
            "uploader": info.get("uploader") or "",
            "thumbnail": info.get("thumbnail") or "",
            "formats": formats,
        }
    )


@app.post("/api/download")
def download():
    url = (request.form.get("url") or "").strip()
    format_selector = (request.form.get("format_selector") or "").strip()
    target_container = (request.form.get("target_container") or "mp4").strip().lower()
    if target_container not in {"mp4", "mkv", "original"}:
        target_container = "mp4"
    if not format_selector:
        # Compatibilidad con formularios antiguos.
        format_selector = (request.form.get("format_id") or "").strip()

    if not url or not format_selector:
        return jsonify({"error": "Faltan datos: URL o formato."}), 400

    try:
        info = _extract_video_info(url)
        title = secure_filename(info.get("title") or "video")

        with tempfile.TemporaryDirectory(prefix="downtube_", dir="/tmp") as temp_dir:
            outtmpl = os.path.join(temp_dir, f"{title}.%(ext)s")
            ydl_opts = {
                **_base_ydl_options(),
                "format": format_selector,
                "outtmpl": outtmpl,
                "restrictfilenames": True,
            }
            if target_container == "mp4":
                ydl_opts["merge_output_format"] = "mp4"
                ydl_opts["postprocessors"] = [
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
                ]
            elif target_container == "mkv":
                ydl_opts["merge_output_format"] = "mkv"

            _download_video(url, ydl_opts)

            files = list(Path(temp_dir).glob("*"))
            if not files:
                return jsonify({"error": "No se generó ningún archivo para descargar."}), 500

            file_path = max(files, key=lambda p: p.stat().st_size)
            download_name = file_path.name

            return send_file(
                str(file_path),
                as_attachment=True,
                download_name=download_name,
                mimetype="application/octet-stream",
            )
    except Exception as exc:
        msg = str(exc)
        if "ffmpeg is not installed" in msg.lower() or "ffmpeg not found" in msg.lower():
            return (
                jsonify(
                    {
                        "error": (
                            "El formato seleccionado requiere mezclar video+audio y no se encontro ffmpeg. "
                            "Instala ffmpeg o elige un formato que ya venga con audio."
                        )
                    }
                ),
                400,
            )
        return jsonify({"error": f"No se pudo descargar el video: {exc}"}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
