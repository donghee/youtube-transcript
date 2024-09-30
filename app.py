from trans_youtube import youtube_transcript, youtube_title2
from flask import Flask, render_template, request, redirect, url_for
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_ADDED
from apscheduler.schedulers.background import BackgroundScheduler
import os

jobs_status = {}
scheduler = BackgroundScheduler()
scheduler.start()

def scheduler_listener(event):
    if event.code == EVENT_JOB_EXECUTED:
        print('The youtube trascript job excuted :)')
        jobs_status.pop(event.job_id)
    elif event.code == EVENT_JOB_ADDED:
        print('The youtube trascript job was added')

scheduler.add_listener(scheduler_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_ADDED)

static_folder = 'output'
app = Flask(__name__, static_folder=static_folder)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        #  youtube_transcript(url, audio_only=False)
        job = scheduler.add_job(func=youtube_transcript, args=(url,), kwargs={'audio_only': False}, id=url)
        jobs_status[url] = {'status': 'Processing...', 'args': url}
        return redirect(url_for('index'))
    
    video_dirs = [d for d in os.listdir(static_folder) if os.path.isdir(os.path.join(static_folder, d))]

    videos = []
    for video_id in video_dirs:
        title = youtube_title2(video_id)
        transcript = os.path.join(static_folder, video_id, f'{video_id}_transcript.txt')
        videos.append({'image': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg', 'title': title,
                      'url': f'/{static_folder}/{video_id}/index.html', 'transcript': transcript})

    jobs_status_ = ', '.join([f'{v["status"]} {v["args"]}' for k, v in jobs_status.items()])

    return render_template('index.html', videos=videos, jobs_status=jobs_status_)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8002)
