from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_ADDED
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, redirect, url_for
from flask_paginate import Pagination, get_page_parameter
from trans_youtube import generate_transcript_page, youtube_title2, target_languages
from pathlib import Path
import os
import re

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
        jobs_status[url]['msg'] = 'Because of an API Error. Please try again'

scheduler.add_listener(scheduler_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_ADDED)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        language_code = request.form['language']
        #  youtube_transcript(url, audio_only=False)
        if url is None or url == '':
            return redirect(url_for('index'))
        job = scheduler.add_job(func=generate_transcript_page, args=(url,), kwargs={'audio_only': False, 'language_code': language_code}, id=url)
        jobs_status[url] = {'status': 'Processing...', 'args': url, 'msg': ''}
        return redirect(url_for('index'))
    
    video_dirs = sorted([x for x in Path(static_folder).iterdir() if x.is_dir()], key=os.path.getmtime, reverse=True)

    videos = []
    for video in video_dirs:
        video_id = video.name
        title = youtube_title2(video_id)
        transcript = os.path.join(static_folder, video_id, f'{video_id}_transcript.txt')
        translation = os.path.join(static_folder, video_id, f'{video_id}_translated.txt')
        videos.append({'image': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg', 'title': title,
                      'url': f'/video/{video_id}/', 'transcript': transcript, 'translation': translation})

    jobs_status_ = ', '.join([f'{v["status"]} {v["msg"]} {v["args"]}' for k, v in jobs_status.items()])

    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    offset = (page - 1) * per_page
    total = len(videos)
    paginated_videos = videos[offset:offset + per_page]
    pagination = Pagination(page=page, total=total, per_page=per_page)

    return render_template('index.html', videos=paginated_videos, pagination=pagination, jobs_status=jobs_status_)

@app.route('/video/<video_id>/', methods=['GET'])
def video_page(video_id):
    title = youtube_title2(video_id)
    transcript_src = os.path.join(static_folder, video_id, f'{video_id}_transcript.txt')
    translated_src = os.path.join(static_folder, video_id, f'{video_id}_translated.txt')

    with open(transcript_src, 'r') as f:
        transcript = f.read()

    with open(translated_src, 'r') as f:
        translated = f.read()

    files = os.listdir(os.path.join(static_folder, video_id))
    language_code_pattern = re.compile(r'\.[a-z]{2}\.vtt')
    #  vtts = [{'language_code': f.split('.')[-2], 'src': f'/{static_folder}/{video_id}/{f}', 'language': target_languages.get(f.split('.')[-2])} for f in files if f.endswith('.vtt') and language_code_pattern.search(f)]
    vtts = []
    for file in files:
        if file.endswith('.vtt') and language_code_pattern.search(file):
            language_code = file.split('.')[-2]
            vtt_info = {
                'srclang': language_code,
                'src': f'/{static_folder}/{video_id}/{file}',
                'language': target_languages.get(language_code)
            }
            vtts.append(vtt_info)

    video_src = f'/{static_folder}/{video_id}/{video_id}.mp4'
    youtube_vtt_src = f'/{static_folder}/{video_id}/{video_id}.en.vtt'
    return render_template(f'video.html' , youtube_video_id=video_id, video_src=video_src, title=title,
                           transcript=transcript, translated=translated, youtube_vtt_src=youtube_vtt_src, vtts=vtts)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8002)
