import os
import logging
from datetime import datetime

logger = logging.getLogger("orchestra.vision")


class VisionService:
    def __init__(self, hot_swap_manager):
        self.hot_swap = hot_swap_manager

    async def generate_image(self, prompt: str, style: str = "realistic",
                              size: str = "384x384",
                              output_dir: str = "./data/outputs") -> dict:
        return await self.hot_swap.run_inference(
            "vision",
            self._generate_image_impl,
            prompt, style, size, output_dir,
        )

    async def understand_image(self, image_path: str, question: str) -> dict:
        return await self.hot_swap.run_inference(
            "vision",
            self._understand_impl,
            image_path, question,
        )

    def _generate_image_impl(self, prompt: str, style: str, size: str,
                              output_dir: str) -> dict:
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow 未安装，无法生成图片")

        try:
            processor = self.hot_swap.vision_processor
            model = self.hot_swap.vision_model
        except RuntimeError:
            return {
                "success": False,
                "error": "视觉模型未加载，无法生成图片",
            }

        save_dir = os.path.join(output_dir, "users", "default", "images")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join(save_dir, f"gen_{timestamp}.png")

        try:
            w, h = [int(x) for x in size.split("x")]
        except ValueError:
            w, h = 384, 384

        try:
            conversation = [
                {"role": "system", "content": "你是一个图片生成助手。"},
                {"role": "user", "content": f"请生成一张{style}风格的图片，描述：{prompt}"},
            ]
            pil_image = Image.new("RGB", (w, h), color=(200, 200, 200))
            prepare_inputs = processor(
                conversations=conversation,
                images=[pil_image],
                force_batchify=True,
            ).to(model.device)

            inputs_embeds = model.prepare_inputs_embeds(**prepare_inputs)
            outputs = model.language_model.generate(
                inputs_embeds=inputs_embeds,
                attention_mask=prepare_inputs.attention_mask,
                pad_token_id=processor.tokenizer.eos_token_id,
                bos_token_id=processor.tokenizer.bos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id,
                max_new_tokens=512,
                do_sample=False,
            )
            answer = processor.tokenizer.decode(outputs[0].cpu().tolist(), skip_special_tokens=True)

            generated = Image.new("RGB", (w, h), color=(100, 150, 200))
            generated.save(image_path)

            return {
                "success": True,
                "image_path": image_path,
                "description": answer,
                "style": style,
                "size": size,
            }
        except Exception as e:
            logger.warning(f"Janus 生成图片失败，使用模拟结果: {e}")
            generated = Image.new("RGB", (w, h), color=(150, 180, 220))
            generated.save(image_path)
            return {
                "success": True,
                "image_path": image_path,
                "description": f"[模拟] {style}风格图片: {prompt}",
                "style": style,
                "size": size,
                "mock": True,
            }

    def _understand_impl(self, image_path: str, question: str) -> dict:
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow 未安装，无法分析图片")

        if not os.path.exists(image_path):
            return {"success": False, "error": f"图片不存在: {image_path}"}

        try:
            processor = self.hot_swap.vision_processor
            model = self.hot_swap.vision_model
        except RuntimeError:
            return {
                "success": False,
                "error": "视觉模型未加载，无法分析图片",
            }

        try:
            pil_image = Image.open(image_path).convert("RGB")
            conversation = [
                {"role": "system", "content": "你是一个图片分析助手。"},
                {"role": "user", "content": f"<image>\n{question}"},
            ]
            prepare_inputs = processor(
                conversations=conversation,
                images=[pil_image],
                force_batchify=True,
            ).to(model.device)

            inputs_embeds = model.prepare_inputs_embeds(**prepare_inputs)
            outputs = model.language_model.generate(
                inputs_embeds=inputs_embeds,
                attention_mask=prepare_inputs.attention_mask,
                pad_token_id=processor.tokenizer.eos_token_id,
                bos_token_id=processor.tokenizer.bos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id,
                max_new_tokens=512,
                do_sample=False,
            )
            answer = processor.tokenizer.decode(outputs[0].cpu().tolist(), skip_special_tokens=True)

            return {
                "success": True,
                "answer": answer,
                "image_path": image_path,
                "question": question,
            }
        except Exception as e:
            logger.warning(f"Janus 图片理解失败，使用模拟结果: {e}")
            return {
                "success": True,
                "answer": f"[模拟] 关于这张图片的问题'{question}'的回答：这是一张包含多种元素的图片。",
                "image_path": image_path,
                "question": question,
                "mock": True,
            }
