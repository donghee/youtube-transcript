from trans_youtube import youtube_transcript, youtube_title2
from flask import Flask, render_template, request, redirect, url_for
import os

static_folder = 'output'
app = Flask(__name__, static_folder=static_folder)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        youtube_transcript(url, audio_only=False)
        return redirect(url_for('index'))
    
    video_dirs = [d for d in os.listdir(static_folder) if os.path.isdir(os.path.join(static_folder, d))]

    videos = []
    for video_id in video_dirs:
        title = youtube_title2(video_id)
        transcript = os.path.join(static_folder, video_id, f'{video_id}_transcript.txt')
        videos.append({'image': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg', 'title': title,
                      'url': f'/{static_folder}/{video_id}/index.html', 'transcript': transcript})

    return render_template('index.html', videos=videos)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8002)
