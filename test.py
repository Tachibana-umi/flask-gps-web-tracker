from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# 访问主页时，返回刚才写的 HTML 页面
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# 你已经写好的 POST 接口（我这里加了简单的打印逻辑）
@app.route('/upload_gps', methods=['POST'])
def receive_gps():
    data = request.json
    print("收到手机发来的 GPS 数据啦！", data)
    # 这里以后加上存入数据库的代码
    return jsonify({"status": "success", "message": "服务器已收到数据"})

if __name__ == '__main__':
    # host='0.0.0.0' 允许局域网内的其他设备（手机）访问
    app.run(host='0.0.0.0', port=5000, debug=True)