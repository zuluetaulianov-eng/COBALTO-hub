@echo off
for %%f in (*.mp4) do (
    ffmpeg -i "%%f" ^
      -vcodec libx264 -crf 23 -preset fast ^
      -vf scale=1280:-2 ^
      -movflags +faststart ^
      -pix_fmt yuv420p ^
      -acodec aac -b:a 128k ^
      "opt_%%~nf.mp4"
)
echo Compresion terminada. Archivos con prefijo "opt_"
pause