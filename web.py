from flask import Flask, redirect, url_for, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return app.send_static_file('index.html')

#url传递参数
@app.route('/info', methods=['POST'])
def info():
    #GET请求参数
    # pwd = request.args.get('pwd')
    # print(pwd)

    #POST请求参数
    info = request.get_json()
    print(info)

    return jsonify({"status": "success", "message": "服务器已收到数据"})

    #JSON数据
    # print(request.json, type(request.json))

    
#变量传递
# @app.route('/<name>')
# def show_info(name):
#     return f'<h1>Hello, {name}!</h1>'

#重定向
# @app.route('/admin')
# def admin():
#     return redirect(url_for('home'))



if __name__ == '__main__':
    app.run()
