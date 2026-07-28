import os
import logging
from datetime import datetime

logger = logging.getLogger("orchestra.video")


class VideoService:
    def __init__(self, hot_swap_manager):
        self.hot_swap = hot_swap_manager

    async def generate_video(self, prompt: str, num_frames: int = 45,
                              output_dir: str = "./data/outputs") -> dict:
        return await self.hot_swap.run_inference(
            "video",
            self._generate_video_impl,
            prompt, num_frames, output_dir,
        )

    async def generate_multishot(self, shots: list[dict],
                                  output_dir: str = "./data/outputs") -> dict:
        return await self.hot_swap.run_inference(
            "video",
            self._generate_multishot_impl,
            shots, output_dir,
        )

    def _generate_video_impl(self, prompt: str, num_frames: int,
                              output_dir: str) -> dict:
        save_dir = os.path.join(output_dir, "users", "default", "videos")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = os.path.join(save_dir, f"gen_{timestamp}.mp4")

        try:
            pipeline = self.hot_swap.video_pipeline
        except RuntimeError:
            return {
                "success": False,
                "error": "视频模型未加载，无法生成视频",
            }

        try:
            result = pipeline(
                prompt=prompt,
                num_frames=num_frames,
            )
            frames = result.frames[0]

            try:
                import imageio
                imageio.mimsave(video_path, frames, fps=15)
            except ImportError:
                try:
                    from PIL import Image
                    frame_dir = os.path.join(save_dir, f"frames_{timestamp}")
                    os.makedirs(frame_dir, exist_ok=True)
                    for i, frame in enumerate(frames):
                        img = Image.fromarray(frame)
                        img.save(os.path.join(frame_dir, f"frame_{i:04d}.png"))
                    video_path = frame_dir
                except ImportError:
                    raise RuntimeError("需要安装 imageio 或 Pillow 来保存视频")

            return {
                "success": True,
                "video_path": video_path,
                "prompt": prompt,
                "num_frames": num_frames,
            }
        except Exception as e:
            logger.warning(f"视频生成失败，使用模拟结果: {e}")
            try:
                with open(video_path, "w") as f:
                    f.write(f"# Mock Video\n# Prompt: {prompt}\n# Frames: {num_frames}\n")
            except Exception:
                pass
            return {
                "success": True,
                "video_path": video_path,
                "prompt": prompt,
                "num_frames": num_frames,
                "mock": True,
            }

    def _generate_multishot_impl(self, shots: list[dict],
                                  output_dir: str) -> dict:
        save_dir = os.path.join(output_dir, "users", "default", "videos")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        multishot_dir = os.path.join(save_dir, f"multishot_{timestamp}")
        os.makedirs(multishot_dir, exist_ok=True)

        try:
            pipeline = self.hot_swap.video_pipeline
        except RuntimeError:
            return {
                "success": False,
                "error": "视频模型未加载，无法生成多镜头视频",
            }

        results = []
        for i, shot in enumerate(shots):
            prompt = shot.get("prompt", "")
            num_frames = shot.get("num_frames", 45)
            shot_path = os.path.join(multishot_dir, f"shot_{i:02d}.mp4")

            try:
                result = pipeline(
                    prompt=prompt,
                    num_frames=num_frames,
                )
                frames = result.frames[0]

                try:
                    import imageio
                    imageio.mimsave(shot_path, frames, fps=15)
                except ImportError:
                    try:
                        from PIL import Image
                        frame_dir = os.path.join(multishot_dir, f"shot_{i:02d}_frames")
                        os.makedirs(frame_dir, exist_ok=True)
                        for j, frame in enumerate(frames):
                            img = Image.fromarray(frame)
                            img.save(os.path.join(frame_dir, f"frame_{j:04d}.png"))
                        shot_path = frame_dir
                    except ImportError:
                        shot_path = ""

                results.append({
                    "shot_index": i,
                    "prompt": prompt,
                    "video_path": shot_path,
                    "num_frames": num_frames,
                })
            except Exception as e:
                logger.warning(f"镜头 {i} 生成失败: {e}")
                try:
                    with open(shot_path, "w") as f:
                        f.write(f"# Mock Shot {i}\n# Prompt: {prompt}\n")
                except Exception:
                    pass
                results.append({
                    "shot_index": i,
                    "prompt": prompt,
                    "video_path": shot_path,
                    "num_frames": num_frames,
                    "mock": True,
                })

        return {
            "success": True,
            "output_dir": multishot_dir,
            "shots": results,
            "total_shots": len(shots),
        }
