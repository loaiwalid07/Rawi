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
        video_segments: List[Dict[str, str]],
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
            local_files = await self._download_segments(video_segments)
            
            # If no valid videos downloaded, return the first video URL or mock
            if not local_files:
                logger.warning("No valid video segments to merge, using first available video URL")
                first_video_url = video_segments[0]["url"] if video_segments else None
                if first_video_url:
                    parsed = _parse_gcs_url(first_video_url)
                    if parsed:
                        return _to_proxy_video_url(parsed[0], parsed[1])
                return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
            
            # If ffmpeg isn't available, fail soft.
            if not self._has_ffmpeg():
                logger.warning("FFmpeg/FFprobe not found. Returning first downloadable segment URL.")
                for seg in video_segments:
                    parsed = _parse_gcs_url(seg.get("url", ""))
                    if parsed:
                        return _to_proxy_video_url(parsed[0], parsed[1])
                return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

            # Calculate durations and offsets
            segment_info = await self._analyze_segments(local_files)
            
            # Merge videos with transitions
            merged_file = os.path.join(self.temp_dir, output_filename)
            await self._merge_with_ffmpeg(local_files, segment_info, merged_file, transition_duration, resolution)
            
            # Upload to GCS
            gcs_url = await self._upload_to_gcs(merged_file, output_filename)
            
            # Cleanup temporary files
            await self._cleanup_files(local_files + [merged_file])
            
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
        video_segments: List[Dict[str, str]]
    ) -> List[str]:
        """Download video segments from GCS to local temp directory"""
        local_files = []
        
        for segment in video_segments:
            gcs_url = segment["url"]
            parsed = _parse_gcs_url(gcs_url)
            if not parsed:
                continue

            bucket_name, blob_path = parsed
            local_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}.mp4")

            try:
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                await asyncio.to_thread(blob.download_to_filename, local_path)
                local_files.append(local_path)
            except Exception as e:
                logger.error("Failed to download segment", error=str(e))
                continue
        
        return local_files
    
    async def _analyze_segments(self, local_files: List[str]) -> List[Dict[str, Any]]:
        segment_info = []
        for i, file_path in enumerate(local_files):
            duration = await self._get_video_duration(file_path)
            segment_info.append({"index": i, "path": file_path, "duration": duration})
        return segment_info
    
    async def _get_video_duration(self, video_path: str) -> float:
        cmd = [self.ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 15.0
    
    async def _merge_with_ffmpeg(self, local_files: List[str], segment_info: List[Dict[str, Any]], output_file: str, transition_duration: float, resolution: str):
        if len(local_files) == 1:
            await asyncio.to_thread(shutil.copy2, local_files[0], output_file)
            return

        # Build complex filter for transitions
        # We'll use crossfade for a more cinematic feel
        inputs = []
        for f in local_files:
            inputs.extend(["-i", f])
            
        # Example for 2 segments:
        # [0:v][1:v]xfade=transition=fade:duration=0.5:offset=14.5[v]
        # For multiple, we chain them.
        
        filter_complex = ""
        current_offset = 0.0
        
        for i in range(len(segment_info) - 1):
            dur = segment_info[i]["duration"]
            current_offset += dur - transition_duration
            
            if i == 0:
                prev_node = "[0:v]"
            else:
                prev_node = "[v%d]" % i
                
            next_node = "[%d:v]" % (i + 1)
            out_node = "[v%d]" % (i + 1)
            
            filter_complex += f"{prev_node}{next_node}xfade=transition=fade:duration={transition_duration}:offset={current_offset}{out_node};"

        # Handle Audio: simple amix or concat
        audio_filter = ""
        for i in range(len(segment_info)):
            audio_filter += "[%d:a]" % i
        audio_filter += f"concat=n={len(segment_info)}:v=0:a=1[a]"

        final_v_node = "[v%d]" % (len(segment_info) - 1)
        
        cmd = [
            self.ffmpeg_bin, "-y"
        ] + inputs + [
            "-filter_complex", f"{filter_complex}{audio_filter}",
            "-map", final_v_node, "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-s", resolution,
            output_file
        ]
        
        try:
            logger.info("Running complex ffmpeg merge", cmd=" ".join(cmd))
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")
        except Exception as e:
            logger.error("Complex merge failed, falling back to simple concat", error=str(e))
            # Fallback to simple concat if complex filter fails (e.g. resolution mismatch)
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
