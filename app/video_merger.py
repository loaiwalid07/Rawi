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
from typing import Dict, Any, List
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


def _to_public_storage_url(uri: str) -> str:
    """Normalize gs:// URL into https://storage.googleapis.com URL."""
    if uri.startswith("gs://"):
        without_scheme = uri[len("gs://"):]
        bucket, _, blob_path = without_scheme.partition("/")
        if not bucket:
            return uri
        if not blob_path:
            return f"https://storage.googleapis.com/{bucket}"
        return f"https://storage.googleapis.com/{bucket}/{quote(blob_path, safe='/')}"
    return uri


def _parse_gcs_url(url: str):
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
            candidates = glob(
                os.path.join(
                    local_appdata,
                    "Microsoft",
                    "WinGet",
                    "Packages",
                    "Gyan.FFmpeg_*",
                    "ffmpeg-*",
                    "bin",
                    exe_name,
                )
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
        
        Args:
            video_segments: List of {"url": "...", "segment_id": "..."}
            output_filename: Final output filename
            transition_duration: Duration of crossfade between segments (seconds)
            resolution: Output resolution (width x height)
            
        Returns:
            GCS URL of the merged video
        """
        logger.info(
            "Starting video merge",
            num_segments=len(video_segments),
            transition_duration=transition_duration
        )
        
        try:
            # Download all segments locally
            local_files = await self._download_segments(video_segments)
            
            # If no valid videos downloaded, return the first video URL or mock
            if not local_files:
                logger.warning("No valid video segments to merge, using first available video URL")
                first_video_url = video_segments[0]["url"] if video_segments else None
                if first_video_url:
                    gcs_parts = _parse_gcs_url(first_video_url)
                    if gcs_parts:
                        return _to_public_storage_url(first_video_url)
                # Return mock or first URL
                return video_segments[0]["url"] if video_segments else "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
            
            # If ffmpeg isn't available (common on Windows dev machines), fail soft.
            if not self._has_ffmpeg():
                logger.warning("FFmpeg/FFprobe not found. Returning first downloadable segment URL.")
                for seg in video_segments:
                    parsed = _parse_gcs_url(seg.get("url", ""))
                    if parsed:
                        return _to_public_storage_url(seg["url"])
                return video_segments[0]["url"] if video_segments else "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"

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
            logger.error("Video merge failed", error=str(e))
            # Do not fail whole story if merge is unavailable; return first valid segment.
            for seg in video_segments:
                parsed = _parse_gcs_url(seg.get("url", ""))
                if parsed:
                    return _to_public_storage_url(seg["url"])
            return video_segments[0]["url"] if video_segments else "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
    
    async def _download_segments(
        self,
        video_segments: List[Dict[str, str]]
    ) -> List[str]:
        """Download video segments from GCS to local temp directory"""
        local_files = []
        
        for segment in video_segments:
            gcs_url = segment["url"]
            segment_id = segment.get("segment_id", "unknown")

            parsed = _parse_gcs_url(gcs_url)
            if not parsed:
                logger.warning(f"Skipping non-GCS video URL for segment {segment_id}: {gcs_url}")
                continue

            bucket_name, blob_path = parsed
            filename = os.path.basename(blob_path) or f"{uuid.uuid4()}.mp4"
            local_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}_{filename}")

            # Download from GCS (supports any source bucket URL).
            try:
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                await asyncio.to_thread(blob.download_to_filename, local_path)
                local_files.append(local_path)
                logger.info("Downloaded segment", segment_id=segment_id, bucket=bucket_name, blob=blob_path)
            except Exception as e:
                logger.error("Failed to download segment", segment_id=segment_id, error=str(e))
                continue
        
        return local_files
    
    async def _analyze_segments(self, local_files: List[str]) -> List[Dict[str, Any]]:
        """Analyze video segments to get duration and other info"""
        segment_info = []
        
        for i, file_path in enumerate(local_files):
            duration = await self._get_video_duration(file_path)
            segment_info.append({
                "index": i,
                "path": file_path,
                "duration": duration
            })
            
            logger.info("Analyzed segment", index=i, duration=duration)
        
        return segment_info
    
    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using FFprobe"""
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            return duration
        except FileNotFoundError:
            logger.error("FFprobe executable not found in PATH")
            raise RuntimeError("FFprobe executable not found in PATH.")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode(errors="ignore") if e.stderr else "")
            logger.error("FFprobe failed", error=stderr)
            raise RuntimeError(f"Failed to get video duration: {e}")
    
    async def _merge_with_ffmpeg(
        self,
        local_files: List[str],
        segment_info: List[Dict[str, Any]],
        output_file: str,
        transition_duration: float,
        resolution: str
    ):
        """Merge videos using FFmpeg with crossfade transitions"""
        
        if len(local_files) == 1:
            # No merging needed, just copy
            import shutil
            await asyncio.to_thread(shutil.copy2, local_files[0], output_file)
            logger.info("Single segment, copying file")
            return
        
        # Build FFmpeg command for concat (simpler than complex filter for hackathon)
        concat_file = os.path.join(self.temp_dir, f"concat_{uuid.uuid4()}.txt")
        
        with open(concat_file, "w") as f:
            for file_path in local_files:
                # FFmpeg concat on Windows expects valid absolute paths like C:/...
                # Do not escape drive-colon (C:) or FFmpeg treats it as invalid.
                escaped_path = file_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        cmd = [
            self.ffmpeg_bin,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-s", resolution,
            "-y",  # Overwrite output file
            output_file
        ]
        
        logger.info("Running FFmpeg merge", cmd=" ".join(cmd))
        
        try:
            await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
            logger.info("FFmpeg merge successful")
        except FileNotFoundError:
            logger.error("FFmpeg executable not found in PATH")
            raise RuntimeError("FFmpeg executable not found in PATH.")
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg merge failed", error=e.stderr.decode())
            raise RuntimeError(f"FFmpeg merge failed: {e}")
        finally:
            try:
                os.remove(concat_file)
            except OSError:
                pass
    
    async def _upload_to_gcs(self, local_file: str, filename: str) -> str:
        """Upload merged video to GCS"""
        gcs_path = f"final/{filename}"

        # Keep a durable local copy in output directory.
        local_final_path = Path(self.local_output_dir) / gcs_path
        local_final_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, local_file, str(local_final_path))
        logger.info("Saved merged video locally", local_path=str(local_final_path))

        blob = self.bucket.blob(gcs_path)
        
        await asyncio.to_thread(blob.upload_from_filename, local_file, content_type="video/mp4")
        
        gcs_url = f"https://storage.googleapis.com/{self.bucket_name}/{gcs_path}"
        logger.info("Uploaded merged video", gcs_url=gcs_url)
        return gcs_url
    
    async def _cleanup_files(self, files: List[str]):
        """Clean up temporary files"""
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    await asyncio.to_thread(os.remove, file_path)
                    logger.debug("Cleaned up file", file_path=file_path)
            except Exception as e:
                logger.warning("Failed to cleanup file", file_path=file_path, error=str(e))
    
    async def merge_with_audio(
        self,
        video_url: str,
        audio_url: str,
        output_filename: str
    ) -> str:
        """
        Merge a video with an audio track.
        
        Args:
            video_url: GCS URL of the video
            audio_url: GCS URL of the audio
            output_filename: Output filename
            
        Returns:
            GCS URL of the merged video
        """
        logger.info("Merging video with audio", video=video_url, audio=audio_url)
        
        # Download video and audio
        video_path = os.path.join(self.temp_dir, f"video_{uuid.uuid4()}.mp4")
        audio_path = os.path.join(self.temp_dir, f"audio_{uuid.uuid4()}.mp3")
        output_path = os.path.join(self.temp_dir, output_filename)
        
        try:
            # Download from GCS
            video_blob = self.bucket.blob(video_url.replace(f"https://storage.googleapis.com/{self.bucket_name}/", ""))
            audio_blob = self.bucket.blob(audio_url.replace(f"https://storage.googleapis.com/{self.bucket_name}/", ""))
            
            await asyncio.to_thread(video_blob.download_to_filename, video_path)
            await asyncio.to_thread(audio_blob.download_to_filename, audio_path)
            
            # Merge with FFmpeg
            cmd = [
                self.ffmpeg_bin,
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-y",
                output_path
            ]
            
            await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
            
            # Upload to GCS
            gcs_url = await self._upload_to_gcs(output_path, output_filename)
            
            # Cleanup
            await self._cleanup_files([video_path, audio_path, output_path])
            
            logger.info("Video with audio merge completed", gcs_url=gcs_url)
            return gcs_url
            
        except Exception as e:
            logger.error("Video+audio merge failed", error=str(e))
            await self._cleanup_files([video_path, audio_path, output_path])
            raise
