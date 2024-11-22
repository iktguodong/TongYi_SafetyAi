from flask import Flask, request, session, render_template, redirect, url_for
from http import HTTPStatus
from dashscope import Application
import os
import uuid
import json
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)

# File used to store history
history_file = 'sessions_history.json'

def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)
def load_history():
    if os.path.exists(history_file):
        with open(history_file, 'r') as file:
            try:
                data = json.load(file)
                # Check if the loaded data is a dictionary
                if isinstance(data, dict):
                    # Return only active sessions
                    return {k: v for k, v in data.items() if isinstance(v, dict) and v.get('is_active')}
                else:
                    # If data is not a dictionary, return an empty dictionary
                    return {}
            except json.JSONDecodeError:
                # If there's a JSON parsing error, return an empty dictionary
                return {}
    return {}



def save_history(history):
    with open(history_file, 'w') as file:
        json.dump(history, file)


# Initialize session history
sessions_history = load_history()


@app.route('/')
def index():
    user_id = session.get('user_id')
    if user_id and sessions_history.get(user_id, {}).get('is_active', False):
        # If an active session exists, show its conversation history
        return render_template('index.html', history=sessions_history[user_id]['conversation'])

    # If no active session exists, create a new one and add an introductory message
    user_id = str(uuid.uuid4())
    session['user_id'] = user_id
    intro_message = {
        'question': '',
        'answer': '你好，我是你的健康专家~~'
    }
    sessions_history[user_id] = {'conversation': [intro_message], 'is_active': True}
    save_history(sessions_history)

    return render_template('index.html', history=sessions_history[user_id]['conversation'])


@app.route('/ask', methods=['POST'])
def ask():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    prompt = request.form['prompt']
    app_id = os.getenv('ASSISTANT_ID')
    api_key = os.getenv('API_KEY')
    response = Application.call(app_id=app_id, prompt=prompt, api_key=api_key)

    if response.status_code != HTTPStatus.OK:
        result = {'request_id': response.request_id, 'error': response.message}
    else:
        # Get the answer and remove HTML tags
        answer = re.sub(r'\*\*', '', response.output.get('text', '无回答')).replace('\n', '<br>')
        stripped_answer = strip_html_tags(answer)  # Remove HTML tags

        result = {'question': prompt, 'answer': stripped_answer}

        # Save the cleaned question-answer to the conversation
        sessions_history[user_id]['conversation'].append(result)
        save_history(sessions_history)

    return render_template('index.html', result=result, history=sessions_history[user_id]['conversation'])


@app.route('/new_session')
def new_session():
    # Mark the current session as inactive and start a new one
    user_id = session.get('user_id')
    if user_id:
        sessions_history[user_id]['is_active'] = False
        save_history(sessions_history)

    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/history')
def view_history():
    # Display only completed sessions (inactive ones)
    completed_sessions = {
        k: v for k, v in sessions_history.items()
        if isinstance(v, dict) and 'is_active' in v and not v['is_active']
    }
    return render_template('history.html', history=completed_sessions)


@app.route('/delete_history/<user_id>', methods=['POST'])
def delete_history(user_id):
    if user_id in sessions_history:
        del sessions_history[user_id]
        save_history(sessions_history)
    return redirect(url_for('view_history'))


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
