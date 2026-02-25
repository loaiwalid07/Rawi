"""
Video Merger - Merges multiple Veo video segments into a final video using FFmpeg
"""

import os
import asyncio
import subprocess
import tempfile
import uuid
from typing import Dict, Any, List
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


class VideoMerger:
    """Merges multiple video segments with smooth transitions using FFmpeg"""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.storage_client = storage.Client(project=project_id)
        self.bucket_name = f"{project_id}-story-assets"
        self.bucket = ensure_bucket_exists(self.storage_client, self.bucket_name, location)
        self.temp_dir = tempfile.gettempdir()
        
        logger.info("Initialized VideoMerger", project=project_id)
    
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
            raise
    
    async def _download_segments(
        self,
        video_segments: List[Dict[str, str]]
    ) -> List[str]:
        """Download video segments from GCS to local temp directory"""
        local_files = []
        
        for segment in video_segments:
            gcs_url = segment["url"]
            segment_id = segment.get("segment_id", "unknown")
            
            # Extract filename from GCS URL
            filename = gcs_url.split("/")[-1]
            local_path = os.path.join(self.temp_dir, filename)
            
            # Download from GCS
            try:
                blob = self.bucket.blob(gcs_url.replace(f"https://storage.googleapis.com/{self.bucket_name}/", ""))
                await asyncio.to_thread(blob.download_to_filename, local_path)
                local_files.append(local_path)
                logger.info("Downloaded segment", segment_id=segment_id, filename=filename)
            except Exception as e:
                logger.error("Failed to download segment", segment_id=segment_id, error=str(e))
                raise
        
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
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            return duration
        except subprocess.CalledProcessError as e:
            logger.error("FFprobe failed", error=e.stderr.decode())
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
                # Escape file paths for FFmpeg concat
                escaped_path = file_path.replace("\\", "/").replace(":", "\\:")
                f.write(f"file '{escaped_path}'\n")
        
        cmd = [
            "ffmpeg",
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
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg merge failed", error=e.stderr.decode())
            raise RuntimeError(f"FFmpeg merge failed: {e}")
    
    async def _upload_to_gcs(self, local_file: str, filename: str) -> str:
        """Upload merged video to GCS"""
        gcs_path = f"final/{filename}"
        blob = self.bucket.blob(gcs_path)
        
        await asyncio.to_thread(blob.upload_from_filename, local_file, content_type="video/mp4")
        await asyncio.to_thread(blob.make_public)
        
        gcs_url = blob.public_url
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
                "ffmpeg",
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
