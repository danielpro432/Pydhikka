    async def AvCh(self, message):
        reply = await message.get_reply_message()

        if not reply or not reply.media:
            return await utils.answer(message, self.strings["no_reply"])

        try:
            with tempfile.TemporaryDirectory() as tmp:
                input_path = os.path.join(tmp, "input")
                output_path = os.path.join(tmp, "output.mp4")

                await message.client.download_media(reply.media, input_path)

                # ---------- ЕСЛИ ФОТО ----------
                if reply.photo:
                    img = Image.open(input_path).convert("RGB")

                    size = max(img.width, img.height)
                    square = Image.new("RGB", (size, size), (0, 0, 0))
                    square.paste(img, ((size - img.width)//2, (size - img.height)//2))

                    square.save(input_path, format="JPEG")

                    uploaded = await self._client.upload_file(input_path)
                    result = await self._client(
                        UploadProfilePhotoRequest(file=uploaded)
                    )

                # ---------- GIF / VIDEO ----------
                else:
                    clip = mp.VideoFileClip(input_path)

                    # обрезка до 7 секунд
                    if clip.duration > MAX_DURATION:
                        clip = clip.subclip(0, MAX_DURATION)

                    # квадрат
                    size = min(clip.w, clip.h)
                    clip = clip.crop(
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                        width=size,
                        height=size
                    )

                    # убираем аудио
                    clip = clip.without_audio()

                    # экспорт
                    clip.write_videofile(
                        output_path,
                        codec="libx264",
                        fps=30,
                        audio=False,
                        verbose=False,
                        logger=None
                    )

                    uploaded = await self._client.upload_file(output_path)

                    result = await self._client(
                        UploadProfilePhotoRequest(video=uploaded)
                    )

                # удаляем старую, добавленную модулем
                self.added.append(result.photo)
                if len(self.added) > 1:
                    await self._client(DeletePhotosRequest(self.added[:-1]))
                    self.added = self.added[-1:]

                await utils.answer(message, self.strings["changed"])

        except Exception as e:
            logger.error(f"AvCh error: {e}")
            await utils.answer(message, self.strings["error"])
