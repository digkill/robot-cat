async function loadEvents() {
  const res = await fetch('/api/events');
  const payload = await res.json();
  const events = payload.events || [];
  const el = document.getElementById('events');
  const badge = document.getElementById('stateBadge');
  badge.textContent = payload.state ? `(${payload.state})` : '';
  el.innerHTML = events.length
    ? events.slice(-20).reverse().map(e => {
        const ts = e.ts ? new Date(e.ts * 1000).toLocaleString() : 'без времени';
        const extra = e.s3_key ? ` · S3: ${e.s3_key}` : '';
        return `<div><strong>${e.type}</strong> — ${ts}${extra}</div>`;
      }).join('')
    : '<div>Нет событий</div>';
}

async function loadLog() {
  const res = await fetch('/api/log?lines=120');
  const payload = await res.json();
  document.getElementById('watchlog').textContent = payload.log || '';
}

async function loadRecordings() {
  const res = await fetch('/api/recordings');
  const files = await res.json();
  const el = document.getElementById('recordings');
  el.innerHTML = files.length
    ? files.map(f => `
      <div>
        <video controls preload="metadata" width="100%" src="${f.path}"></video>
        <a href="${f.path}" download>${f.name}</a>
      </div>
    `).join('')
    : '<div>Нет записей</div>';
}

async function loadSnapshots() {
  const res = await fetch('/api/snapshots');
  const files = await res.json();
  const el = document.getElementById('snapshots');
  el.innerHTML = files.length
    ? files.map(f => `
      <div>
        <img src="${f.path}" alt="${f.name}" loading="lazy" />
        <a href="${f.path}" download>${f.name}</a>
      </div>
    `).join('')
    : '<div>Нет снимков</div>';
}

async function loadCameraStatus() {
  const res = await fetch('/api/camera/status');
  const data = await res.json();
  const status = document.getElementById('cameraStatus');
  const btn = document.getElementById('cameraRecordBtn');
  if (data.recording) {
    btn.textContent = 'Остановить запись';
    btn.classList.add('recording-live');
    status.textContent = `Идёт запись с ${new Date(data.started_at).toLocaleTimeString()} · кадров: ${data.frames}`;
  } else {
    btn.textContent = 'Начать запись';
    btn.classList.remove('recording-live');
    status.textContent = 'Поток доступен по локальной сети';
  }
}

let volumeUpdateTimer;

function fillSelect(el, values, selected, allowEmpty = false) {
  const items = [];
  if (allowEmpty) items.push('<option value="">Без фона</option>');
  items.push(...values.map(value => `<option value="${value}">${value}</option>`));
  el.innerHTML = items.join('');
  el.value = selected || '';
}

async function loadFaceStatus() {
  const [faceRes, mediaRes] = await Promise.all([fetch('/api/face'), fetch('/api/media')]);
  const faceData = await faceRes.json();
  const mediaData = await mediaRes.json();
  const status = document.getElementById('faceStatus');
  if (!faceRes.ok) {
    status.textContent = faceData.error || 'Лицо недоступно';
    return;
  }
  fillSelect(document.getElementById('faceEmotion'), faceData.options.emotions || [], faceData.state.emotion);
  fillSelect(document.getElementById('faceTheme'), faceData.options.themes || [], faceData.state.theme);
  fillSelect(document.getElementById('faceAnimation'), faceData.options.animations || [], faceData.state.animation_mode);
  fillSelect(
    document.getElementById('faceBackground'),
    (mediaData || []).map(item => item.name),
    faceData.state.background_name,
    true
  );
  const bg = faceData.state.background_name
    ? `${faceData.state.background_kind}: ${faceData.state.background_name}`
    : 'без фона';
  status.textContent = `Сейчас: ${faceData.state.emotion} · ${faceData.state.theme} · ${faceData.state.animation_mode} · ${bg}`;
}

async function applyFaceSettings() {
  const payload = {
    emotion: document.getElementById('faceEmotion').value,
    theme: document.getElementById('faceTheme').value,
    animation_mode: document.getElementById('faceAnimation').value,
    background_name: document.getElementById('faceBackground').value
  };
  const res = await fetch('/api/face/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Ошибка лица');
  await loadFaceStatus();
}

async function uploadBackgroundMedia(file) {
  const fd = new FormData();
  fd.append('media', file, file.name);
  const res = await fetch('/api/media/upload', { method: 'POST', body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Ошибка загрузки');
  await loadFaceStatus();
  document.getElementById('faceBackground').value = data.name;
}

async function loadAudioStatus() {
  const res = await fetch('/api/audio/status');
  const data = await res.json();
  const slider = document.getElementById('volumeSlider');
  const valueEl = document.getElementById('volumeValue');
  const statusEl = document.getElementById('audioStatus');
  const muteBtn = document.getElementById('muteToggleBtn');
  if (!data.available) {
    slider.disabled = true;
    muteBtn.disabled = true;
    statusEl.textContent = 'ALSA/amixer недоступен';
    return;
  }
  slider.disabled = false;
  muteBtn.disabled = false;
  slider.value = data.volume;
  valueEl.textContent = `${data.volume}%`;
  muteBtn.textContent = data.muted ? 'Unmute' : 'Mute';
  statusEl.textContent = data.muted ? 'Звук выключен' : 'Звук включён';
}

async function setAudioVolume(volume) {
  const res = await fetch('/api/audio/volume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ volume })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Ошибка громкости');
  await loadAudioStatus();
}

async function toggleMute() {
  const muted = document.getElementById('muteToggleBtn').textContent === 'Mute';
  const res = await fetch('/api/audio/mute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ muted })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Ошибка mute');
  await loadAudioStatus();
}

async function toggleCameraRecording() {
  const btn = document.getElementById('cameraRecordBtn');
  const result = document.getElementById('cameraResult');
  const shouldStop = btn.classList.contains('recording-live');
  btn.disabled = true;
  result.textContent = shouldStop ? 'Остановка записи и сборка файла...' : 'Старт записи...';
  try {
    const res = await fetch(shouldStop ? '/api/camera/record/stop' : '/api/camera/record/start', {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Ошибка камеры');
    if (shouldStop) {
      const audioText = data.with_audio ? 'со звуком' : 'без звука';
      const s3Text = data.s3_key ? ` · S3: ${data.s3_key}` : '';
      result.innerHTML = `Готово: <a href="${data.path}" target="_blank">${data.name}</a> (${audioText})${s3Text}`;
      loadRecordings();
    } else {
      result.textContent = 'Запись запущена.';
    }
  } catch (e) {
    result.textContent = 'Ошибка: ' + e.message;
  } finally {
    btn.disabled = false;
    loadCameraStatus();
    loadEvents();
  }
}

async function sendToAssistant() {
  const input = document.getElementById('assistantInput');
  const text = input.value.trim();
  if (!text) return;
  const replyEl = document.getElementById('assistantReply');
  replyEl.textContent = '...';
  try {
    const res = await fetch('/api/assistant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    replyEl.textContent = data.reply || data.error || 'Нет ответа';
  } catch (e) {
    replyEl.textContent = 'Ошибка: ' + e.message;
  }
  input.value = '';
}

document.getElementById('assistantInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendToAssistant();
});

document.getElementById('cameraRecordBtn').addEventListener('click', toggleCameraRecording);
document.getElementById('cameraRefreshBtn').addEventListener('click', loadCameraStatus);
document.getElementById('faceApplyBtn').addEventListener('click', async () => {
  try {
    await applyFaceSettings();
  } catch (e) {
    document.getElementById('faceStatus').textContent = 'Ошибка: ' + e.message;
  }
});
document.getElementById('faceRefreshBtn').addEventListener('click', loadFaceStatus);
document.getElementById('backgroundUpload').addEventListener('change', async e => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  document.getElementById('faceStatus').textContent = 'Загрузка фона...';
  try {
    await uploadBackgroundMedia(file);
    document.getElementById('faceStatus').textContent = `Загружено: ${file.name}`;
  } catch (err) {
    document.getElementById('faceStatus').textContent = 'Ошибка: ' + err.message;
  } finally {
    e.target.value = '';
  }
});
document.getElementById('muteToggleBtn').addEventListener('click', async () => {
  try {
    await toggleMute();
  } catch (e) {
    document.getElementById('audioStatus').textContent = 'Ошибка: ' + e.message;
  }
});
document.getElementById('volumeSlider').addEventListener('input', e => {
  const volume = Number(e.target.value);
  document.getElementById('volumeValue').textContent = `${volume}%`;
  clearTimeout(volumeUpdateTimer);
  volumeUpdateTimer = setTimeout(async () => {
    try {
      await setAudioVolume(volume);
    } catch (err) {
      document.getElementById('audioStatus').textContent = 'Ошибка: ' + err.message;
    }
  }, 120);
});

let mediaRecorder;
let audioChunks;
document.getElementById('recordBtn').addEventListener('click', async () => {
  const btn = document.getElementById('recordBtn');
  const status = document.getElementById('recordStatus');
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = e => e.data.size && audioChunks.push(e.data);
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      const fd = new FormData();
      fd.append('audio', blob, 'recording.webm');
      status.textContent = 'Отправка...';
      btn.textContent = '🎙️ Записать голос';
      try {
        const res = await fetch('/api/audio/upload', { method: 'POST', body: fd });
        const data = await res.json();
        status.textContent = data.path ? 'Сохранено: ' + data.name : (data.error || 'Ошибка');
        if (data.path) loadRecordings();
      } catch (e) {
        status.textContent = 'Ошибка: ' + e.message;
      }
      btn.classList.remove('recording');
    };
    mediaRecorder.start();
    btn.classList.add('recording');
    btn.textContent = '⏹ Остановить';
    status.textContent = 'Запись...';
  } catch (e) {
    status.textContent = 'Ошибка: ' + e.message;
  }
});

document.getElementById('cameraStream').addEventListener('error', () => {
  document.getElementById('cameraStatus').textContent = 'Поток камеры недоступен';
});

loadEvents();
loadLog();
loadRecordings();
loadSnapshots();
loadCameraStatus();
loadFaceStatus();
loadAudioStatus();
setInterval(loadEvents, 5000);
setInterval(loadLog, 5000);
setInterval(loadCameraStatus, 3000);
setInterval(loadFaceStatus, 7000);
setInterval(loadAudioStatus, 5000);
