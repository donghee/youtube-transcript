#!/usr/bin/env python
#pip install assemblyai yt_dlp anthropic nltk --user --break-system-packages

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from text_chunker import TextChunker
import argparse
import assemblyai as aai
import os
import yt_dlp
from tqdm import tqdm

#  save_path = "/tmp"
current_path = os.path.dirname(os.path.realpath(__file__))
save_path = f"{current_path}/output"

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

    # TODO: optimize best request line size
    line_size_one_request = int(66/3)
    vtts = []
    lines = vtt.split("\n\n")
    for i in range(0, len(lines), line_size_one_request):
        vtts.append("\n\n".join(lines[i:i+line_size_one_request]))

    translated_vtts = []
    for vtt in tqdm(vtts, desc="Translating VTT"):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    system="당신은 유능한 AI 한국어 번역 어시스턴트입니다. vtt 자막 파일을 입력 받아서, 사용자의 질문에 대해 확인 없이 바로 간결하고 정확한 한국어 vtt 자막 파일을 제공하세요. 불필요한 인사말이나 설명은 생략하고 핵심 정보만 전달하세요.",
                    messages=[{"role": "user", "content": f"{vtt}"}]
                )
                content = response.content[0].text
                translated_vtts.append(content)
                break
            except Exception as e:
                print(f"Error occurred: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying... (Attempt {attempt + 2}/{max_retries})")
                else:
                    print(f"Failed to translate after {max_retries} attempts. Skipping this chunk.")
                    translated_vtts.append(vtt)  # 번역 실패 시 원본 텍스트 추가

    return translated_vtts

def youtube_info(URL):
    ydl_opts = { 'quiet': True }
    title = ""
    vid = ""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        vid = ydl.extract_info(URL, download=False).get('id', None)
        title = ydl.extract_info(vid, download=False).get('title', None)

    return vid, title


def youtube_title2(video_id):
    transcript = os.path.join(save_path, video_id, f'{video_id}_transcript.txt')
    if os.path.exists(transcript):
        # return first line of the transcript
        with open(transcript, 'r') as f:
            return f.readline().split(' - ')[0]
    return ""

def youtube_transcript(URL):
    paragraphs = []
    transcript = None
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

    with yt_dlp.YoutubeDL(audio_only_ydl_opts) as ydl:
        error_code = ydl.download(URL)
        vid, title = youtube_info(URL)
        filename = ydl.prepare_filename(ydl.extract_info(URL, download=False))
        filesize = os.path.getsize(filename) / 1024 / 1024
        print(f"Download: {filename}, {filesize} MB")

        # transcribe the audio
        config = aai.TranscriptionConfig(language_detection=True)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(filename)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"Transcription failed: {transcript.error}")
            raise Exception(f"Transcription failed: {transcript.error}")
    
        print("Original transcript:")
        print(transcript.text)
        print("---")

    return transcript

def save_transcript(transcript, vid, title):
    # save the transcript to a file
    transcript_filename = f"{save_path}/{vid}_transcript.txt"
    with open(transcript_filename, "w") as f:
        f.write(f"{title} - https://www.youtube.com/watch?v={vid}\n\n")
        f.write(transcript.text)

    # save the transcript to a vtt file
    vtt = transcript.export_subtitles_vtt()
    en_vtt_filename = f"{save_path}/{vid}.en.vtt"
    with open(en_vtt_filename, "w") as f:
        f.write(vtt)

    ko_vtts = translate_vtt(vtt)
    print("\nKorean translation:")
    print(len(ko_vtts))
    ko_vtt_filename = f"{save_path}/{vid}.ko.vtt"
    with open(ko_vtt_filename, "w") as f:
        f.write("\n".join(ko_vtts))

    # copy the transcript to the clipboard
    #  if os.system("which /usr/bin/xclip > /dev/null 2>&1") == 0: # linux
    #      print("Transcript copied to clipboard")
    #      os.system(f"xclip -selection clipboard {save_path}/{vid}_transcript.txt")
    #
    #  if os.system("which /usr/bin/pbcopy > /dev/null 2>&1") == 0: # mac os
    #      print("Transcript copied to clipboard")
    #      os.system(f"pbcopy < {save_path}/{vid}_transcript.txt")
    
    #  paragraphs = chunk_text_to_paragraphs_semantic(transcript.text)
    # print("\nParagraphs:")
    # print(paragraphs)
    return transcript_filename, en_vtt_filename, ko_vtt_filename

def generate_html(vid, title, transcript_filename, en_vtt, ko_vtt):
    video_src = f"{vid}.mp4"
    en_vtt_src = os.path.basename(en_vtt)
    ko_vtt_src = os.path.basename(ko_vtt)

    transcript = ""
    with open(transcript_filename, "r") as f:
        transcript = f.read()

    write_video_html(title, video_src, en_vtt_src, ko_vtt_src, transcript)

    os.system(f"mkdir -p {save_path}/{vid}")
    os.system(f"cp {save_path}/{vid}* {save_path}/{vid}")
    os.system(f"cp {save_path}/index.html {save_path}/{vid}")

def save_video(URL): 
    ydl_opts = { 'outtmpl': '%(id)s.%(ext)s', 'paths': {"home": save_path}, 'writesubtitles': True }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download(URL)
        vid, title = youtube_info(URL)
        filename = ydl.prepare_filename(ydl.extract_info(URL, download=False))
        filesize = os.path.getsize(filename) / 1024 / 1024
        print(f"Download: {filename}, {filesize} MB")

        # for ios playable video, convert to mp4
        base_filename = filename.split(".")[0]
        video_filter=""
        if filesize > 1000: # 1000MB
            video_filter="-vf scale=1920:-1" # 1080p

        video_converting_cmd = f"ffmpeg -y -hide_banner -i {filename} {video_filter} -c:v libx264 -preset veryfast -crf 22 -movflags +faststart -c:a aac -b:a 192k -pix_fmt yuv420p {base_filename}_converted.mp4"
        os.system(video_converting_cmd)
        os.system(f"mv {base_filename}_converted.mp4 {save_path}/{vid}/{vid}.mp4")

        print(f"Video saved to {save_path}/{vid}")

def write_video_html(title, video_src, en_vtt_src, ko_vtt_src, transcript):
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
        <div class="mt-10 max-w-3xl mx-auto">
            <p>
            From: https://www.youtube.com/watch?v={video_src.split('.')[0]}
            </p>
        </div>
        <div class="mt-10 max-w-3xl mx-auto">
            <h2 class="text-2xl font-bold mb-4">Transcript</h2>
            <div class="bg-white p-4 rounded-lg shadow-md">
               <pre class="whitespace-pre-wrap">
{transcript}
               </pre>
            </div>
        </div>
    </div>
</body>
</html>
        """
    with open(f"{save_path}/index.html", "w") as f:
        f.write(html)

def generate_transcript_page(URL, audio_only=False):
    transcript = youtube_transcript(URL)
    vid, title = youtube_info(URL)
    transcript_filename, en_vtt_filename, ko_vtt_filename = save_transcript(transcript, vid, title)
    generate_html(vid, title, transcript_filename, en_vtt_filename, ko_vtt_filename)
    save_video(URL)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Transcribe and translate a YouTube video')
    parser.add_argument('URL', type=str, help='The URL of the YouTube video to transcribe and translate')
    args = parser.parse_args()

    generate_transcript_page(args.URL)
