#!/usr/bin/env python
#pip install assemblyai yt_dlp anthropic nltk --user --break-system-packages

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from text_chunker import TextChunker
import argparse
import assemblyai as aai
import os
import yt_dlp

#  save_path = "/tmp"
current_path = os.path.dirname(os.path.realpath(__file__))
save_path = f"{current_path}/output"

audio_only_ydl_opts = {
    'format': 'm4a/bestaudio/best',  # The best audio version in m4a format
    'outtmpl': '%(id)s.%(ext)s',  # The output name should be the id followed by the extension
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
    }],
    'quiet': True,  # Suppress output
    'paths': {"home": save_path},  # Save the file to save_path
    'writesubtitles': True
}

def chunk_text_to_paragraphs_semantic(text):
    # NLTK의 TextTilingTokenizer를 사용하여 텍스트를 의미 단위로 분할
    chunker = TextChunker(maxlen=1000)
    return [ chunk for chunk in chunker.chunk(text) ]

def translate(paragraphs):
    # Claude API를 사용하여 한국어로 번역
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    messages = []
    for paragraph in paragraphs:
        if paragraph == "":
            continue
        messages.append({"role": "user", "content": f"{paragraph}"})
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system="당신은 유능한 AI 한국어 번역 어시스턴트입니다. 사용자의 질문에 대해 확인 없이 바로 간결하고 정확한 한국어 번역을 제공하세요. 불필요한 인사말이나 설명은 생략하고 핵심 정보만 전달하세요.",
            messages=messages
        )
        content = response.content[0].text
        messages.append({"role": "assistant", "content": content})
        print(content)
        print('---')

    print("\n한국어 번역:\n")
    for message in messages:
        print(message["content"])
        print('---')

def translate_vtt(vtt):
    # Claude API를 이용하여 vtt 파일을 한국어로 번역된 vtt 파일로 변환
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # make vtt one element per 70 lines
    # TODO: optimize best request line size to ???
    request_line_size = 70
    vtts = []
    lines = vtt.split("\n")
    for i in range(0, len(lines), request_line_size):
        vtts.append("\n".join(lines[i:i+request_line_size]))

    translated_vtts = []
    for vtt in vtts:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system="당신은 유능한 AI 한국어 번역 어시스턴트입니다. vtt 자막 파일을 입력 받아서, 사용자의 질문에 대해 확인 없이 바로 간결하고 정확한 한국어 vtt 자막 파일을 제공하세요. 불필요한 인사말이나 설명은 생략하고 핵심 정보만 전달하세요.",
            messages=[{"role": "user", "content": f"{vtt}"}]
        )
        content = response.content[0].text
        translated_vtts.append(content)

    return translated_vtts

def youtube_title(video_id):
    ydl_opts = { 'quiet': True }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        title = ydl.extract_info(video_id, download=False).get('title', None)
    return title

def youtube_title2(video_id):
    transcript = os.path.join(save_path, video_id, f'{video_id}_transcript.txt')
    if os.path.exists(transcript):
        # return first line of the transcript
        with open(transcript, 'r') as f:
            return f.readline().split(' - ')[0]
    return ""

def youtube_transcript(URL, audio_only=False):
    paragraphs = []

    ydl_opts = { 'outtmpl': '%(id)s.%(ext)s', 'paths': {"home": save_path}, 'writesubtitles': True }
    #  ydl_opts = {
    #      'outtmpl': '%(id)s.%(ext)s',
    #      'paths': {"home": save_path},
    #      'writesubtitles': True,
    #      'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    #      'postprocessors': [{
    #          'key': 'FFmpegVideoConvertor',
    #          'preferedformat': 'mp4',
    #      }],
    #  }

    if audio_only:
        ydl_opts = audio_only_ydl_opts

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download(URL)
        title = ydl.extract_info(URL, download=False).get('title', None)
        vid = ydl.extract_info(URL, download=False).get('id', None)
        filename = ydl.prepare_filename(ydl.extract_info(URL, download=False))

        # transcribe the audio
        config = aai.TranscriptionConfig(language_detection=True)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(filename)
    
        print("Original transcript:")
        print(transcript.text)
        print("---")
    
        # save the transcript to a file
        with open(f"{save_path}/{vid}_transcript.txt", "w") as f:
            f.write(f"{title} - {URL}\n\n")
            f.write(transcript.text)

        # save the transcript to a vtt file
        vtt = transcript.export_subtitles_vtt()
        en_vtt_filename = f"{filename}.en.vtt"
        with open(en_vtt_filename, "w") as f:
            f.write(vtt)

        ko_vtts = translate_vtt(vtt)
        print("\nKorean translation:")
        print(len(ko_vtts))
        ko_vtt_filename = f"{filename}.ko.vtt"
        with open(ko_vtt_filename, "w") as f:
            f.write("\n".join(ko_vtts))

        # copy the transcript to the clipboard
        if os.system("which /usr/bin/xclip > /dev/null 2>&1") == 0: # linux
            print("Transcript copied to clipboard")
            os.system(f"xclip -selection clipboard {save_path}/{vid}_transcript.txt")
    
        if os.system("which /usr/bin/pbcopy > /dev/null 2>&1") == 0: # mac os
            print("Transcript copied to clipboard")
            os.system(f"pbcopy < {save_path}/{vid}_transcript.txt")
    
        paragraphs = chunk_text_to_paragraphs_semantic(transcript.text)
        # print("\nParagraphs:")
        # print(paragraphs)

        video_src = os.path.basename(filename)
        en_vtt_src = os.path.basename(en_vtt_filename)
        ko_vtt_src = os.path.basename(ko_vtt_filename)
        if not audio_only:
            write_video_html(title, video_src, en_vtt_src, ko_vtt_src)
            os.system(f"mkdir -p {save_path}/{vid}")
            os.system(f"cp {save_path}/{vid}* {save_path}/{vid}")
            os.system(f"cp {save_path}/index.html {save_path}/{vid}")

        # for ios playable video, convert to mp4
        base_filename = filename.split(".")[0]
        video_converting_cmd = f"ffmpeg -y -hide_banner -i {filename} -c:v libx264 -preset veryfast -crf 22 -movflags +faststart -c:a aac -b:a 192k -pix_fmt yuv420p {base_filename}_converted.mp4"
        os.system(video_converting_cmd)
        os.system(f"mv {base_filename}_converted.mp4 {save_path}/{vid}/{video_src}")

        print(f"Transcript saved to {save_path}/{vid}_transcript.txt")
        print(f"Video saved to {save_path}/{vid}")

    return paragraphs

def write_video_html(title, video_src, en_vtt_src, ko_vtt_src):
    # download from youtube
    original_vtt_src = video_src.replace("mp4", "en")+ ".vtt"

    html = f"""
        <!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>번역: {title}</title>
    <!-- video.js CSS -->
    <link href="https://vjs.zencdn.net/8.16.1/video-js.css" rel="stylesheet" />
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- video.js JavaScript -->
    <script src="https://vjs.zencdn.net/8.16.1/video.min.js"></script>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-6 text-center">{title}</h1>
        <div class="max-w-3xl mx-auto">
            <video class="video-js vjs-default-skin vjs-16-9"
                id="my-video"
                class="video-js vjs-big-play-centered"
                controls
                preload="auto"
                width="640"
                height="360"
                data-setup=""
            >
                <source src="{video_src}" type="video/mp4" />
                <track kind="subtitles" src="{original_vtt_src}" srclang="en" label="Subtitle From Youtube">
                <track kind="subtitles" src="{en_vtt_src}" srclang="en" label="Orginal">
                <track kind="subtitles" src="{ko_vtt_src}" srclang="ko" label="한국어" default>
            </video>
        </div>
    </div>
</body>
</html>
        """
    with open(f"{save_path}/index.html", "w") as f:
        f.write(html)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Transcribe and translate a YouTube video')
    parser.add_argument('URL', type=str, help='The URL of the YouTube video to transcribe and translate')
    args = parser.parse_args()
    paragraphs = youtube_transcript(args.URL, audio_only=False)
    # translate(paragraphs)
