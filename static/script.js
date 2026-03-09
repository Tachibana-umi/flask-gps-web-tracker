// 全局变量定义
var marker       = null;
var pathPolyline = null;
var pathPoints   = [];
var watchId      = null;    // Geolocation API 的监听ID
var wakeLock     = null;    // Wake Lock API 的锁对象

var statusEl  = document.getElementById('status');      //显示状态，便于调试、展示信息
var btnToggle = document.getElementById('btn-toggle');  //登录/注册按钮
var btnClear  = document.getElementById('btn-clear');   //清除路径按钮

// 与登录相关的 DOM 元素
var userLabel      = document.getElementById('user-label');
var btnOpenAuth    = document.getElementById('btn-open-auth');
var btnLogout      = document.getElementById('btn-logout');
var authModal      = document.getElementById('auth-modal');
var authClose      = document.getElementById('auth-close');
var tabLogin       = document.getElementById('auth-tab-login');
var tabRegister    = document.getElementById('auth-tab-register');
var formLogin      = document.getElementById('auth-login-form');
var formRegister   = document.getElementById('auth-register-form');
var authErrorEl    = document.getElementById('auth-error');
var authMessageEl  = document.getElementById('auth-message');


// ================= 1. 初始化地图 =================
// 默认中心点（北京天安门），如果用户允许获取位置，后续会自动调整到当前位置
var defaultPoint = [39.915, 116.404];
var map = L.map('map').setView(defaultPoint, 15);

// 使用 OpenStreetMap 的免费瓦片服务
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap'
}).addTo(map);

// 页面加载时获取一次初始位置作为地图中心
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(function(position) {
    map.setView([position.coords.latitude, position.coords.longitude], 16);
  }, function() {
    console.log("未授权或无法获取初始位置");
  });
}

// ================= 2. Kalman 滤波器 =================
/**
 * 一维卡尔曼滤波
 *   R：测量噪声协方差，越大越平滑（但会滞后），建议 3~10
 *   Q：过程噪声协方差，越大越跟随真实值，建议 0.1~1
 *   P：误差协方差，越大估计越不可靠，初始值可以设为 1
 *   K：卡尔曼增益，自动计算，范围 0~1
 *   x：当前估计值，初始为 null，表示未有有效测量输入
 */

// 对经纬度各自独立滤波
var kfLat = new KalmanFilter({R: 3, Q: 0.6});
var kfLng = new KalmanFilter({R: 3, Q: 0.6});

// ================= 3. 速度合理性检查 =================
/**
 * 检测当前点是否为"跳跃点"
 * 根据与上一有效点之间的距离 / 时间差计算速度，
 * 超过 MAX_SPEED_MS（默认 10 m/s ≈ 36 km/h）则视为异常点丢弃。
 */
var MAX_SPEED_MS = 10;  // 单位：m/s，可按实际场景调整（步行 ~2、驾车 ~30）
var lastValidPoint = null;  // { lat, lng, timestamp }

function isJumpPoint(lat, lng, timestamp) {
  if (!lastValidPoint) return false;  // 第一个点，无法判断

  var dist = map.distance(
    [lastValidPoint.lat, lastValidPoint.lng],
    [lat, lng]
  ); // Leaflet 内置距离计算，返回单位 米

  var timeDiff = (timestamp - lastValidPoint.timestamp) / 1000; // 毫秒 → 秒
  if (timeDiff <= 0) return false;  // 时间戳异常时不过滤

  var speed = dist / timeDiff;

  if (speed > MAX_SPEED_MS) {
    console.warn('速度异常被过滤：' + Math.round(speed) + ' m/s,距离 ' + Math.round(dist) + ' 米');
    return true;
  }
  return false;
}

// ================= 4. 核心：处理位置更新 =================
function updateLocation(position) {
  var rawLat   = position.coords.latitude;
  var rawLng   = position.coords.longitude;
  var accuracy = position.coords.accuracy;
  var timestamp = position.timestamp || Date.now();

  // ── 第一道过滤：精度过差直接丢弃 ──
  if (accuracy > 20) {
    console.log('精度太差被过滤：误差 ' + Math.round(accuracy) + ' 米');
    return;
  }

  // ── 第二道过滤：速度检查（跳跃点）──
  if (isJumpPoint(rawLat, rawLng, timestamp)) {
    statusEl.textContent = '采集中... 跳跃点已过滤（精度: ' + Math.round(accuracy) + '米）';
    return;
  }

  // ── 第三步：Kalman 滤波平滑坐标 ──
  var smoothLat = kfLat.filter(rawLat);
  var smoothLng = kfLng.filter(rawLng);

  console.log(
    '原始:', rawLat.toFixed(6), rawLng.toFixed(6),
    '→ 平滑后:', smoothLat.toFixed(6), smoothLng.toFixed(6),
    '精度:', Math.round(accuracy) + 'm'
  );
  statusEl.textContent = '采集中... 精度: ' + Math.round(accuracy) + '米';

  // 记录本次有效点（用原始坐标做速度判断，避免滤波后距离失真）
  lastValidPoint = { lat: rawLat, lng: rawLng, timestamp: timestamp };

  // 使用平滑后的坐标绘图
  var currentLatLng = [smoothLat, smoothLng];
  pathPoints.push(currentLatLng);

  // 更新或创建大头针
  if (!marker) {
    marker = L.marker(currentLatLng).addTo(map);
    map.setView(currentLatLng, 17);
  } else {
    marker.setLatLng(currentLatLng);
    map.setView(currentLatLng);
  }

  // 更新或创建路径折线
  if (!pathPolyline) {
    pathPolyline = L.polyline(pathPoints, {
      color: '#1976d2',
      weight: 5,
      opacity: 0.8
    }).addTo(map);
  } else {
    pathPolyline.setLatLngs(pathPoints);
  }

  // 上报给 Flask 后端（上报平滑后的坐标）
  // 登录后，后端会把数据写入数据库。
  fetch('/api/location', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      latitude:  smoothLat,
      longitude: smoothLng,
      timestamp: new Date(timestamp).toISOString()
    })
  }).then(function (res) {
    // 如果未登录，后端会返回 401并打印日志
    if (!res.ok) {
      if (res.status === 401) {
        console.log('未登录：轨迹只在本地显示，不会保存到服务器。');
      } else {
        console.warn('上报位置信息返回状态码：', res.status);
      }
    }
  }).catch(function(err) {
    console.error('上报位置信息失败：', err);
  });
}

// ================= 5. 错误处理与控制按钮 =================

btnToggle.addEventListener('click', toggleTracking);
btnClear.addEventListener('click', clearPath);

function handleLocationError(error) {
  var msg = "发生未知错误";
  switch(error.code) {
    case error.PERMISSION_DENIED:    msg = "用户拒绝了定位请求。"; break;
    case error.POSITION_UNAVAILABLE: msg = "位置信息不可用。"; break;
    case error.TIMEOUT:              msg = "获取位置超时。"; break;
  }
  console.error(msg, error);
  statusEl.textContent = msg;
  stopTracking();
}

function startTracking() {
  if (!navigator.geolocation) {
    alert("您的浏览器不支持地理位置。");
    return;
  }
  if (watchId !== null) return;

  statusEl.textContent = '正在请求定位权限...';
  watchId = navigator.geolocation.watchPosition(updateLocation, handleLocationError, {
    enableHighAccuracy: true,         //高精度模式
    maximumAge: 0,                    //不使用缓存位置，确保每次都是最新数据
    timeout: 10000
  });
  // 请求 Wake Lock，保持屏幕常亮
  requestWakeLock();

  // 采集中时，把按钮文字切换为“结束轨迹”
  if (btnToggle) {
    btnToggle.textContent = '结束轨迹';
    btnToggle.style.backgroundColor = '#d32f2f';
    btnToggle.style.color = '#fff';
    btnClear.style.display = '';
  }
}

function stopTracking() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
    statusEl.textContent = '已停止采集。共 ' + pathPoints.length + ' 个有效点。';
  }  
  // 释放 Wake Lock（允许屏幕熄灭）
  releaseWakeLock();
  
    // 停止后，把按钮文字切换回“开始轨迹”
  if (btnToggle) {
    btnToggle.textContent = '开始轨迹';
    btnToggle.style.backgroundColor = '#ffffff';
    btnToggle.style.color = '#1976d2';
    btnClear.style.display = 'none';
  }
}

// 统一的点击事件：根据当前是否在采集，决定“开始”还是“结束”
function toggleTracking() {
  if (watchId === null) {
    startTracking();
  } else {
    stopTracking();
  }
}

function clearPath() {
  pathPoints     = [];
  lastValidPoint = null;
  // 重置滤波器状态，避免新轨迹受旧数据影响
  kfLat.x = NaN;
  kfLat.cov = NaN;
  kfLng.x = NaN;
  kfLng.cov = NaN;

  if (pathPolyline) { map.removeLayer(pathPolyline); pathPolyline = null; }
  //if (marker)       { map.removeLayer(marker);       marker = null;       }
  statusEl.textContent = '路径已清除。';
}

// ================= Wake Lock API 相关函数 =================
/**
 * 请求 Wake Lock（保持屏幕常亮）
 * 用途：防止手机在采集轨迹时熄屏，导致 GPS 更新暂停
 */
function requestWakeLock() {
  // 检查浏览器是否支持 Wake Lock API
  if (!('wakeLock' in navigator)) {
    console.warn('当前浏览器不支持 Wake Lock API,建议使用 Chrome/Edge/Safari 最新版本。');
    alert('提示：您的浏览器可能不支持屏幕常亮功能。\n\n为确保轨迹采集不中断,请手动保持屏幕亮着(我知道这很蠢...),或在系统设置中延长息屏时间。');
    return;
  }

  // 请求屏幕唤醒锁
  navigator.wakeLock.request('screen').then(function(lock) {
    wakeLock = lock;
    console.log('Wake Lock 激活成功：屏幕将保持常亮，直到结束采集。');
    
    // 监听锁被释放的事件（如用户手动切换应用）
    wakeLock.addEventListener('release', function() {
      console.log('Wake Lock 已释放（可能因切换应用或系统限制）');
    });
  }).catch(function(err) {
    console.error('Wake Lock 请求失败：', err.name, err.message);
    alert('无法保持屏幕常亮，请手动保持屏幕亮着以确保轨迹采集正常。');
  });
}

/**
 * 释放 Wake Lock（允许屏幕熄灭）
 */
function releaseWakeLock() {
  if (wakeLock !== null) {
    wakeLock.release().then(function() {
      console.log('Wake Lock 已释放：屏幕可以正常熄灭。');
      wakeLock = null;
    }).catch(function(err) {
      console.error('释放 Wake Lock 失败：', err);
    });
  }
}

// 监听页面可见性变化（如切换到后台）
document.addEventListener('visibilitychange', function() {
  if (document.visibilityState === 'visible' && watchId !== null && wakeLock === null) {
    // 页面重新可见且正在采集，重新请求 Wake Lock
    console.log('页面重新可见，尝试恢复 Wake Lock...');
    requestWakeLock();
  }
});


// ================= 6. 登录 / 注册弹窗与后端交互 =================
// 这一部分代码实现：
// 1. 在右上角展示“当前登录状态”（未登录 / 已登录：用户名）。
// 2. 点“登录 / 注册”打开弹窗，在其中完成注册或登录。
// 3. 登录成功后，轨迹上报接口就会把数据写入数据库。

// 注册事件监听
tabLogin.addEventListener('click', function () { setAuthTab('login'); });
tabRegister.addEventListener('click', function () { setAuthTab('register'); });
btnOpenAuth.addEventListener('click', function () { openAuthModal('login'); });
authClose.addEventListener('click', function () { closeAuthModal(); });

// 切换弹窗中的“登录 / 注册”标签页
function setAuthTab(type) {
  if (type === 'login') {
    tabLogin.classList.add('active');
    tabRegister.classList.remove('active');
    formLogin.style.display = '';
    formRegister.style.display = 'none';
  } else {
    tabRegister.classList.add('active');
    tabLogin.classList.remove('active');
    formRegister.style.display = '';
    formLogin.style.display = 'none';
  }
  authErrorEl.textContent = '';
  authMessageEl.textContent = '';
}

// 打开登录/注册弹窗，默认显示登录页
function openAuthModal(defaultTab) {
  setAuthTab(defaultTab || 'login');
  authModal.classList.add('active');
}

function closeAuthModal() {
  authModal.classList.remove('active');
  authErrorEl.textContent = '';
  authMessageEl.textContent = '';
}

// 从 /api/me 获取当前登录状态，并更新右上角显示
function refreshUserInfo() {
  fetch('/api/me')
  .then(function (res) { return res.json(); })
  .then(function (data) {
    if (data.logged_in) {
      userLabel.textContent = '已登录：' + data.username;
      btnOpenAuth.style.display = 'none';
      //btnOpenAuth.textContent = '切换账号';
      btnLogout.style.display = '';
    } else {
      userLabel.textContent = '未登录';
      btnOpenAuth.style.display = '';
      btnOpenAuth.textContent = '登录 / 注册';
      btnLogout.style.display = 'none';
    }
  })
  .catch(function (err) {
    console.error('获取登录状态失败：', err);
  });
}

// 登录表单提交事件：调用后端 /login 接口
formLogin.addEventListener('submit', function (event) {
  event.preventDefault();
  var username = document.getElementById('login-username').value.trim();
  var password = document.getElementById('login-password').value;

  authErrorEl.textContent = '';
  authMessageEl.textContent = '正在登录...';

  fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: password })
  })
  .then(function (res) { return res.json().then(function (data) { return { res: res, data: data }; }); })
  .then(function (result) {
    var res = result.res;
    var data = result.data;
    if (!res.ok || !data.ok) {
      authErrorEl.textContent = (data && data.error) || '登录失败，请重试。';
      authMessageEl.textContent = '';
      return;
    }
    authMessageEl.textContent = '登录成功！';
    authErrorEl.textContent = '';
    refreshUserInfo();
    // 短暂延迟后关闭弹窗
    setTimeout(closeAuthModal, 1000);
  })
  .catch(function (err) {
    console.error('登录请求失败：', err);
    authErrorEl.textContent = '登录请求失败，请检查网络。';
    authMessageEl.textContent = '';
  });
});

// 注册表单提交事件：调用后端 /register 接口
formRegister.addEventListener('submit', function (event) {
  event.preventDefault();
  var username = document.getElementById('register-username').value.trim();
  var password = document.getElementById('register-password').value;

  authErrorEl.textContent = '';
  authMessageEl.textContent = '正在注册...';

  fetch('/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: username, password: password })
  })
  .then(function (res) { return res.json().then(function (data) { return { res: res, data: data }; }); })
  .then(function (result) {
    var res = result.res;
    var data = result.data;
    if (!res.ok || !data.ok) {
      authErrorEl.textContent = (data && data.error) || '注册失败，请重试。';
      authMessageEl.textContent = '';
      return;
    }
    authMessageEl.textContent = data.message || '注册成功，请使用该账号登录。';
    authErrorEl.textContent = '';
    // 注册成功后，自动切换到“登录”标签，方便用户直接登录
    setAuthTab('login');
  })
  .catch(function (err) {
    console.error('注册请求失败：', err);
    authErrorEl.textContent = '注册请求失败，请检查网络。';
    authMessageEl.textContent = '';
  });
});

// 退出登录按钮：调用 /logout 接口
btnLogout.addEventListener('click', function () {
  fetch('/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
  .then(function () {
    refreshUserInfo();
  })
  .catch(function (err) {
    console.error('退出登录失败：', err);
  });
});

// 页面加载完成后，先查询一次当前登录状态
refreshUserInfo();