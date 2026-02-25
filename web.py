from flask import Flask, redirect, url_for, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return 'Welcome to the Home Page!<h1>This is a heading</h1>'

# @app.route('/<name>')
# def show_info(name):
#     return f'<h1>Hello, {name}!</h1>'

# @app.route('/admin')
# def admin():
#     return redirect(url_for('home'))



if __name__ == '__main__':
    app.run()
