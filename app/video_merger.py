"""
Video Merger - Merges multiple Veo video segments into a final video using FFmpeg
"""

import os
import asyncio
import shutil
import subprocess
import tempfile
import uuid
from glob import glob
from pathlib import Path
from urllib.parse import quote
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
load_dotenv()

from google.cloud import storage
import structlog

logger = structlog.get_logger(__name__)


def ensure_bucket_exists(storage_client, bucket_name: str, location: str = "us-central1"):
    """Create bucket if it doesn't exist"""
    try:
        bucket = storage_client.bucket(bucket_name)
        if bucket.exists():
            return bucket
        bucket.location = location
        bucket.create()
        logger.info(f"Created bucket: {bucket_name}")
        return bucket
    except Exception as e:
        logger.warning(f"Could not create bucket {bucket_name}: {e}")
        return None


def _to_proxy_video_url(bucket: str, blob_path: str) -> str:
    """Create a proxy video URL for video content served via FastAPI."""
    return f"/video/{bucket}/{quote(blob_path, safe='/')}"


def _parse_gcs_url(url: str) -> Optional[Tuple[str, str]]:
    """Parse gs://bucket/path or https://storage.googleapis.com/bucket/path."""
    if url.startswith("gs://"):
        without_scheme = url[len("gs://"):]
        bucket, _, blob_path = without_scheme.partition("/")
        if bucket and blob_path:
            return bucket, blob_path
        return None
    if url.startswith("https://storage.googleapis.com/"):
        without_host = url[len("https://storage.googleapis.com/"):]
        bucket, _, blob_path = without_host.partition("/")
        if bucket and blob_path:
            return bucket, blob_path
        return None
    # Handle proxy URLs as well
    if url.startswith("/video/") or url.startswith("/media/"):
        parts = url.strip("/").split("/")
        if len(parts) >= 3:
            bucket = parts[1]
            blob_path = "/".join(parts[2:])
            return bucket, blob_path
    return None

def _format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"


class VideoMerger:
    """Merges multiple video segments with smooth transitions using FFmpeg"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Use bucket from env or generate default
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}-story-assets")
        self.local_output_dir = os.getenv("LOCAL_OUTPUT_DIR", "local_media")
        
        self.storage_client = storage.Client(project=project_id)
        self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        self.temp_dir = tempfile.gettempdir()
        self.ffmpeg_bin = self._resolve_binary("FFMPEG_BINARY", "ffmpeg.exe", "ffmpeg")
        self.ffprobe_bin = self._resolve_binary("FFPROBE_BINARY", "ffprobe.exe", "ffprobe")
        
        logger.info(
            "Initialized VideoMerger",
            project=project_id,
            bucket=self.bucket_name,
            ffmpeg=self.ffmpeg_bin,
            ffprobe=self.ffprobe_bin,
        )

    def _resolve_binary(self, env_var: str, exe_name: str, fallback_name: str) -> str:
        """Resolve ffmpeg/ffprobe binary path from env, PATH, or WinGet install."""
        explicit = os.getenv(env_var)
        if explicit and os.path.exists(explicit):
            return explicit

        from_path = shutil.which(fallback_name)
        if from_path:
            return from_path

        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            # Use glob with forward slashes for cross-platform compatibility in path building
            base_search = local_appdata.replace("\\", "/") 
            candidates = glob(
                f"{base_search}/Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*/bin/{exe_name}"
            )
            if candidates:
                return candidates[0]

        return fallback_name

    def _has_ffmpeg(self) -> bool:
        """Check if ffmpeg and ffprobe executables are available."""
        return os.path.exists(self.ffmpeg_bin) and os.path.exists(self.ffprobe_bin)
    
    async def merge_segments(
        self,
        video_segments: List[Dict[str, Any]],
        output_filename: str,
        transition_duration: float = 0.5,
        resolution: str = "1920x1080"
    ) -> str:
        """
        Merge multiple video segments with smooth transitions.
        """
        logger.info(
            "Starting video merge",
            num_segments=len(video_segments)
        )
        
        try:
            # Download all segments locally
            downloaded_segments = await self._download_segments(video_segments)
            
            # If no valid videos downloaded, return the first video URL or mock
            if not downloaded_segments:
                logger.warning("No valid video segments to merge, using first available video URL")
                first_video_url = video_segments[0]["url"] if video_segments else None
                if first_video_url:
                    parsed = _parse_gcs_url(first_video_url)
                    if parsed:
                        return _to_proxy_video_url(parsed[0], parsed[1])
                return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
            
            local_files = [seg["path"] for seg in downloaded_segments]
            local_audio_files = [seg["audio_path"] for seg in downloaded_segments if seg.get("audio_path")]

            # If ffmpeg isn't available, fail soft.
            if not self._has_ffmpeg():
                logger.warning("FFmpeg/FFprobe not found. Returning first downloadable segment URL.")
                for seg in video_segments:
                    parsed = _parse_gcs_url(seg.get("url", ""))
                    if parsed:
                        return _to_proxy_video_url(parsed[0], parsed[1])
                return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

            # Calculate durations and offsets
            segment_info = await self._analyze_segments(downloaded_segments)
            
            # Merge videos with transitions and subtitles
            merged_file = os.path.join(self.temp_dir, output_filename)
            await self._merge_with_ffmpeg(local_files, segment_info, merged_file, transition_duration, resolution)
            
            # Upload to GCS
            gcs_url = await self._upload_to_gcs(merged_file, output_filename)
            
            # Cleanup temporary files
            await self._cleanup_files(local_files + local_audio_files + [merged_file, os.path.join(self.temp_dir, f"subs_{output_filename}.srt")])
            
            logger.info("Video merge completed", gcs_url=gcs_url)
            return gcs_url
            
        except Exception as e:
            logger.error("Video merge failed", error=str(e), exc_info=True)
            for seg in video_segments:
                parsed = _parse_gcs_url(seg.get("url", ""))
                if parsed:
                    return _to_proxy_video_url(parsed[0], parsed[1])
            return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    
    async def _download_segments(
        self,
        video_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Download video segments from GCS to local temp directory"""
        downloaded = []
        
        for segment in video_segments:
            gcs_url = segment["url"]
            parsed = _parse_gcs_url(gcs_url)
            if not parsed:
                continue

            bucket_name, blob_path = parsed
            local_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}.mp4")
            local_audio_path = None
            
            # Download audio if available
            voiceover_url = segment.get("voiceover_url")
            if voiceover_url:
                v_parsed = _parse_gcs_url(voiceover_url)
                if v_parsed:
                    v_bucket, v_path = v_parsed
                    local_audio_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}.mp3")
                    try:
                        a_bucket = self.storage_client.bucket(v_bucket)
                        a_blob = a_bucket.blob(v_path)
                        await asyncio.to_thread(a_blob.download_to_filename, local_audio_path)
                    except Exception as e:
                        logger.error("Failed to download audio segment", error=str(e))
                        local_audio_path = None

            try:
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                await asyncio.to_thread(blob.download_to_filename, local_path)
                downloaded.append({
                    "path": local_path, 
                    "audio_path": local_audio_path,
                    "narration": segment.get("narration", "")
                })
            except Exception as e:
                logger.error("Failed to download video segment", error=str(e))
                continue
        
        return downloaded
    
    async def _analyze_segments(self, downloaded_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        segment_info = []
        for i, seg in enumerate(downloaded_segments):
            duration = await self._get_video_duration(seg["path"])
            segment_info.append({
                "index": i, 
                "path": seg["path"], 
                "audio_path": seg.get("audio_path"),
                "duration": duration,
                "narration": seg["narration"]
            })
        return segment_info
    
    async def _get_video_duration(self, video_path: str) -> float:
        cmd = [self.ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 15.0
    
    async def _merge_with_ffmpeg(self, local_files: List[str], segment_info: List[Dict[str, Any]], output_file: str, transition_duration: float, resolution: str):
        # Even if len == 1, we must run it through the subtitles filter.
        # So we do not do a simple copy.

        # Generate SRT
        srt_filename = f"subs_{os.path.basename(output_file)}.srt"
        srt_path = os.path.join(self.temp_dir, srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            curr_t = 0.0
            for i, seg in enumerate(segment_info):
                end_t = curr_t + seg["duration"]
                if i < len(segment_info) - 1:
                    end_t -= transition_duration
                f.write(f"{i+1}\n")
                f.write(f"{_format_srt_time(curr_t)} --> {_format_srt_time(end_t)}\n")
                f.write(f"{seg.get('narration', '')}\n\n")
                curr_t = end_t
                
        # Combine inputs: video files first, then audio files
        inputs = []
        for f in local_files:
            inputs.extend(["-i", f])
            
        audio_inputs = []
        for seg in segment_info:
            if seg.get("audio_path"):
                audio_inputs.append(seg["audio_path"])
                
        for f in audio_inputs:
            inputs.extend(["-i", f])
            
        filter_parts = []
        current_offset: float = 0.0
        
        if len(segment_info) > 1:
            for i in range(len(segment_info) - 1):
                dur = float(segment_info[i]["duration"])
                current_offset += dur - transition_duration
                
                prev_node = "[0:v]" if i == 0 else f"[v{i}]"
                next_node = f"[{i + 1}:v]"
                out_node = f"[v{i + 1}]"
                
                filter_parts.append(f"{prev_node}{next_node}xfade=transition=fade:duration={transition_duration}:offset={current_offset}{out_node};")
            
            merged_v_node = f"[v{len(segment_info) - 1}]"
        else:
            merged_v_node = "[0:v]"

        # Add subs filter using the generated SRT file.
        # Professional educational subtitle style: larger font, semi-transparent background, bottom positioning
        final_v_node = "[final_v]"
        sub_style = "FontSize=28,FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=4,Outline=1,Shadow=0,MarginV=30,Bold=1"
        filter_parts.append(f"{merged_v_node}subtitles={srt_filename}:force_style='{sub_style}'{final_v_node};")

        # Handle Audio
        audio_stream_idx: int = len(local_files)
        audio_offset: float = 0.0
        mix_nodes: str = ""
        num_mix: int = 0
        
        for i in range(len(segment_info)):
            if segment_info[i].get("audio_path"):
                delay_ms = int(audio_offset * 1000)  # type: ignore
                filter_parts.append(f"[{audio_stream_idx}:a]adelay={delay_ms}:all=1[a{i}];")
                mix_nodes += f"[a{i}]"  # type: ignore
                audio_stream_idx += 1   # type: ignore
                num_mix += 1            # type: ignore
                
            dur = float(segment_info[i]["duration"])
            if i < len(segment_info) - 1:
                audio_offset += dur - transition_duration  # type: ignore
                
        if num_mix > 0:
            filter_parts.append(f"{mix_nodes}amix=inputs={num_mix}:duration=longest:dropout_transition=0,volume={num_mix}[a]")
            audio_map = ["-map", "[a]"]
        else:
            audio_map = []
            
        final_filter = "".join(filter_parts)
        
        cmd = [
            self.ffmpeg_bin, "-y"
        ] + inputs + [
            "-filter_complex", final_filter,
            "-map", final_v_node
        ] + audio_map + [
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-s", resolution,
            output_file
        ]
        
        try:
            logger.info("Running complex ffmpeg merge with audio", cmd=" ".join(cmd), cwd=self.temp_dir)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")
        except Exception as e:
            logger.error("Complex merge with audio failed, retrying without audio", error=str(e))
            # Fallback: retry without audio inputs
            try:
                video_only_inputs = []
                for f_path in local_files:
                    video_only_inputs.extend(["-i", f_path])
                
                # Rebuild filter without audio parts
                video_filter_parts = [p for p in filter_parts if "adelay" not in p and "amix" not in p]
                video_only_filter = "".join(video_filter_parts)
                
                fallback_cmd = [
                    self.ffmpeg_bin, "-y"
                ] + video_only_inputs + [
                    "-filter_complex", video_only_filter,
                    "-map", final_v_node,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-an",
                    "-s", resolution,
                    output_file
                ]
                logger.info("Running ffmpeg merge without audio", cmd=" ".join(fallback_cmd))
                process2 = await asyncio.create_subprocess_exec(
                    *fallback_cmd,
                    cwd=self.temp_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout2, stderr2 = await process2.communicate()
                if process2.returncode != 0:
                    raise RuntimeError(f"FFmpeg video-only fallback also failed: {stderr2.decode()}")
            except Exception as e2:
                logger.error("Video-only fallback also failed, using simple concat", error=str(e2))
                await self._simple_concat(local_files, output_file, resolution)

    async def _simple_concat(self, local_files: List[str], output_file: str, resolution: str):
        concat_file = os.path.join(self.temp_dir, f"concat_{uuid.uuid4()}.txt")
        with open(concat_file, "w") as f:
            for file_path in local_files:
                escaped_path = file_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        cmd = [self.ffmpeg_bin, "-f", "concat", "-safe", "0", "-i", concat_file, "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k", "-s", resolution, "-y", output_file]
        try:
            await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
        finally:
            try: os.remove(concat_file)
            except OSError: pass
    
    async def _upload_to_gcs(self, local_file: str, filename: str) -> str:
        gcs_path = f"final/{filename}"
        local_final_path = Path(self.local_output_dir) / gcs_path
        local_final_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, local_file, str(local_final_path))

        if self.bucket:
            blob = self.bucket.blob(gcs_path)
            await asyncio.to_thread(blob.upload_from_filename, local_file, content_type="video/mp4")
            return _to_proxy_video_url(self.bucket_name, gcs_path)
        return f"file://{local_final_path}"
    
    async def _cleanup_files(self, files: List[str]):
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    await asyncio.to_thread(os.remove, file_path)
            except Exception: pass

    async def merge_with_audio(self, video_url: str, audio_url: str, output_filename: str) -> str:
        video_path = os.path.join(self.temp_dir, f"v_{uuid.uuid4()}.mp4")
        audio_path = os.path.join(self.temp_dir, f"a_{uuid.uuid4()}.mp3")
        output_path = os.path.join(self.temp_dir, output_filename)
        
        try:
            v_parsed = _parse_gcs_url(video_url)
            a_parsed = _parse_gcs_url(audio_url)
            if not v_parsed or not a_parsed: raise ValueError("Invalid URLs")
            
            await asyncio.to_thread(self.storage_client.bucket(v_parsed[0]).blob(v_parsed[1]).download_to_filename, video_path)
            await asyncio.to_thread(self.storage_client.bucket(a_parsed[0]).blob(a_parsed[1]).download_to_filename, audio_path)
            
            cmd = [self.ffmpeg_bin, "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", output_path]
            await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
            return await self._upload_to_gcs(output_path, output_filename)
        finally:
            await self._cleanup_files([video_path, audio_path, output_path])
