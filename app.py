from trans_youtube import generate_transcript_page, youtube_title2
from flask import Flask, render_template, request, redirect, url_for
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_ADDED
from apscheduler.schedulers.background import BackgroundScheduler
import os

static_folder = 'output'
app = Flask(__name__, static_folder=static_folder)

jobs_status = {}
scheduler = BackgroundScheduler()
scheduler.start()

def scheduler_listener(event):
    if event.code == EVENT_JOB_EXECUTED:
        print('The youtube transcript job executed :)')
        url = event.job_id
        jobs_status.pop(url)
        #  socketio.emit('job_completed', {'job_id': job_id})
    elif event.code == EVENT_JOB_ADDED:
        print('The youtube transcript job was added')
    elif event.code == EVENT_JOB_ERROR:
        print('The youtube transcript job failed :(')
        url = event.job_id
        jobs_status[url]['status'] = 'Failed'
        jobs_status[url]['msg'] = 'Because of an Claude API Error. Please try again'

scheduler.add_listener(scheduler_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_ADDED)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        language_code = request.form['language']
        #  youtube_transcript(url, audio_only=False)
        job = scheduler.add_job(func=generate_transcript_page, args=(url,), kwargs={'audio_only': False,
                                                                                    'language_code': language_code}, id=url)
        jobs_status[url] = {'status': 'Processing...', 'args': url, 'msg': ''}
        return redirect(url_for('index'))
    
    video_dirs = [d for d in os.listdir(static_folder) if os.path.isdir(os.path.join(static_folder, d))]

    videos = []
    for video_id in video_dirs:
        title = youtube_title2(video_id)
        transcript = os.path.join(static_folder, video_id, f'{video_id}_transcript.txt')
        videos.append({'image': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg', 'title': title,
                      'url': f'/{static_folder}/{video_id}/index.html', 'transcript': transcript})

    jobs_status_ = ', '.join([f'{v["status"]} {v["msg"]} {v["args"]}' for k, v in jobs_status.items()])

    return render_template('index.html', videos=videos, jobs_status=jobs_status_)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8002)
